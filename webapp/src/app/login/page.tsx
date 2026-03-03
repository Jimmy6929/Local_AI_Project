"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const supabase = createClient();

    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        // For local Supabase, auto-confirm is usually on
        const { error: loginError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (loginError) throw loginError;
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
      }
      router.push("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* ASCII art header */}
        <pre className="text-[#00ff41] text-xs mb-8 text-center leading-tight select-none">
{`
 ╔═══════════════════════════╗
 ║   LOCAL AI ASSISTANT      ║
 ║   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   ║
 ║   private · fast · yours  ║
 ╚═══════════════════════════╝
`}
        </pre>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-[#77bb88] mb-1">
              {"> email"}
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-[#00ff41] px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#00ff41] transition-colors"
              placeholder="user@example.com"
              required
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs text-[#77bb88] mb-1">
              {"> password"}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-[#00ff41] px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#00ff41] transition-colors"
              placeholder="••••••••"
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="text-[#ff3333] text-xs border border-[#ff3333]/30 bg-[#ff3333]/5 px-3 py-2">
              error: {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full border border-[#00ff41] text-[#00ff41] py-2 text-sm font-mono hover:bg-[#00ff41]/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? "connecting..."
              : isSignUp
              ? "[create_account]"
              : "[login]"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError("");
            }}
            className="text-xs text-[#77bb88] hover:text-[#00ff41] transition-colors"
          >
            {isSignUp
              ? "// already have an account? login"
              : "// need an account? sign up"}
          </button>
        </div>

        <div className="mt-8 text-center text-xs text-[#555555]">
          v0.1.0 · all data stays local
        </div>
      </div>
    </div>
  );
}
