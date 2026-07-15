import { BookOpen, ExternalLink } from "lucide-react";
import type { Citation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

export function CitationChip({ citation }: { citation: Citation }) {
  if (citation.type === "rule") {
    return (
      <Badge
        variant="secondary"
        className="h-auto min-h-7 max-w-full gap-1.5 rounded-md border-border/60 px-2.5 py-1 font-normal whitespace-normal text-secondary-foreground/90"
      >
        <BookOpen aria-hidden className="shrink-0 text-muted-foreground" />
        <span>
          Section {citation.section_number}
          {citation.document && <> · {citation.document}</>}
        </span>
      </Badge>
    );
  }

  return (
    <Badge
      asChild
      variant="outline"
      className="h-auto min-h-9 max-w-full gap-1.5 rounded-md border-blue-300 bg-blue-50 px-2.5 py-1 font-normal text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-300 dark:hover:bg-blue-950"
    >
      <a href={citation.url} target="_blank" rel="noopener noreferrer" title={citation.url}>
        <ExternalLink aria-hidden className="shrink-0" />
        <span className="truncate underline decoration-blue-400/70 underline-offset-2 dark:decoration-blue-500/70">
          {citation.url}
        </span>
      </a>
    </Badge>
  );
}
