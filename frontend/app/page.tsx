"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircleQuestion, RotateCcw, Send } from "lucide-react";
import { ASSOCIATION } from "@/lib/config";
import type { ApiErrorBody, ChatResponse, GradeScope, Turn } from "@/lib/types";
import { ChatMessage } from "@/components/ChatMessage";
import { GradeScopePicker } from "@/components/GradeScopePicker";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import { Button } from "@/components/ui/button";

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
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border px-4 py-3 md:px-8">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{ASSOCIATION.label}</h1>
          <p className="text-xs text-muted-foreground">Cricket rules assistant</p>
        </div>
        <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-end">
          <GradeScopePicker value={gradeScope} onChange={setGradeScope} />
          <Button
            type="button"
            variant="outline"
            onClick={handleNewConversation}
            className="h-11 gap-1.5 whitespace-nowrap rounded-lg px-3.5"
          >
            <RotateCcw aria-hidden />
            New conversation
          </Button>
        </div>
      </header>

      <main className="flex-1 space-y-4 overflow-y-auto px-4 py-4 md:px-8">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-muted">
              <MessageCircleQuestion aria-hidden className="size-6 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">
              Ask a question about {ASSOCIATION.label}&apos;s playing conditions.
            </p>
          </div>
        )}
        {turns.map((turn) => (
          <ChatMessage key={turn.id} turn={turn} />
        ))}
        {status !== "idle" && <ThinkingIndicator phase={status} />}
        <div ref={scrollRef} />
      </main>

      <form
        onSubmit={handleSubmit}
        className="sticky bottom-0 flex gap-2 border-t border-border bg-background/90 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur md:px-8"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a rules question…"
          disabled={status !== "idle"}
          className="h-12 flex-1 rounded-full border border-input bg-background px-4 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60"
        />
        <Button
          type="submit"
          disabled={status !== "idle" || !input.trim()}
          className="h-12 gap-1.5 rounded-full px-5"
        >
          <Send aria-hidden />
          Send
        </Button>
      </form>
    </div>
  );
}
