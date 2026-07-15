import { ChevronDown } from "lucide-react";
import { GRADE_SCOPE_OPTIONS } from "@/lib/config";
import type { GradeScope } from "@/lib/types";

export function GradeScopePicker({
  value,
  onChange,
}: {
  value: GradeScope | null;
  onChange: (v: GradeScope | null) => void;
}) {
  return (
    <span className="relative inline-flex">
      <select
        aria-label="Grade scope"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : (e.target.value as GradeScope))}
        className="h-11 appearance-none rounded-lg border border-input bg-background pr-8 pl-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {GRADE_SCOPE_OPTIONS.map((opt) => (
          <option key={opt.label} value={opt.value ?? ""}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
    </span>
  );
}
