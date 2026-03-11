"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => unknown;
    webkitSpeechRecognition?: new () => unknown;
  };
  return (w.SpeechRecognition || w.webkitSpeechRecognition || null) as SpeechRecognitionCtor | null;
}

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

export function useSpeechRecognition(options?: { lang?: string; onFinalTranscript?: (text: string) => void }) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const supportsSpeechRecognition = useMemo(() => getRecognitionCtor() !== null, []);

  const createRecognition = useCallback(() => {
    if (recognitionRef.current) return recognitionRef.current;
    const Ctor = getRecognitionCtor();
    if (!Ctor) return null;

    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = options?.lang || "en-US";

    recognition.onstart = () => {
      setError(null);
      setTranscript("");
      setIsListening(true);
    };
    recognition.onend = () => {
      setIsListening(false);
    };
    recognition.onerror = (event) => {
      setError(event.error || "speech recognition error");
      setIsListening(false);
    };
    recognition.onresult = (event) => {
      let finalText = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript || "";
        if ((result as { isFinal?: boolean }).isFinal) {
          finalText += text;
        } else {
          interim += text;
        }
      }
      const merged = `${finalText} ${interim}`.trim();
      setTranscript(merged);
      if (finalText.trim() && options?.onFinalTranscript) {
        options.onFinalTranscript(finalText.trim());
      }
    };

    recognitionRef.current = recognition;
    return recognition;
  }, [options]);

  const startListening = useCallback(() => {
    setError(null);
    if (!supportsSpeechRecognition) {
      setError("Voice input is not supported in this browser.");
      return;
    }
    const recognition = createRecognition();
    if (!recognition) return;
    recognition.lang = options?.lang || "en-US";
    recognition.start();
  }, [createRecognition, options, supportsSpeechRecognition]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const abortListening = useCallback(() => {
    recognitionRef.current?.abort();
  }, []);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return {
    supportsSpeechRecognition,
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    abortListening,
  };
}

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
