"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/gateway";

const VOICE_SETTINGS_KEY = "local-ai-voice-settings";

export interface VoicePreferences {
  voiceURI: string;
  rate: number;
  pitch: number;
}

const DEFAULT_VOICE_PREFERENCES: VoicePreferences = {
  voiceURI: "",
  rate: 1,
  pitch: 1,
};

function cleanSpeechText(text: string): string {
  return text
    .replace(/<think>[\s\S]*?<\/think>/g, " ")
    .replace(/<\/think>/g, " ")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[#*_>\-\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// ---------------------------------------------------------------------------
// Voice Settings (localStorage)
// ---------------------------------------------------------------------------

export function useVoiceSettings() {
  const [settings, setSettings] = useState<VoicePreferences>(() => {
    if (typeof window === "undefined") return DEFAULT_VOICE_PREFERENCES;
    try {
      const raw = window.localStorage.getItem(VOICE_SETTINGS_KEY);
      if (!raw) return DEFAULT_VOICE_PREFERENCES;
      const parsed = JSON.parse(raw) as Partial<VoicePreferences>;
      return {
        voiceURI: typeof parsed.voiceURI === "string" ? parsed.voiceURI : "",
        rate: typeof parsed.rate === "number" ? parsed.rate : 1,
        pitch: typeof parsed.pitch === "number" ? parsed.pitch : 1,
      };
    } catch {
      return DEFAULT_VOICE_PREFERENCES;
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(VOICE_SETTINGS_KEY, JSON.stringify(settings));
  }, [settings]);

  return { settings, setSettings };
}

// ---------------------------------------------------------------------------
// Available TTS voices
// ---------------------------------------------------------------------------

export function useSpeechVoices() {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return [];
    return window.speechSynthesis.getVoices();
  });

  const loadVoices = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setVoices([]);
      return;
    }
    const available = window.speechSynthesis.getVoices();
    setVoices(available);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
  }, [loadVoices]);

  return voices;
}

// ---------------------------------------------------------------------------
// Speech-to-Text via MediaRecorder + backend Whisper
// ---------------------------------------------------------------------------

export function useSpeechRecognition(options?: {
  token?: string | null;
  onFinalTranscript?: (text: string) => void;
}) {
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const abortedRef = useRef(false);

  const onFinalTranscriptRef = useRef(options?.onFinalTranscript);
  onFinalTranscriptRef.current = options?.onFinalTranscript;
  const tokenRef = useRef(options?.token);
  tokenRef.current = options?.token;

  const supportsVoiceInput =
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function";

  const startListening = useCallback(async () => {
    setError(null);
    setTranscript("");
    abortedRef.current = false;

    if (!supportsVoiceInput) {
      setError("Microphone access is not available in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (abortedRef.current) {
          chunksRef.current = [];
          return;
        }

        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];

        if (blob.size === 0) {
          setError("No audio recorded");
          return;
        }

        const token = tokenRef.current;
        if (!token) {
          setError("Not authenticated");
          return;
        }

        setIsTranscribing(true);
        try {
          const text = await transcribeAudio(token, blob);
          setTranscript(text);
          if (text.trim() && onFinalTranscriptRef.current) {
            onFinalTranscriptRef.current(text.trim());
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Transcription failed");
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsListening(true);
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Microphone permission denied. Allow access in browser settings.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to start recording");
      }
    }
  }, [supportsVoiceInput]);

  const stopListening = useCallback(() => {
    abortedRef.current = false;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === "recording") {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    setIsListening(false);
  }, []);

  const abortListening = useCallback(() => {
    abortedRef.current = true;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === "recording") {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    chunksRef.current = [];
    setIsListening(false);
  }, []);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return {
    supportsSpeechRecognition: supportsVoiceInput,
    isListening,
    isTranscribing,
    transcript,
    error,
    startListening,
    stopListening,
    abortListening,
  };
}

// ---------------------------------------------------------------------------
// Text-to-Speech via browser SpeechSynthesis
// ---------------------------------------------------------------------------

export function useSpeechSynthesis(settings: VoicePreferences, voices: SpeechSynthesisVoice[]) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const supportsSpeechSynthesis = typeof window !== "undefined" && "speechSynthesis" in window;

  const speak = useCallback(
    (rawText: string) => {
      if (!supportsSpeechSynthesis || !rawText.trim()) return;
      const text = cleanSpeechText(rawText);
      if (!text) return;

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = settings.rate;
      utterance.pitch = settings.pitch;

      const selectedVoice = voices.find((voice) => voice.voiceURI === settings.voiceURI);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
        if (!utterance.lang) utterance.lang = selectedVoice.lang;
      }

      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    },
    [settings.pitch, settings.rate, settings.voiceURI, supportsSpeechSynthesis, voices]
  );

  const cancel = useCallback(() => {
    if (!supportsSpeechSynthesis) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [supportsSpeechSynthesis]);

  return { supportsSpeechSynthesis, isSpeaking, speak, cancel };
}
