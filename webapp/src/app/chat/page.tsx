"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import {
  sendMessageStream,
  listSessions,
  getSessionMessages,
  deleteSession,
  renameSession,
  type SessionInfo,
  type ChatMessage,
} from "@/lib/gateway";
import Sidebar from "./sidebar";

interface DisplayMessage {
  id: string;
  role: string;
  content: string;
  mode_used?: string | null;
  streaming?: boolean;
}

export default function ChatPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string>("");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"instant" | "thinking">("instant");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isStreamingRef = useRef(false);

  // Auth check
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setToken(session.access_token);
      setUserEmail(session.user.email || "");
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.replace("/login");
      } else {
        setToken(session.access_token);
      }
    });

    return () => subscription.unsubscribe();
  }, [router]);

  // Load sessions
  const loadSessions = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listSessions(token);
      setSessions(data.sessions);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  }, [token]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Load messages when active session changes
  useEffect(() => {
    if (!token || !activeSessionId) {
      setMessages([]);
      return;
    }

    // Don't reload from DB while streaming — the stream handler manages state
    if (isStreamingRef.current) return;

    async function loadMessages() {
      try {
        const msgs = await getSessionMessages(token!, activeSessionId!);
        setMessages(
          msgs.map((m: ChatMessage) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            mode_used: m.mode_used,
          }))
        );
      } catch (err) {
        console.error("Failed to load messages:", err);
      }
    }
    loadMessages();
  }, [token, activeSessionId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Send message
  async function handleSend() {
    if (!input.trim() || !token || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);

    // Add user message to display
    const userMsg: DisplayMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: userMessage,
    };

    // Add streaming placeholder
    const assistantMsg: DisplayMessage = {
      id: `stream-${Date.now()}`,
      role: "assistant",
      content: "",
      streaming: true,
      mode_used: mode,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    isStreamingRef.current = true;

    try {
      await sendMessageStream(
        token,
        userMessage,
        mode,
        activeSessionId || undefined,
        // onChunk
        (content) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.streaming ? { ...m, content } : m
            )
          );
        },
        // onSessionId
        (sid) => {
          setActiveSessionId(sid);
        }
      );

      // Mark as done streaming
      setMessages((prev) =>
        prev.map((m) => (m.streaming ? { ...m, streaming: false } : m))
      );

      // Refresh sessions
      loadSessions();
    } catch (err) {
      console.error("Send error:", err);
      setMessages((prev) =>
        prev.map((m) =>
          m.streaming
            ? {
                ...m,
                content: `error: ${err instanceof Error ? err.message : "connection failed"}`,
                streaming: false,
              }
            : m
        )
      );
    } finally {
      isStreamingRef.current = false;
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  // New chat
  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    inputRef.current?.focus();
  }

  // Delete session
  async function handleDeleteSession(id: string) {
    if (!token) return;
    try {
      await deleteSession(token, id);
      if (activeSessionId === id) {
        setActiveSessionId(null);
        setMessages([]);
      }
      loadSessions();
    } catch (err) {
      console.error("Delete error:", err);
    }
  }

  // Rename session
  async function handleRenameSession(id: string, title: string) {
    if (!token) return;
    try {
      await renameSession(token, id, title);
      loadSessions();
    } catch (err) {
      console.error("Rename error:", err);
    }
  }

  // Logout
  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.replace("/login");
  }

  // Handle key press
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glow">authenticating...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          onLogout={handleLogout}
          userEmail={userEmail}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Header */}
        <header className="border-b border-[#3a3a3a] px-4 py-2 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-[#77bb88] hover:text-[#00ff41] text-sm"
            >
              {sidebarOpen ? "[≡]" : "[≡]"}
            </button>
            <span className="text-xs text-[#77bb88]">
              {activeSessionId
                ? `session:${activeSessionId.slice(0, 8)}...`
                : "new_session"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {/* Mode toggle */}
            <button
              onClick={() =>
                setMode(mode === "instant" ? "thinking" : "instant")
              }
              className={`text-xs px-2 py-1 border transition-colors ${
                mode === "thinking"
                  ? "border-[#ff9900] text-[#ff9900] bg-[#ff9900]/10"
                  : "border-[#3a3a3a] text-[#77bb88] hover:border-[#77bb88]"
              }`}
            >
              {mode === "thinking" ? "[think]" : "[instant]"}
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-[#555555] space-y-2">
                <pre className="text-xs leading-tight">
{`
  ┌─────────────────────────┐
  │  ready for input...     │
  │                         │
  │  type a message below   │
  │  to start a session     │
  └─────────────────────────┘
`}
                </pre>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-[#0d1f0d] border border-[#00ff41]/20 text-[#00ff41]"
                    : "bg-[#111111] border border-[#3a3a3a] text-[#b0b0b0]"
                }`}
              >
                <div className="text-[10px] text-[#77bb88] mb-1">
                  {msg.role === "user" ? "> you" : "> ai"}
                  {msg.mode_used === "thinking" && " [think]"}
                </div>
                <div className="whitespace-pre-wrap break-words">
                  {msg.content}
                  {msg.streaming && (
                    <span className="inline-block w-2 h-4 bg-[#00ff41] ml-0.5 animate-pulse" />
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-[#3a3a3a] p-4 shrink-0">
          <div className="flex gap-2 items-end max-w-4xl mx-auto">
            <div className="text-[#77bb88] text-sm pt-2">{">"}</div>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="type your message..."
              rows={1}
              className="flex-1 bg-transparent text-[#00ff41] text-sm resize-none focus:outline-none placeholder-[#555555] min-h-[36px] max-h-[200px] py-2"
              style={{
                height: "auto",
                overflow: "hidden",
              }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = "auto";
                t.style.height = t.scrollHeight + "px";
              }}
              disabled={loading}
              autoFocus
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="text-sm px-3 py-2 border border-[#3a3a3a] text-[#77bb88] hover:border-[#00ff41] hover:text-[#00ff41] transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
            >
              {loading ? "[...]" : "[send]"}
            </button>
          </div>
          <div className="text-[10px] text-[#555555] mt-1 text-center">
            enter to send · shift+enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}
