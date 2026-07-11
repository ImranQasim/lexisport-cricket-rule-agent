import type { Turn } from "@/lib/types";
import { CitationChip } from "./CitationChip";
import { ReviewBanner } from "./ReviewBanner";

export function ChatMessage({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2 text-sm text-white md:max-w-[70%] dark:bg-slate-100 dark:text-slate-900">
          {turn.question}
        </div>
      </div>
    );
  }

  if (turn.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 md:max-w-[70%] dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {turn.message}
        </div>
      </div>
    );
  }

  const { response } = turn;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-2 text-sm text-slate-900 md:max-w-[70%] dark:bg-slate-800 dark:text-slate-100">
        <div className="whitespace-pre-wrap">{response.answer}</div>

        {response.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {response.citations.map((c, i) => (
              <CitationChip key={i} citation={c} />
            ))}
          </div>
        )}

        {response.needs_human_review && (
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
