import type { Citation } from "@/lib/types";

export function CitationChip({ citation }: { citation: Citation }) {
  if (citation.type === "rule") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
        <span aria-hidden>📖</span>
        Section {citation.section_number} · {citation.document}
      </span>
    );
  }

  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-full border border-blue-300 bg-blue-50 px-2.5 py-1 text-xs text-blue-700 underline decoration-blue-400 underline-offset-2 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-300"
    >
      <span aria-hidden>🔗</span>
      {citation.url}
    </a>
  );
}
