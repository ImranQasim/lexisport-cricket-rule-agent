import { Calculator, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">{title}</p>
      <ul className="ml-4 list-disc text-xs text-amber-800 dark:text-amber-300">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Mounted only when needs_human_review === true. Confirmed against
 * JUDGE_SYSTEM_PROMPT's own rule ("Return PASS only if ... no arithmetic
 * error"): a PASS structurally cannot carry arithmetic_ok === false, and
 * needs_human_review only becomes true via flag_and_finalize_node (post a
 * genuine FAIL or judge error) — so gating this whole banner, including
 * the arithmetic notice, on needs_human_review is provably sufficient.
 */
export function ReviewBanner({
  judgeReasoning,
  arithmeticOk,
  flaggedClaims,
  flaggedCitations,
}: {
  judgeReasoning: string | null;
  arithmeticOk: boolean | null;
  flaggedClaims: string[];
  flaggedCitations: string[];
}) {
  return (
    <Alert className="mt-3 border-amber-400/70 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/50 dark:text-amber-200">
      <TriangleAlert aria-hidden className="text-amber-600 dark:text-amber-400" />
      <AlertTitle className="text-sm font-semibold whitespace-normal text-amber-900 dark:text-amber-200">
        This answer could not be fully verified — please double-check before relying on it.
      </AlertTitle>
      <AlertDescription className="mt-1 space-y-2 text-amber-800 dark:text-amber-300">
        <ListSection title="Unsupported claims" items={flaggedClaims} />
        <ListSection title="Possibly fabricated citations" items={flaggedCitations} />
        {judgeReasoning && (
          <p className="border-l-2 border-amber-400/70 pl-2.5 text-xs italic dark:border-amber-500/50">
            Reviewer notes: {judgeReasoning}
          </p>
        )}
        {arithmeticOk === false && (
          <p className="flex items-start gap-1.5 text-xs font-semibold text-red-600 dark:text-red-400">
            <Calculator aria-hidden className="mt-0.5 size-3.5 shrink-0" />
            Arithmetic check failed — a calculation in this answer may be incorrect.
          </p>
        )}
        {/* arithmeticOk === null or true: no arithmetic-specific line — null
            means no arithmetic was present or the judge didn't run, and
            showing anything here would be a false "arithmetic failed" signal. */}
      </AlertDescription>
    </Alert>
  );
}
