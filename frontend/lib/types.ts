/**
 * TypeScript mirror of backend/api.py's Pydantic models. Keep in sync by
 * hand — there is no shared schema generation in this project.
 */

export type GradeScope = "junior" | "senior_men" | "senior_women";

export interface ChatRequestBody {
  association_id: string;
  thread_id: string;
  question: string;
  grade_scope?: GradeScope | null;
}

export interface RuleCitation {
  type: "rule";
  section_number: string;
  document: string;
}

export interface WebCitation {
  type: "web";
  url: string;
}

export type Citation = RuleCitation | WebCitation;

export interface ChatResponse {
  thread_id: string;
  answer: string;
  citations: Citation[];
  needs_human_review: boolean;
  flagged_claims: string[];
  flagged_citations: string[];
  // Item zero: always populated from the last judge call this turn,
  // regardless of PASS/FAIL. Null only when the judge was skipped
  // (a greeting never reaches judge_node).
  judge_reasoning: string | null;
  arithmetic_ok: boolean | null;
}

// FastAPI's 422 Pydantic validation error shape.
export interface ValidationErrorDetail {
  type: string;
  loc: (string | number)[];
  msg: string;
  [key: string]: unknown;
}

// The shape of every non-2xx JSON body the backend (or the proxy itself) returns.
export interface ApiErrorBody {
  detail: string | ValidationErrorDetail[];
}

// One turn in the visible chat transcript. A "user" turn is the question
// as typed; "assistant" carries the full ChatResponse (citations, review
// flag, judge_reasoning, arithmetic_ok all render from it); "error" is a
// client- or proxy-side failure rendered inline, never a silent drop.
export interface UserTurn {
  id: string;
  role: "user";
  question: string;
}

export interface AssistantTurn {
  id: string;
  role: "assistant";
  response: ChatResponse;
}

export interface ErrorTurn {
  id: string;
  role: "error";
  message: string;
}

export type Turn = UserTurn | AssistantTurn | ErrorTurn;
