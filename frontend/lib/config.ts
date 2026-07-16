import type { GradeScope } from "./types";

// Hardcoded for cert scope — the only association with real ingested data
// today. Production delta: fetch a real association list (and its
// grade_scope options) from Supabase once multi-association selection
// exists. Not built here.
export const ASSOCIATION = {
  id: "9b03694a-ebd4-4c4a-b378-52ab96b9abe6",
  label: "MYCA (Mid Year Cricket Association)",
} as const;

export const GRADE_SCOPE_OPTIONS: { value: GradeScope | null; label: string }[] = [
  { value: null, label: "All grades" },
  { value: "junior", label: "Junior" },
  { value: "senior_men", label: "Senior Men's" },
  { value: "senior_women", label: "Senior Women's" },
];

// Review banner hidden for now. needs_human_review, judge_reasoning, and
// arithmetic_ok still flow through the API response and component props
// untouched - this only gates whether ReviewBanner renders. Flip back to
// true to restore it.
export const SHOW_REVIEW_BANNER = false;
