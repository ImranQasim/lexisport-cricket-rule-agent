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
    <select
      aria-label="Grade scope"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : (e.target.value as GradeScope))}
      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
    >
      {GRADE_SCOPE_OPTIONS.map((opt) => (
        <option key={opt.label} value={opt.value ?? ""}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
