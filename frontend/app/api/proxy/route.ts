import { NextRequest, NextResponse } from "next/server";
import type { ChatRequestBody, ApiErrorBody } from "@/lib/types";

// Node runtime, not Edge: Edge functions have their own, shorter duration
// model. This route needs the fuller Node serverless-function budget below.
export const runtime = "nodejs";

// Vercel Hobby (fluid compute, default-on) allows up to 300s. Originally
// planned for ~60-80s worst case (cold Render free-tier start + a retried,
// judge-looped turn), but a real cold-boot measurement against the live
// deployment showed a first request after 15+ minutes idle can exceed 90s
// on its own before the container finishes booting — a second request
// right after still took ~60s to fully resolve. 170s gives real margin
// over the worst *measured* case, not just the originally estimated one.
export const maxDuration = 170;

// A few seconds under maxDuration so this handler can still return a
// clean JSON error itself, instead of Vercel hard-killing the function
// first and the browser seeing a bare connection failure.
const FETCH_TIMEOUT_MS = 150_000;

const BACKEND_URL = process.env.BACKEND_API_URL;
const BACKEND_API_KEY = process.env.BACKEND_API_KEY; // server-only: no NEXT_PUBLIC_ prefix

function isValidBody(body: unknown): body is ChatRequestBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  if (typeof b.association_id !== "string" || b.association_id.length === 0) return false;
  if (typeof b.thread_id !== "string" || b.thread_id.length === 0) return false;
  if (typeof b.question !== "string" || b.question.length === 0) return false;
  if (
    b.grade_scope !== undefined &&
    b.grade_scope !== null &&
    !["junior", "senior_men", "senior_women"].includes(b.grade_scope as string)
  ) {
    return false;
  }
  return true;
}

export async function POST(request: NextRequest) {
  if (!BACKEND_URL || !BACKEND_API_KEY) {
    console.error("proxy: BACKEND_API_URL or BACKEND_API_KEY env var is not set");
    return NextResponse.json<ApiErrorBody>({ detail: "Server misconfiguration." }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json<ApiErrorBody>({ detail: "Malformed JSON body." }, { status: 400 });
  }

  if (!isValidBody(body)) {
    return NextResponse.json<ApiErrorBody>(
      { detail: "association_id, thread_id, and question are all required, non-empty strings." },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const upstream = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": BACKEND_API_KEY,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const payload = await upstream.json().catch(() => null);

    if (!upstream.ok) {
      // Pass FastAPI's own {"detail": ...} shape straight through so the
      // client renders the real reason (401/404/422/500), not a generic one.
      return NextResponse.json<ApiErrorBody>(
        (payload as ApiErrorBody) ?? { detail: `Upstream error (status ${upstream.status}).` },
        { status: upstream.status },
      );
    }

    return NextResponse.json(payload, { status: 200 });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json<ApiErrorBody>(
        { detail: "The agent took too long to respond (timed out). Please try again." },
        { status: 504 },
      );
    }
    console.error("proxy: fetch to backend failed", err);
    return NextResponse.json<ApiErrorBody>(
      { detail: "Could not reach the agent service. Please try again." },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
