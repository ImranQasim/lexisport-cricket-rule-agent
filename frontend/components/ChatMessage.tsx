import { CircleAlert } from "lucide-react";
import { SHOW_REVIEW_BANNER } from "@/lib/config";
import { fixMisdecodedTiLigature } from "@/lib/utils";
import type { Turn } from "@/lib/types";
import { CitationChip } from "./CitationChip";
import { ReviewBanner } from "./ReviewBanner";

export function ChatMessage({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-sm md:max-w-[70%]">
          {turn.question}
        </div>
      </div>
    );
  }

  if (turn.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="flex max-w-[85%] items-start gap-2 rounded-2xl rounded-bl-md border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm leading-relaxed text-destructive md:max-w-[70%]">
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          {turn.message}
        </div>
      </div>
    );
  }

  const { response } = turn;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-4 py-3 text-sm leading-relaxed text-foreground shadow-sm md:max-w-[70%]">
        <div className="whitespace-pre-wrap">{fixMisdecodedTiLigature(response.answer)}</div>

        {response.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-2.5">
            {response.citations.map((c, i) => (
              <CitationChip key={i} citation={c} />
            ))}
          </div>
        )}

        {SHOW_REVIEW_BANNER && response.needs_human_review && (
          <ReviewBanner
            judgeReasoning={response.judge_reasoning}
            arithmeticOk={response.arithmetic_ok}
            flaggedClaims={response.flagged_claims}
            flaggedCitations={response.flagged_citations}
          />
        )}
      </div>
    </div>
  );
}
