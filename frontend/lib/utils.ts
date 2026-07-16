import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Ingestion's PDF text extraction mis-decodes the "ti" ligature glyph as
// U+01A6 for some source documents (e.g. "playing Ɵme"). Display-only
// patch — the underlying stored chunk text and embeddings are unaffected.
export function fixMisdecodedTiLigature(text: string): string {
  return text.replace(/Ɵ/g, "ti")
}
