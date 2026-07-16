"""Deterministic, non-LLM citation-provenance check for one agent turn.

Verifies that every citation in a draft answer -- "(Section X[, Document])"
for rule content, "(Source: URL)" for web content -- points at something
the tools actually retrieved this turn (backend.agent's search_rules_tool /
web_search_tool output, gathered the same way judge_node gathers it,
via _gather_turn_evidence).

This module deliberately does NOT verify that the cited chunk's text
actually supports the claim being made. A citation can be completely
real -- pointing at a chunk that genuinely was retrieved -- and still be
the wrong chunk for the question (a retrieval-relevance failure, not a
provenance failure). That semantic check is backend.agent's judge_node's
job. This module only answers "does this citation exist in what was
retrieved," never "is this citation relevant to the claim."

Known, documented residual gap in that provenance check itself, found
while measuring this against the real baseline run (89 real citations):
ingestion's chunking bundles multiple numbered sub-clauses under one
heading-level section_number tag (e.g. a chunk tagged "5.3 Hours of
play" whose body contains 5.3.1 through 5.3.7) in roughly half of the
two Senior documents' chunks. Models correctly cite the specific
sub-clause they relied on (e.g. "5.3.5"), which is finer than the
chunk's own tag -- 53 of 89 real citations were exactly this shape, so
this is matched deliberately (see _codes_match's dotted-prefix
containment) rather than treated as unverified. The residual risk this
opens, confirmed with a real (not hypothetical) example: eval-022 cited
"Section 5.3.4" for a claim that IS genuinely in a retrieved "5.3"
chunk (bowlers limited to one-fifth of overs remaining) -- but 5.3.4
does not exist in the source document at all (the numbering skips from
content ending near 5.3.3 straight to 5.3.5). The judge PASSed this
too, unflagged, the same shape of miss as eval-023. Dotted-prefix
containment matching verifies "5.3.4" against the retrieved "5.3" tag
just as it correctly verifies the other 51 genuine cases, and cannot
distinguish a real sub-clause number from an invented one within a
genuinely-retrieved parent section -- that would require checking the
cited number against the chunk's literal text, which is a semantic
check, not a provenance one, and stays out of scope here by the same
division of labor as eval-023.

One tuning round happened here, per the approved plan's failure-honesty
policy: the full golden-set VERIFY run surfaced 7 false fires on rows
clean at baseline, all traced to two concrete bugs (not vague
over-firing) plus one node-level evidence-gathering gap fixed in
backend.agent instead of here:
1. citation_check_node was reusing judge_node's then-gatherer (ToolMessage
   content only) -- but retry_retrieval_node
   injects its broadened-search results as a SystemMessage (retry
   bypasses ToolNode entirely). Every rule-citation false-fire had
   retry_count == 1: the check was evaluating the revised draft against
   stale, pre-retry evidence. Fixed in backend.agent via a dedicated
   gatherer including both message types (now _gather_turn_evidence,
   shared with judge_node since the 2026-07-16 judge fix).
2. The evidence-header regex (_RULE_HEADER_RE) used a lazy section
   group, which mis-split on section headings containing their own
   internal comma (e.g. "5.1 Naming of teams, the toss and commencement
   of play") -- landing on the first comma instead of the one separating
   section from document, garbling the document field so it could never
   match. Fixed by making the section group greedy and bounding the
   document group to non-comma characters (document names never contain
   one, verified against the actual ingested titles).
3. _codes_match's dotted-prefix guard originally required the *parent*
   code to itself contain a dot, to stop a bare "Section 5" from
   matching every "5.x" chunk -- but this also blocked the legitimate
   case of a bare top-level chapter heading like "15 Blood Rule" (real
   sub-clauses 15.1-15.6) matching a citation to "15.4". The "+ '.'"
   join anchor alone already provides the needed safety for that
   direction, so the extra guard was dropped there and kept only for
   the (unobserved in practice) opposite direction.
Re-verified after this round: 5 of 7 false-fire rows now pass cleanly.
The remaining 2 are not treated as a third tuning round -- one is an
already-accepted trade-off, the other a new, honestly-reported
limitation rather than a further patch, per the plan's own "more than
one tuning round becomes a finding, not an endless loop" discipline:
- eval-040: two real, correctly-retrieved sections ("Section 3.2.1,
  Doc A; Section 3.2.1, Doc B") joined in one parenthetical -- the same
  compound shape as eval-027, and this module deliberately refuses to
  auto-split it (see the unparseable-citation policy above) rather than
  guess at the split. Flagged as unverified even though both underlying
  facts are real -- an accepted cost of the conservative parsing choice,
  not a new bug.
- eval-045: cites "Section 11.8.6" which DOES exist verbatim in the
  retrieved evidence -- but as a sibling clause appended after "11.8.5
  Appeals Tribunal Members" in the same bundled chunk, not a
  dotted-prefix child of it ("11.8.6" doesn't start with "11.8.5.").
  _codes_match only recognizes parent-child containment, not adjacent
  siblings sharing one bundled chunk. Closing this would mean searching
  a candidate chunk's literal body text for the cited number rather than
  comparing structural section labels -- a real capability extension,
  not a normalization tweak, so left as a documented, known false-fire
  shape rather than patched here.

Separate from backend/api.py's own citation-extraction regex
(_RULE_CITATION_RE / _WEB_CITATION_RE), which is narrower and misses
citations built from long, descriptive section_number values (raw
document-heading text from ingestion/parse.py, not a controlled compact
code -- e.g. "LEVEL 4: IN-GAME ONFIELD SANCTIONS/PENALTIES" alongside
"5.3.5"). This module's draft-answer parser is anchored on the exact
document-name strings actually retrieved this turn (a small known set),
which recovers those cases; api.py's regex is intentionally left
untouched by this change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Trusted format -- our own f-string headers (agent.py: search_rules_tool,
# retry_retrieval_node, web_search_tool), not the model's free text.
# Section group is greedy (not lazy): real section_number values are raw
# document-heading text and sometimes contain their own internal comma
# (e.g. "5.1 Naming of teams, the toss and commencement of play"), which
# a lazy match would split on incorrectly. Document names never contain
# a comma (verified against the actual ingested titles), so bounding the
# document group to non-comma characters lets greedy backtracking land
# on the correct final split every time.
_RULE_HEADER_RE = re.compile(r"\[Section\s+(.+),\s*([^,\]]+),\s*similarity\s+[\d.]+\]")
_WEB_LINK_RE = re.compile(r"\]\((\S+?)\)")

# Untrusted format -- the model's own citation text. Handles both the
# prompt's asked-for "(Source: URL)" and an observed variant where the
# model wraps it as a markdown link, "(Source: [Title](URL))" -- the
# optional non-capturing group consumes the "[Title](" prefix if
# present, and the URL itself is bounded to non-paren characters so
# trailing ")"s (the link's own close, then the citation's) don't get
# swallowed into the captured URL.
_WEB_CITATION_RE = re.compile(r"\(Source:\s*(?:\[[^\]]*\]\()?(https?://[^\s)]+)\)+")

# Loose "does this look like an attempted citation" detectors, used only
# to notice when the precise parser below silently failed to read
# something -- see the module docstring's provenance-not-relevance split
# and the fail-toward-review policy on unparseable citations.
_SECTION_OPEN_RE = re.compile(r"\(Section\b")
_SOURCE_OPEN_RE = re.compile(r"\(Source:")

# One level of balanced parens (a lettered sub-clause like "3.5.2(B)",
# observed in production) is treated as a single atomic unit so it isn't
# split by its own closing paren; a bare comma always ends the section
# token so the following ", {document}" can be recognised.
_SECTION_TOKEN = r"(?:[^(),]|\([^()]*\))+"

# A generic-document fallback (same section-token handling, but the
# document half is only bounded by the closing paren, not anchored to a
# known retrieved document) -- used only for a "(Section" opener the
# anchored pattern didn't cover, so a citation naming a document that was
# never retrieved this turn at all still gets a precise, named
# unverified reason instead of falling into the generic "could not be
# parsed" bucket. Rejected if the captured "document" itself contains
# another embedded "Section ..." -- that's the signature of the real
# compound-citation format seen in production (two "Section X, Doc"
# clauses crammed into one parenthetical, joined by "; "), which is
# genuinely unparseable rather than a single citation naming an
# unretrieved document.
_GENERIC_RULE_CITATION_RE = re.compile(rf"\(Section\s+({_SECTION_TOKEN})(?:,\s*([^)]+))?\)")
_EMBEDDED_SECTION_RE = re.compile(r"\bSection\s+\S")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().casefold())


_LEADING_CODE_RE = re.compile(r"^([\w]+(?:\.[\w]+)*)")


def _leading_code(section: str) -> str | None:
    """The leading word/dot-separated code at the start of a section
    label -- "5.3" from "5.3 Hours of play", "J15" from "J15 OVERS",
    "5.3.5" from a citation naming that exact sub-clause. None for a
    label that doesn't start with one (rare; falls back to exact-label
    matching only)."""
    m = _LEADING_CODE_RE.match(section.strip())
    return m.group(1).casefold() if m else None


def _codes_match(cited_code: str | None, retrieved_code: str | None) -> bool:
    """Equal, or one is a dotted-prefix extension of the other (a
    numbered sub-clause nested under a bundled parent heading, in
    either direction).

    Citation-is-finer direction (the common real shape: a bundled parent
    heading is retrieved, the model cites a specific child clause) has
    no extra guard beyond the "+ '.'" join anchor -- that anchor alone
    already prevents "15" from matching "150.4", so requiring the
    *parent* code to itself be multi-level would incorrectly reject a
    real bare top-level chapter number like "15" (see "15 Blood Rule",
    whose real sub-clauses are 15.1-15.6 -- found live in VERIFY,
    eval-048, when the old stricter guard blocked this legitimate case).

    Citation-is-coarser direction (cites the general area, a more
    specific chunk was retrieved) keeps a guard requiring the *citation*
    itself to be at least two levels deep, so a bare single-token
    reference like "Section 5" can't match every "5.x" chunk -- this
    direction has zero observed instances in real data (see module
    docstring), so it's kept conservative rather than relaxed without
    evidence."""
    if not cited_code or not retrieved_code:
        return False
    if cited_code == retrieved_code:
        return True
    if cited_code.startswith(retrieved_code + "."):
        return True
    if "." in cited_code and retrieved_code.startswith(cited_code + "."):
        return True
    return False


@dataclass
class CitationCheckResult:
    verdict: str  # "PASS" | "FAIL"
    unverified_citations: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class _RetrievedRuleEntry:
    leading_code: str | None
    norm_section: str
    norm_doc: str


def _retrieved_rule_data(evidence_text: str) -> tuple[list[_RetrievedRuleEntry], list[str]]:
    """(one entry per retrieved rule chunk, raw document strings for
    regex anchoring)."""
    entries: list[_RetrievedRuleEntry] = []
    raw_docs: list[str] = []
    for section, doc in _RULE_HEADER_RE.findall(evidence_text):
        entries.append(
            _RetrievedRuleEntry(
                leading_code=_leading_code(section),
                norm_section=_normalize(section),
                norm_doc=_normalize(doc),
            )
        )
        raw_docs.append(doc.strip())
    return entries, raw_docs


def _retrieved_urls(evidence_text: str) -> set[str]:
    return {url.strip() for url in _WEB_LINK_RE.findall(evidence_text)}


def _build_rule_citation_re(known_docs: list[str]) -> re.Pattern:
    """Anchors the document half of a citation on the exact strings
    actually retrieved this turn (a small, known set) rather than a
    generic bounded-word regex. This is what lets the section half --
    often multi-word descriptive heading text in this corpus, not a
    compact code -- parse correctly instead of being cut short at the
    first space."""
    unique_docs = sorted(set(known_docs), key=len, reverse=True)
    doc_alt = "|".join(re.escape(d) for d in unique_docs) if unique_docs else "[^)]+"
    return re.compile(rf"\(Section\s+({_SECTION_TOKEN})(?:,\s*({doc_alt}))?\)")


def check_citations(draft_answer: str, evidence_text: str) -> CitationCheckResult:
    retrieved_entries, raw_docs = _retrieved_rule_data(evidence_text)
    retrieved_urls = _retrieved_urls(evidence_text)

    rule_pattern = _build_rule_citation_re(raw_docs)
    rule_matches = list(rule_pattern.finditer(draft_answer))
    covered_spans = [m.span() for m in rule_matches]

    # Anything the anchored pattern didn't cover: try the generic
    # fallback so "cites a document never retrieved this turn" gets a
    # precise reason rather than being lumped in with genuinely
    # unparseable text (see _GENERIC_RULE_CITATION_RE's docstring).
    for opener in _SECTION_OPEN_RE.finditer(draft_answer):
        pos = opener.start()
        if any(start <= pos < end for start, end in covered_spans):
            continue
        candidate = _GENERIC_RULE_CITATION_RE.match(draft_answer, pos)
        if candidate and candidate.group(2) and not _EMBEDDED_SECTION_RE.search(candidate.group(2)):
            rule_matches.append(candidate)
            covered_spans.append(candidate.span())

    web_matches = list(_WEB_CITATION_RE.finditer(draft_answer))

    unverified_citations: list[str] = []
    reasons: list[str] = []

    for match in rule_matches:
        section = match.group(1).strip()
        document = match.group(2).strip() if match.group(2) else None
        norm_section = _normalize(section)
        cited_code = _leading_code(section)

        if document is not None:
            norm_doc = _normalize(document)
            candidates = (e for e in retrieved_entries if e.norm_doc == norm_doc)
            label = f"Section {section}, {document}"
        else:
            # Bare citation: no document to check, so this only verifies
            # the section label exists in *some* retrieved chunk -- see
            # module docstring, this is a real limit the bare-citation
            # format itself creates.
            candidates = iter(retrieved_entries)
            label = f"Section {section}"

        ok = any(
            norm_section == e.norm_section or _codes_match(cited_code, e.leading_code) for e in candidates
        )
        if not ok:
            unverified_citations.append(label)
            reasons.append(f"citation not in retrieved context: {label}")

    for match in web_matches:
        url = match.group(1).strip()
        if url not in retrieved_urls:
            label = f"Source: {url}"
            unverified_citations.append(label)
            reasons.append(f"citation not in retrieved context: {label}")

    detected_rule_opens = len(_SECTION_OPEN_RE.findall(draft_answer))
    detected_source_opens = len(_SOURCE_OPEN_RE.findall(draft_answer))
    if detected_rule_opens > len(rule_matches) or detected_source_opens > len(web_matches):
        unverified_citations.append("citation present but could not be parsed cleanly")
        reasons.append("citation could not be parsed")

    if not reasons:
        return CitationCheckResult(
            verdict="PASS",
            unverified_citations=[],
            reason="all citations verified against retrieved context this turn",
        )

    return CitationCheckResult(verdict="FAIL", unverified_citations=unverified_citations, reason="; ".join(reasons))
