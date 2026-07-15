import { ShieldCheck } from "lucide-react";

export function ThinkingIndicator({ phase }: { phase: "thinking" | "verifying" }) {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2.5 rounded-2xl rounded-bl-md bg-muted px-4 py-3 text-sm text-muted-foreground">
        {phase === "thinking" ? (
          <>
            <span className="flex gap-1" aria-hidden>
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.3s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.15s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70" />
            </span>
            Thinking…
          </>
        ) : (
          <>
            <ShieldCheck aria-hidden className="size-4 animate-pulse text-muted-foreground/80" />
            Verifying answer…
          </>
        )}
      </div>
    </div>
  );
}
