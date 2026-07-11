"use client";

import { useEffect, useRef, useState } from "react";
import { ASSOCIATION } from "@/lib/config";
import type { ApiErrorBody, ChatResponse, GradeScope, Turn } from "@/lib/types";
import { ChatMessage } from "@/components/ChatMessage";
import { GradeScopePicker } from "@/components/GradeScopePicker";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";

type Status = "idle" | "thinking" | "verifying";

const THREAD_ID_KEY = "lexisport:thread_id";
// A few seconds past the proxy's own maxDuration (170s — see route.ts for
// why this is higher than originally planned, based on a real cold-boot
// measurement), so the browser's own fetch always eventually resolves to
// an error even in the edge case where Vercel hard-kills the function
// without the client ever seeing a response — this is what actually
// guarantees "never a permanently hung spinner," not the server-side
// timeout alone.
const CLIENT_FETCH_TIMEOUT_MS = 190_000;
const VERIFYING_COPY_DELAY_MS = 8_000;

// thread_id lifecycle: sessionStorage, not React state alone (lost on
// refresh) and not localStorage (would outlive the tab, contradicting
// "current session only, no permanent history"). A lazy useState
// initializer reads it once on mount — the SSR pass has no `window`, so it
// falls back to "" there; the client's first render replaces it with the
// real value before anything ever reads threadId (it's only used inside
// handleSubmit, never rendered into DOM), so there's nothing to mismatch.
function initThreadId(): string {
  if (typeof window === "undefined") return "";
  const existing = sessionStorage.getItem(THREAD_ID_KEY);
  if (existing) return existing;
  const fresh = crypto.randomUUID();
  sessionStorage.setItem(THREAD_ID_KEY, fresh);
  return fresh;
}

export default function Page() {
  const [threadId, setThreadId] = useState<string>(initThreadId);
  const [gradeScope, setGradeScope] = useState<GradeScope | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const verifyingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, status]);

  function handleNewConversation() {
    if (verifyingTimerRef.current) clearTimeout(verifyingTimerRef.current);
    const fresh = crypto.randomUUID();
    sessionStorage.setItem(THREAD_ID_KEY, fresh);
    setThreadId(fresh);
    setTurns([]);
    setStatus("idle");
    // No DELETE/reset call to the backend: its memory is keyed purely by
    // thread_id, so a fresh id is a fresh conversation with no server call needed.
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || status !== "idle" || !threadId) return;

    setTurns((prev) => [...prev, { id: crypto.randomUUID(), role: "user", question }]);
    setInput("");
    setStatus("thinking");

    verifyingTimerRef.current = setTimeout(() => setStatus("verifying"), VERIFYING_COPY_DELAY_MS);

    const controller = new AbortController();
    const clientTimeoutId = setTimeout(() => controller.abort(), CLIENT_FETCH_TIMEOUT_MS);

    try {
      const res = await fetch("/api/proxy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          association_id: ASSOCIATION.id,
          thread_id: threadId,
          question,
          grade_scope: gradeScope,
        }),
        signal: controller.signal,
      });

      const payload = await res.json().catch(() => null);

      if (!res.ok) {
        const detail = (payload as ApiErrorBody | null)?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((d) => d.msg).join("; ")
              : "Something went wrong. Please try again.";
        setTurns((prev) => [...prev, { id: crypto.randomUUID(), role: "error", message }]);
      } else {
        setTurns((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", response: payload as ChatResponse },
        ]);
      }
    } catch {
      setTurns((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "error", message: "Network error or timeout. Please try again." },
      ]);
    } finally {
      clearTimeout(clientTimeoutId);
      if (verifyingTimerRef.current) clearTimeout(verifyingTimerRef.current);
      setStatus("idle");
    }
  }

  return (
    <div className="mx-auto flex h-dvh w-full flex-col md:max-w-2xl">
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 md:px-8 dark:border-slate-800">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{ASSOCIATION.label}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">Cricket rules assistant</p>
        </div>
        <div className="flex items-center gap-2">
          <GradeScopePicker value={gradeScope} onChange={setGradeScope} />
          <button
            type="button"
            onClick={handleNewConversation}
            className="whitespace-nowrap rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            New conversation
          </button>
        </div>
      </header>

      <main className="flex-1 space-y-3 overflow-y-auto px-4 py-4 md:px-8">
        {turns.length === 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Ask a question about {ASSOCIATION.label}&apos;s playing conditions.
          </p>
        )}
        {turns.map((turn) => (
          <ChatMessage key={turn.id} turn={turn} />
        ))}
        {status !== "idle" && <ThinkingIndicator phase={status} />}
        <div ref={scrollRef} />
      </main>

      <form
        onSubmit={handleSubmit}
        className="sticky bottom-0 flex gap-2 border-t border-slate-200 bg-white px-4 py-3 md:px-8 dark:border-slate-800 dark:bg-slate-950"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a rules question…"
          disabled={status !== "idle"}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
        <button
          type="submit"
          disabled={status !== "idle" || !input.trim()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
        >
          Send
        </button>
      </form>
    </div>
  );
}
