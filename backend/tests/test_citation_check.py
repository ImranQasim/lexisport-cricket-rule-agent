"""Unit tests for backend.citations.check_citations -- the mechanical,
deterministic citation-provenance check. No graph, no LLM: these test
the parser and matcher directly against evidence-text/draft-answer
string pairs shaped exactly like what backend/agent.py's tools produce
(see agent.py:150, agent.py:186, agent.py:294 for the real formats).

Written before backend/agent.py integration, per the approved plan's
EXECUTE order.
"""

from __future__ import annotations

from backend.citations import check_citations

SENIOR_MEN = "MYCA Senior Men's Playing Rules v2"
SENIOR_WOMEN = "MYCA Senior Women's Playing Rules v1"


def _evidence(*blocks: str) -> str:
    return "--- From search_rules_tool ---\n" + "\n\n".join(blocks)


def test_full_format_citation_matches_retrieved_chunk_passes():
    evidence = _evidence(
        f"[Section 5.3.5, {SENIOR_WOMEN}, similarity 0.72]\n"
        "5.3.5 If the team bowling second fails to bowl the minimum overs required, "
        "12 penalty runs per over shall be awarded to the batting team."
    )
    draft = f"You are owed 36 penalty runs (Section 5.3.5, {SENIOR_WOMEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_bare_citation_matches_retrieved_section_any_document_passes():
    # Documented limitation: a bare citation (no document named) can only
    # be checked against the section label, not the right document -- see
    # backend/citations.py's own docstring for why.
    evidence = _evidence(
        f"[Section 3.3.2, {SENIOR_MEN}, similarity 0.65]\n"
        "3.3.2 Deduct overs per the time-lost table."
    )
    draft = "Deduct 2 overs for the late start (Section 3.3.2)."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_misattributed_citation_wrong_document_for_real_section_fails():
    # Both documents are genuinely retrieved this turn (so both are known,
    # anchorable document strings), but 5.6 only exists in the Men's
    # chunk -- the draft attributes it to the Women's document instead.
    evidence = _evidence(
        f"[Section 5.6, {SENIOR_MEN}, similarity 0.55]\n"
        "5.6.1 The team scoring more runs on first innings wins.",
        f"[Section 5.8.1, {SENIOR_WOMEN}, similarity 0.50]\n"
        "5.8.1.1 Finals are determined by ladder position.",
    )
    draft = f"The team scoring more runs wins (Section 5.6, {SENIOR_WOMEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"
    assert any("5.6" in c for c in result.unverified_citations)


def test_invented_section_not_in_any_retrieved_chunk_fails():
    evidence = _evidence(
        f"[Section 5.3.5, {SENIOR_WOMEN}, similarity 0.72]\n"
        "5.3.5 12 penalty runs per over shall be awarded to the batting team."
    )
    draft = f"There is no Super Over (Section 5.8.5, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"
    assert any("5.8.5" in c for c in result.unverified_citations)


def test_unparseable_compound_citation_fails_toward_review():
    # The real eval-027 shape: two "Section X, Doc" clauses crammed into
    # one parenthetical, joined by "; " rather than being two separate
    # citations. The second "Section" has no preceding "(", so the
    # precise parser can't cleanly split it -- and shouldn't guess.
    evidence = _evidence(
        f"[Section 5.6, {SENIOR_MEN}, similarity 0.50]\n5.6.1 Match result rule.",
        f"[Section 5.8.1, {SENIOR_WOMEN}, similarity 0.49]\n5.8.1.1 Finals rule.",
    )
    draft = (
        "The higher-ladder team wins the tie "
        f"(Section 5.8.5, {SENIOR_MEN}; Section 5.8.5, {SENIOR_WOMEN})."
    )

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"
    assert "parse" in result.reason.lower()


def test_nested_paren_subclause_citation_parses_and_matches_passes():
    evidence = _evidence(
        f"[Section 3.5.2(B), {SENIOR_MEN}, similarity 0.60]\n"
        "3.5.2(B) Late forfeit fine is $200 plus umpire fees."
    )
    draft = f"The fine is $200 plus umpire fees (Section 3.5.2(B), {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_web_citation_url_match_passes():
    evidence = (
        "--- From web_search_tool ---\n"
        "[Weather forecast for Saturday](https://weather.example.com/forecast)\n"
        "Partly cloudy, 20% chance of rain."
    )
    draft = "Expect partly cloudy conditions (Source: https://weather.example.com/forecast)."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_web_citation_url_mismatch_fails():
    evidence = (
        "--- From web_search_tool ---\n"
        "[Weather forecast for Saturday](https://weather.example.com/forecast)\n"
        "Partly cloudy, 20% chance of rain."
    )
    draft = "Expect partly cloudy conditions (Source: https://not-retrieved.example.com)."

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"
    assert any("not-retrieved.example.com" in c for c in result.unverified_citations)


def test_web_citation_nested_markdown_link_format_passes():
    # Real production shape (eval-010, full golden-set VERIFY run): the
    # model sometimes wraps the URL as a markdown link inside the Source
    # parenthetical, "(Source: [Title](URL))", instead of the prompt's
    # asked-for bare "(Source: URL)".
    evidence = (
        "--- From web_search_tool ---\n"
        "[Weather in home ground](https://www.weatherapi.com/)\n"
        "8% chance of rain Saturday."
    )
    draft = "It's unlikely to rain Saturday (Source: [WeatherAPI](https://www.weatherapi.com/))."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_same_leading_code_different_heading_suffix_passes():
    # The most common real shape (27/89 in the baseline run): the chunk's
    # section_number is a full heading ("J15 OVERS"), the model cites
    # just the leading code ("J15"). Exact full-label match alone would
    # false-fire on this constantly.
    evidence = _evidence(
        "[Section J15 OVERS, MYCA Junior Playing Rules v1, similarity 0.68]\n"
        "An over ends at 6 legal deliveries or 8 total, whichever comes first."
    )
    draft = "The over ends at whichever comes first (Section J15, MYCA Junior Playing Rules v1)."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_finer_subclause_under_bundled_heading_passes():
    # The second most common real shape (53/89 in the baseline run):
    # ingestion bundles multiple numbered sub-clauses under one
    # heading-level section_number tag, and the model correctly cites
    # the specific sub-clause it relied on -- see module docstring.
    evidence = _evidence(
        f"[Section 5.3 Hours of play, {SENIOR_MEN}, similarity 0.50]\n"
        "5.3.1 Matches commence at 12pm.\n\n"
        "5.3.5 If fielding side fails to bowl the minimum overs, 12 penalty runs per over are awarded."
    )
    draft = f"12 penalty runs per over (Section 5.3.5, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_coarser_citation_against_finer_retrieved_tag_passes():
    evidence = _evidence(f"[Section 5.3.5, {SENIOR_MEN}, similarity 0.50]\n5.3.5 12 penalty runs per over.")
    draft = f"See the hours-of-play rules (Section 5.3, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_bare_top_level_chapter_heading_with_real_subclause_passes():
    # Real production shape (eval-048, full golden-set VERIFY run): a
    # bare, single-token chapter heading ("15 Blood Rule") bundling real
    # sub-clauses 15.1-15.6. The dotted-prefix "+ '.'" join anchor alone
    # is enough to safely match "15.4" against retrieved "15" -- no
    # extra guard needed on this (citation-is-finer) direction.
    evidence = _evidence(
        f"[Section 15 Blood Rule, {SENIOR_MEN}, similarity 0.56]\n"
        "15.1 Where a player or umpire suffers an injury...\n\n"
        "15.4 The player must leave the field for treatment."
    )
    draft = f"The player must leave the field (Section 15.4, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_section_heading_with_internal_comma_still_matches_document():
    # Real production shape (eval-040/eval-045, full golden-set VERIFY
    # run): the retrieved chunk's own section_number contains a comma
    # ("5.1 Naming of teams, the toss and commencement of play"). A lazy
    # section-group regex mis-splits this, garbling the document field
    # so it can never match -- see _RULE_HEADER_RE's docstring.
    evidence = _evidence(
        f"[Section 5.1 Naming of teams, the toss and commencement of play, {SENIOR_MEN}, similarity 0.59]\n"
        "5.1.1 Teams may name up to 12 players prior to the toss."
    )
    draft = f"Teams may name up to 12 players (Section 5.1.1, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []


def test_bare_top_level_code_does_not_match_every_subsection():
    # Guard against the over-broad case: a bare, single-token citation
    # like "Section 5" (no dot) must not verify against every "5.x"
    # chunk just because it's a string prefix.
    evidence = _evidence(f"[Section 5.3.5, {SENIOR_MEN}, similarity 0.50]\n5.3.5 12 penalty runs per over.")
    draft = f"See the general rules (Section 5, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"


def test_known_gap_invented_subclause_under_real_bundled_heading_is_not_caught():
    # Documents a real, observed limitation (eval-022), not a bug: a
    # fabricated specific sub-clause number under a genuinely-retrieved
    # bundled heading passes provenance, because dotted-prefix
    # containment can't distinguish a real sub-clause from an invented
    # one without reading the chunk's literal text -- a semantic check,
    # out of scope here (see module docstring). This stays the judge's
    # residual responsibility, the same division of labor as eval-023.
    evidence = _evidence(
        f"[Section 5.3 Hours of play, {SENIOR_MEN}, similarity 0.50]\n"
        "5.3.1 Matches commence at 12pm.\n\n"
        "5.3.3 Bowlers are limited to a maximum of one fifth of the overs remaining.\n\n"
        "5.3.5 If fielding side fails to bowl the minimum overs, 12 penalty runs per over are awarded."
    )
    # 5.3.4 does not exist in this document at all -- the real eval-022 shape.
    draft = f"A bowler can bowl one-fifth of the overs remaining (Section 5.3.4, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"  # known gap, not a target for this check to close


def test_known_gap_sibling_clause_in_bundled_chunk_is_not_matched():
    # Documents a second real, observed limitation (eval-045, full
    # golden-set VERIFY run), distinct from the invented-subclause gap
    # above: "11.8.6" genuinely exists verbatim in the retrieved
    # evidence, but as a SIBLING clause appended after "11.8.5 Appeals
    # Tribunal Members" in the same bundled chunk, not a dotted-prefix
    # CHILD of it. _codes_match only recognizes parent-child
    # containment ("11.8.6".startswith("11.8.5.") is False -- they share
    # a parent, "11.8", but neither extends the other). Closing this
    # would mean searching a chunk's literal body text for the cited
    # number rather than comparing structural section labels -- a real
    # capability extension, left as a documented false-fire shape rather
    # than patched in this tuning round (see module docstring).
    evidence = _evidence(
        f"[Section 11.8.5 Appeals Tribunal Members, {SENIOR_MEN}, similarity 0.60]\n"
        "11.8.5.1 MYCA secretary will organize a minimum of 3 Independent Panel members.\n\n"
        "11.8.6 Any player under suspension or disqualification is not permitted on the field."
    )
    draft = f"Players under suspension are not permitted on the field (Section 11.8.6, {SENIOR_MEN})."

    result = check_citations(draft, evidence)

    assert result.verdict == "FAIL"  # known false-fire shape, not fixed in this round


def test_no_citations_present_passes_trivially():
    evidence = _evidence(
        f"[Section 5.3.5, {SENIOR_WOMEN}, similarity 0.72]\n"
        "5.3.5 12 penalty runs per over shall be awarded to the batting team."
    )
    draft = "I could not find an answer to this in the rules or in any web results."

    result = check_citations(draft, evidence)

    assert result.verdict == "PASS"
    assert result.unverified_citations == []
