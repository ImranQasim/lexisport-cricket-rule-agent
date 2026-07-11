# Submission

## Problem

Umpires, captains, and officials at local cricket associations need to combine detailed, association-specific and format-specific playing conditions and by-laws, written as individual rule statements rather than worked scenarios, into a correct ruling in the moment during a live match, but today they can only rely on memory from occasional training, dense PDF rule documents that are hard to consult on a phone, and ad hoc calls to a match-day contact, which leads to inconsistent or wrong rulings under pressure.

## Why this is a problem

I umpire local cricket myself, and the people who carry this problem are umpires first, then the captains and club officials who lean on them for a ruling. An umpire on the field has to apply the correct playing conditions for that specific association and that specific format, senior, junior, or women's, and often has to combine two or three separate rule clauses into one ruling on the spot. A junior over might end at six legal balls or eight balls in total, whichever comes first, and the documents never spell out what happens if the eighth ball is a no-ball and a free hit is owed. A time-lost calculation after a late start has to be combined with an over-rate penalty later in the same innings. None of this is answered by reading one rule on its own.

Right now the only preparation umpires get is a handful of training meetings a year and weekly notes from the association's umpire development officer, and none of it is scenario based, it is general reminders. Detailed situations like rain rules get handed out as printed sheets that nobody can memorize, and when an umpire needs to check something mid match, the rule documents are dense PDFs that are hard to read on a phone, especially for older umpires who rarely carry a laptop to the ground. The fallback is a phone call to whoever is the match-day contact that day. I have watched this go wrong in front of me. At a senior MYCA match, play started six minutes late, which should have meant one over off each side. The bowling side then ran over time and should have lost a further over for slow over rate on top of that. Both captains argued opposite interpretations, the umpire had no way to check the actual rule in the moment, and the ruling that came out was wrong. The calculation itself is simple. Getting it right under live pressure with only memory and a phone call to fall back on is not.

## Solution

I am building an AI assistant that answers umpires, captains, and officials from the rule documents of whichever cricket association they are working with, with citations to the specific document and section, and an honest fallback when a question falls outside those documents.

## Infrastructure

```mermaid
flowchart TD
    User([User on phone or laptop browser])

    subgraph Vercel["Vercel"]
        FE[Next.js responsive frontend]
    end

    subgraph Render["Render (always-on)"]
        API[FastAPI agent API]
        Gateway[LiteLLM proxy gateway]
        subgraph Agent["LangGraph agent"]
            Route{Tool choice}
            Rules[search_rules tool]
            Web[Tavily web search tool]
            Gen[Generate cited answer]
            Judge{Judge: grounded?}
            Review[Human review flag]
        end
    end

    subgraph Supabase["Supabase (one project)"]
        SQL[(Structured tables: countries, cities, associations)]
        Vec[(pgvector: rule chunks tagged by association_id)]
        Bucket[(Storage: raw rule PDFs)]
        Mem[(LangGraph checkpointer: conversation memory)]
        Auth[Supabase Auth]
    end

    OpenAI[gpt-4o-mini + text-embedding-3-small]
    Tavily[Tavily API]
    LS[LangSmith: traces, cost, evals]
    CI[GitHub Actions: Ragas eval gate]

    User --> FE --> API
    API --> Auth
    API --> Agent
    Route --> Rules --> Vec
    Route --> Web --> Tavily
    Rules --> Gen
    Web --> Gen
    Gen --> Judge
    Judge -->|low confidence| Review
    Agent <--> Mem
    Agent --> Gateway --> OpenAI
    Bucket -. ingestion pipeline .-> Vec
    API -. traces .-> LS
    CI -. runs golden set .-> Agent
```

### Why each component

1. **LLM: gpt-4o-mini** - cheap enough to serve as both generator and judge, and it is the model I have used all cohort, so its behavior with my prompts and evals is a known quantity.
2. **Agent orchestration: LangGraph** - the judge-retry loop, honest fallback, and human review path need an explicit graph with state, not a linear chain.
3. **Tools: search_rules + Tavily** - search_rules retrieves rule chunks hard-filtered by association_id so the agent can only see the right association's rules, and Tavily covers current public questions the rule documents cannot answer.
4. **Embedding model: text-embedding-3-small** - cheap, proven in my earlier retrieval work, and low lock-in since swapping later only costs re-embedding the corpus.
5. **Vector database: Supabase pgvector** - vectors live in the same Postgres as my existing association tables, so one foreign key joins structured data, chunks, and files with no second database to run or pay for.
6. **Monitoring: LangSmith** - every agent run is traced with latency, token cost, and judge score, which is how I debug retrieval instead of guessing.
7. **Evaluation framework: Ragas + GitHub Actions** - Ragas scores faithfulness, context precision, context recall, and answer relevance against a golden set, and a CI gate fails any change that drops faithfulness below baseline.
8. **User interface: Next.js on Vercel** - a responsive web app satisfies the phone-and-laptop browser requirement with one codebase.
9. **Deployment: Render + Vercel** - the agent API and gateway run always-on on Render so there are no cold starts, and Vercel serves the frontend from its free tier.
10. **LLM gateway: LiteLLM proxy** - run as a service, not an SDK import, it gives every model call retries, fallbacks, budget caps, and one place where all traffic is logged.
11. **Memory: LangGraph Postgres checkpointer** - conversation state persists in Supabase keyed by thread id, so follow-up questions resolve against prior turns.
12. **Auth: Supabase Auth** - the API verifies the JWT the platform already issues, reusing existing auth instead of building any.
13. **File storage: Supabase Storage** - raw rule PDFs live in a bucket keyed by association_id, kept for re-ingestion and document versioning.

## Evaluation questions

| # | Question | Expected answer | Source | Actual baseline answer | Result |
|---|----------|------------------|--------|-------------------------|--------|
| 1 | Umpire: "We started 6 minutes late today, batting side reckons they should still get the full 35 overs. What do I actually give them?" | Deduct overs for time lost at MYCA's rate of 1 over per 4 minutes lost, so 6 minutes lost means 1 over off, 34 overs allowed. If the bowling side then goes over its allotted time for those 34 overs, apply a separate over-rate deduction on top of the time-lost deduction. | MYCA Senior Playing Conditions | Identified the correct rule, 3.3.2, but could not state a number because the lookup table it points to was not retrieved. | Partial, see Baseline Evaluation Findings |
| 2 | Umpire: "In U13 does the over end at 6 balls or 8 balls, and what if most of those extra balls are wides?" | The over ends at whichever limit is reached first, 6 legal deliveries or 8 balls bowled in total. Wides and no-balls count toward the 8-ball cap, so an over full of wides can end before 6 legal deliveries are bowled. | MYCA Junior Playing Conditions | Correctly said the over ends at whichever comes first, 6 legal deliveries or 8 total, citing J15. | Pass |
| 3 | Umpire: "If the 8th ball in a junior over turns out to be a no-ball, does the batter still get a free hit, or has the over already ended?" | The junior playing conditions set the 8-ball cap and the no-ball/free hit rule separately, but do not state which one governs when they collide on the same delivery. | not in rules - expect honest fallback | Said the rules do not appear to cover this, matching the genuine ambiguity in the real document. | Pass |
| 4 | Captain: "If it rains after 20 overs and we can't finish, how do we decide the winner?" | MYCA Senior Playing Conditions sets out a run-rate based revised target method for interrupted one-day matches, applied once a minimum number of overs per side has been bowled. | MYCA Senior Playing Conditions | Said the rules do not appear to cover this. Avoided the fabricated "revised target" claim but missed the real answer, rule 5.2.2, a lost result is a draw. | Partial, see Baseline Evaluation Findings |
| 5 | Parent: "My son's in the U13s, why do their overs sometimes run longer than 6 balls, is that even allowed?" | Yes. Junior grade overs can run up to 8 balls if there are wides or no-balls, because the over only ends once 6 legal deliveries or 8 total balls have been bowled, whichever comes first. | MYCA Junior Playing Conditions | Correctly explained overs can run to 8 balls under J15, matching the real rule. | Pass |
| 6 | Umpire: "Does the women's one-day comp use the same powerplay overs as the senior comp?" | No. MYCA Women's Playing Conditions sets its own powerplay length and fielding restrictions, which differ from the senior grade. | MYCA Women's Playing Conditions | Said the rules do not appear to cover this. Confirmed correct: no MYCA document, any grade, mentions powerplay at all. The expected answer was fabricated. | Pass |
| 7 | Captain: "One of our players wants to transfer in from another club mid-season so he can play finals with us, can we do that?" | MYCA By-Laws set a transfer window during the season and a cut-off date before which a player must be registered to be eligible for finals. A transfer after that date is not eligible for finals. | MYCA By-Laws | Said the rules do not appear to cover this, then partially cited a junior finals-eligibility clause. The real rules separate transfer limits, one per season, from finals eligibility, games played, with no unified transfer cut-off as the expected answer assumed. | Partial, see Baseline Evaluation Findings |
| 8 | Club official: "What's the fine if we forfeit a match with less than 24 hours notice?" | MYCA By-Laws set a fixed forfeit fine for late notice, higher than the fine for a forfeit notified before the cut-off. | MYCA By-Laws | Correctly quoted Senior Men's forfeit fine, $100 rounds 1-6, $200 rounds 7-9, but the question was not grade-scoped and Senior Women's actually uses a flat $50 fine every round. Presented one grade's numbers without flagging that other grades differ. | Partial, see Baseline Evaluation Findings |
| 9 | Umpire: "A captain reckons MCC Laws say an over is always 6 balls, full stop, so we should ignore the 8-ball cap for U13. Is he right?" | No. MYCA's own junior playing conditions set the 8-ball cap for that grade, and that local rule overrides the general MCC default of a 6-ball over. | MYCA Junior Playing Conditions (overrides MCC Law default) | Correctly said the captain is wrong and the junior 8-ball cap applies, citing J15. | Pass |
| 10 | Captain: "Does the follow-on rule apply if we bowl the other team out cheaply in our one-day comp?" | Follow-on is a multi-innings concept that does not exist in MYCA's one-day playing conditions for any grade. | not in rules - expect honest fallback | Said the rules do not appear to cover this, matching the real rules. | Pass |
| 11 | Captain: "Is it going to rain Saturday at our home ground, should we plan for a delayed start?" | Requires a live weather forecast for the specific ground and date, which the rule documents don't contain. | public web - expect Tavily route | Not yet testable, requires the Tavily web-search route, not yet built. | Not tested |
| 12 | Umpire: "I heard Cricket Australia changed the concussion substitute rule this season, does that apply to our grade?" | Requires checking Cricket Australia's current published policy and whether MYCA has adopted it, since the association's own documents may not yet reflect a recent national rule change. | public web - expect Tavily route | Not yet testable, requires the Tavily web-search route, not yet built. | Not tested |
| 13 | Parent: "My daughter's 12. Can she play in the boys U13 team if our club doesn't have a girls team this year?" | MYCA By-Laws set eligibility for girls to play in the corresponding boys grade when no girls team is fielded by their club, subject to age and grade limits. | MYCA By-Laws | Said the rules do not appear to cover this, despite the applicable clause, a female age allowance to play with males, being retrieved and included in context above the relevance threshold. A reasoning miss, not a retrieval miss. | Partial, see Baseline Evaluation Findings |
| 14 | Umpire: "Ball hits the sightscreen on the full, is that a six or do I call dead ball?" | MYCA Senior Playing Conditions treats a full-pitched hit into the sightscreen as a boundary six at grounds without a boundary rope, unless that ground's specific conditions state otherwise. | MYCA Senior Playing Conditions | Said the rules do not appear to cover this. The sightscreen-specific claim was fabricated, the real general rule, 4.9.12, was not retrieved. | Partial, see Baseline Evaluation Findings |

## Baseline Evaluation Findings

I ran the baseline retrieval and answer pipeline (search_rules, then one gpt-4o-mini call through the LiteLLM proxy, no agent framework, no judge, no web search) against real questions, using the full MYCA corpus that is actually ingested: Junior, Senior Men's, and Senior Women's playing rules, plus the two operational forms. This section replaces guesswork with what the system actually did.

The first finding is about the evaluation table itself. Of the ten expected answers I have now checked against real documents, five turned out to be wrong. Question 1 assumed a flat one over per four minutes formula and stated 34 overs, but the real rule for a non-weather late start points to a separate lookup table, and 6 minutes lost falls in that table's 5 to 8 minute band, which is 2 overs, giving 33 overs, not 34. Question 4 invented a run rate based revised target method. The real rule is simpler: a lost result after play has commenced is just a draw. Question 6 assumed MYCA has a powerplay system that differs by grade. I searched every ingested document for the word powerplay and found it nowhere. No such system exists at all. Question 7 assumed a single rule ties a transfer cut-off date to finals eligibility. The real rules keep those two things separate, a one-transfer-per-season limit and a games-played threshold for finals, with no cut-off date connecting them. Question 14 invented a specific sightscreen rule. No such rule exists, only a general boundary six rule for a ball hit into a tree or other obstacle. Only questions 2, 5, 9, and 10 turned out to be correct as originally written. I wrote all fourteen expected answers before the real documents were ingested, and half of the ones I have now checked were wrong, in one case, question 6, wrong about a whole rule existing at all. An eval table written before a corpus exists is a guess, not a ground truth.

The second finding is about retrieval recall. In three cases, question 1, 4, and 14, the real answer existed somewhere in the ingested chunks, but the specific clause needed, a lookup table, a two-line clause in a five-sentence section, or a deep sub-clause, did not make the top 5 results. The baseline did not guess in any of these cases. It either said the rules do not appear to cover the question, or, for question 1, correctly named the applicable rule and then honestly admitted it could not state a number.

The third finding is that even when the right chunk is retrieved, the model does not reliably use it. Question 13 is the clearest case: the exact clause needed, a female age allowance to play in a boys' competition, was retrieved above the relevance threshold and included in the prompt, and the model still said the rules do not cover the question. I saw the same pattern testing two multi-step calculations directly outside the table. A question about time lost during a first innings produced three correct answers and one wrong one across four attempts with the same retrieved context and no fixed temperature setting. A related question about a mid-innings weather delay was refused three times in a row, even though the exact formula it needed was sitting in the context it had already retrieved. Retrieval itself was reliable throughout. The single LLM call is not, in both directions: sometimes refusing an answerable question, sometimes making an arithmetic mistake partway through a multi-step rule.

The fourth finding came from ingesting the rest of the corpus today. With only the Senior Men's document ingested, there was no way to notice this, but match_rule_chunks originally filtered only on association_id, not grade. Once Junior and Senior Women's documents shared the same association_id, a senior-grade question could in principle retrieve and cite a junior-only or women's-only chunk as if it applied. Question 8 showed a real version of this: asked without specifying a grade, the baseline confidently quoted Senior Men's forfeit fine, $100 to $200 by round, with no mention that Senior Women's uses a flat $50 fine instead. I fixed the underlying gap today, match_rule_chunks and search_rules now take an optional grade_scope filter, verified working, but the fix only helps when a grade is actually supplied. A genuinely grade-ambiguous question, like question 8's, still needs either a clarifying question back to the user or an explicit warning that the answer may vary by grade, and the baseline does neither.

The fifth finding came from a question outside the table, once both operational forms were ingested. Asked what the process is if a bowling action is found to be illegal, the baseline retrieved both the general rules text on suspect actions and the dedicated Suspect Bowling Action Form's own procedure chunk, both above the relevance threshold. The answer used only the rules text: correctly describing what happens once a report escalates, no action on the day, the club must rectify, a second report suspends the player from bowling, a Cricket Victoria remedial session before they can return. It never mentioned the form's own specific first step, submit that exact form to the Secretary and Umpires' Coordinator within 48 hours, keep it confidential, one form per player. Both chunks were sitting in the same context. The model favored the rule_text chunks over the procedure chunk and produced an answer that was accurate as far as it went but left out the actual first action an umpire needs to take.

None of this failed silently in the sense that matters most. Every fallback I saw named no invented rule number and no fabricated section, the one case where a wrong number reached an answer, question 8, was a real number from a real document, just the wrong grade's, not an invention, and the suspect-bowling case was accurate as far as it went, just incomplete. That is the property I care most about holding at this baseline stage. It held in every test except the grade-ambiguity gap, which is now at least partially addressed at the retrieval level.

## Data Strategy

### Chunking strategy

I am using structure-aware chunking, not fixed-size blind chunking. Each of MYCA's documents already has its own numbering scheme, and I split on that instead of on a raw token count. The Junior document uses flat labels, J1 through J25. The Senior Men's and Senior Women's documents use a decimal hierarchy, section down to sub-clause, for example 5.3.3. A chunk boundary always falls on one of these section breaks, so a retrieved chunk is a complete rule, not half of one.

Within that constraint I target roughly 500 to 800 tokens per chunk, with about 15 percent overlap, 100 to 120 tokens, between adjacent chunks. MYCA's own rules cross-reference each other constantly. Rule 5.3.3 in the Senior Men's document sets overs and time penalties and then points at the Appendix B table for the exact numbers. Without overlap, a chunk containing the penalty clause could get separated from the table it depends on, and the agent would answer with half the rule.

Tables get special handling. Appendix B in both Senior documents, the overs-reduction table for time lost to rain, is about 70 rows mapping accumulated minutes lost to overs lost, running from 0 up to 280 minutes. If a chunk boundary cut through that table, a chunk covering only the first half would silently have no answer, or the wrong nearby answer, for a real question like "we lost 150 minutes today, how many overs do we lose." So every table, the Appendix B overs-reduction table, the Appendix A fines table, the junior bowling-restriction table in J16, and the over-rate schedule in J15, is extracted and kept as one chunk each, tagged as a table, and never split even if that chunk runs over the target size. A partial table is worse than no table.

The three playing-conditions documents cover different grades and genders, and they genuinely disagree with each other, not just in numbers but in which rules exist at all. The Senior Women's document has a clause capping an over at 8 total balls, 6 legal deliveries or 8 balls including extras, whichever comes first. That clause does not exist anywhere in the Senior Men's document. If retrieval pulled from both documents without distinguishing them, a senior men's query could surface a women's-only rule as if it applied, which is exactly the kind of wrong answer this project exists to prevent. So every chunk carries a grade_scope tag, junior, senior_men, or senior_women, and retrieval filters on it alongside association_id.

The two forms, the Player Conduct Report and the Suspect Bowling Action form, are not rules text, they are short operational documents: tick-box sections and a set of instructions for who to email and within what deadline. I chunk each form as one procedural chunk covering the instructions, plus one chunk per structured section, for example the Level 1 tick-box section separate from the Level 2 tick-box section on the conduct report. These are short documents, so this produces only a handful of chunks total. They go into the same pgvector table and are retrieved through the same single retrieval tool as the rules documents, not a separate tool, because the project's Task 2 commitment was one retrieval tool scoped by association_id, and a second tool for two small forms would add agent complexity without real benefit at this scale. They are distinguished purely by a document_type tag set to form, so a rules question about no-balls never surfaces a form chunk, and a question like "what do I do if I suspect an illegal bowling action" retrieves the form's procedure text instead of rules text.

Every chunk carries the same metadata regardless of document: association_id, document_type (rules or form), grade_scope (junior, senior_men, or senior_women), section_number, and content_type (rule_text, table, or procedure). This is what lets the retrieval tool answer correctly: a senior women's overs question never surfaces a junior chunk, and a rules question never surfaces a form chunk.

### Data source and external API

The data source is MYCA's own documents: the three playing-conditions documents, Junior, Senior Men's, Senior Women's, and the two operational forms. They are stored as PDFs in Supabase Storage, chunked as described above, and embedded into a pgvector table scoped by association_id, using OpenAI's text-embedding-3-small model at 1536 dimensions. I chose that model over text-embedding-3-large because it gives strong retrieval quality for this kind of structured, moderate-length domain text at a fraction of the cost, and because each association's corpus is only a handful of PDFs, so the larger model's extra dimensionality buys almost nothing while roughly doubling embedding cost and pgvector storage, a cost that compounds once more associations are added to the platform.

The external API is Tavily. It handles two different kinds of question MYCA's own documents don't cover. The first is current public information that isn't in the PDFs, like weather on a given match day. The second is basic Laws of Cricket questions that MYCA's playing conditions assume rather than define. Both the Junior and Senior documents open by stating that the Laws of Cricket apply to all matches unless a rule excludes or modifies them, which means the documents only ever spell out where MYCA differs from the Laws, never the Laws themselves. A question like what counts as an LBW dismissal, what a no ball or a wide or a dead ball is, or how an umpire signals a short run, has no answer anywhere in MYCA's corpus, because that corpus was never written to teach the base game. For this second kind of question the agent draws on the model's own general cricket knowledge together with Tavily, rather than searching a corpus that was never meant to hold the answer.

The two sources interact in a fixed order. Local retrieval is always attempted first, because the entire premise of this project is that an association's own playing conditions override general or public cricket knowledge where the two overlap. The Route decision in the agent workflow sends rules questions to local retrieval first, and the Found check decides whether that retrieval turned up something relevant. Only a genuine miss, whether that's a question the association's documents are silent on, a current public-information question, or a base Laws of Cricket question the documents assume without defining, falls through to Tavily and general knowledge, or to the honest fallback if nothing usable comes back.
