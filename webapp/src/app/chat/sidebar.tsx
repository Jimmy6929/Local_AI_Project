"use client";

import { useState, useRef, useEffect } from "react";
import { type SessionInfo } from "@/lib/gateway";

interface SidebarProps {
  sessions: SessionInfo[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  onLogout: () => void;
  userEmail: string;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onLogout,
  userEmail,
}: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingId]);

  function timeAgo(dateStr: string): string {
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  function startRename(s: SessionInfo) {
    setEditingId(s.id);
    setEditTitle(s.title);
  }

  function commitRename() {
    if (editingId && editTitle.trim()) {
      onRenameSession(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle("");
  }

  function cancelRename() {
    setEditingId(null);
    setEditTitle("");
  }

  return (
    <div className="w-64 border-r border-[#3a3a3a] flex flex-col min-h-screen bg-[#080808]">
      {/* Header */}
      <div className="p-3 border-b border-[#3a3a3a]">
        <div className="text-xs text-[#00ff41] glow font-bold">
          LOCAL_AI v0.1
        </div>
      </div>

      {/* New Chat */}
      <div className="p-2">
        <button
          onClick={onNewChat}
          className="w-full text-left text-xs px-2 py-2 border border-dashed border-[#3a3a3a] text-[#77bb88] hover:border-[#00ff41] hover:text-[#00ff41] transition-colors"
        >
          + new_session
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {sessions.length === 0 && (
          <div className="text-[10px] text-[#555555] p-2 text-center">
            no sessions yet
          </div>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group flex items-center text-xs cursor-pointer transition-colors ${
              activeSessionId === s.id
                ? "bg-[#0d1f0d] border border-[#00ff41]/30 text-[#00ff41]"
                : "border border-transparent text-[#77bb88] hover:text-[#00ff41] hover:bg-[#111111]"
            }`}
          >
            {editingId === s.id ? (
              <div className="flex-1 px-2 py-1.5">
                <input
                  ref={editInputRef}
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename();
                    if (e.key === "Escape") cancelRename();
                  }}
                  onBlur={commitRename}
                  className="w-full bg-[#0a0a0a] border border-[#00ff41] text-[#00ff41] px-1 py-0.5 text-xs font-mono focus:outline-none"
                  maxLength={200}
                />
                <div className="text-[10px] text-[#555555] mt-0.5">
                  enter to save · esc to cancel
                </div>
              </div>
            ) : (
              <button
                onClick={() => onSelectSession(s.id)}
                onDoubleClick={() => startRename(s)}
                className="flex-1 text-left px-2 py-2 min-w-0"
              >
                <div className="truncate">{s.title || "untitled"}</div>
                <div className="text-[10px] text-[#555555] mt-0.5">
                  {timeAgo(s.updated_at)}
                </div>
              </button>
            )}
            {editingId !== s.id && (
              <div className="flex opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(s);
                  }}
                  className="px-1 text-[#555555] hover:text-[#00ff41]"
                  title="rename session"
                >
                  [r]
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(s.id);
                  }}
                  className="px-1 text-[#555555] hover:text-[#ff3333]"
                  title="delete session"
                >
                  [x]
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* User Info */}
      <div className="border-t border-[#3a3a3a] p-3 space-y-2">
        <div className="text-[10px] text-[#555555] truncate">
          {userEmail}
        </div>
        <button
          onClick={onLogout}
          className="text-[10px] text-[#77bb88] hover:text-[#ff3333] transition-colors"
        >
          [logout]
        </button>
      </div>
    </div>
  );
}
