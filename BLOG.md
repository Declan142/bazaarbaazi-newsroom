# How a one-person AI newsroom publishes 10 daily finance shows

Ten days ago I shipped the first episode of BazaarBaazi, a daily Indian-markets
publication. Today there are 192 URLs live, ten shows running on cron, every
piece signed with a stance and anchored in a first-party chart. One editor.
No staff. The stack is open-source now and this is the post-mortem.

## The problem

Indian retail-finance media reads like a defensive memo from 2003.
Moneycontrol, ET Markets, Mint, Livemint, Business Standard — they all
move in the same hedged voice. "Equity benchmarks ended mixed on
Thursday as investors weighed..." Nobody commits. Every analyst quote is
loaded with caveats. The video desks are louder but no more committal.

The reader who actually trades — retail F-and-O punter, the smallcap
hunter, the IPO grey-market follower — gets nothing usable. They want a
take. They want to know what someone with a name on it thinks. They
want the chart. They want three numbers, not seven paragraphs.

The category vacuum was obvious. The cost of filling it was the
problem. A traditional newsroom for daily markets coverage runs you a
team of six and burn at a few lakhs a month before you have a single
reader. A one-editor publication ships maybe one piece a day before
burning out.

So the bet was: can AI do the typing if a human owns the editorial
discipline? Not AI does journalism — AI assists journalism. Editor
picks the beats, writes the prompts, owns the verdicts. AI executes
within strict brand constraints.

## The bet

Four anchors held the whole thing together.

**Signed-verdict editorial.** Every episode ends with WHAT BAZAARBAAZI
THINKS — one explicit stance with a name on it. If we can't commit,
we don't publish. This is the opposite of hedge-everything finance
journalism.

**Chart-anchored.** No piece ships without at least one first-party
chart embedded inline. Daily Kite captures of NIFTY, BANKNIFTY, VIX,
eight sector indices. The chart is the thesis spine.

**Voice locked.** Pure English. Filmy retail-finance India tone (IPO ka
khel, levels ka kahaani, brand-anchored verdict labels). Zero em-dashes
(em-dash is the number-one LLM tell). No "moreover", no "furthermore",
no "it is important to note." The voice is checked by lint, not by hope.

**AI-augmented, human-edited.** Composer per show writes the draft from
inputs (today's numbers, today's chart, the show brief). Quality gate
lints sixteen failure modes. The editor reviews and ships. The AI never
hits publish.

## The architecture

Ten composers, one per show. `show-opening-move.py`, `show-closing-bell-flash.py`,
`show-fno-data-dive.py`, etc. Each takes today's date as argument,
pulls the chart manifest and verdict inputs, calls an LLM with a
locked prompt, writes markdown to `content/shows/<slug>/<date>.md`.

The prompt for each composer is two layers. A base desk-brief
(`prompts/desk-fno.md`) sets the editorial frame. A per-show wrapper
inside the composer locks structure, word cap, chart-embed rules, and
the verdict block. Together they produce 800-1100 words, ~3-8 inline
charts, one signed verdict.

The quality gate is sixteen separate checks: thin content (sub-400
words rejected), dead links (HTTP probe of every external URL), em-dash
detection (instant reject), Hinglish particles in body (only chrome
allowed), duplicate-paragraph match against last 30 days, missing
chart, missing verdict block, atomic-lede width violation (18-32 words
locked), broken frontmatter, malformed canonical, FAQPage schema
absence, ClaimReview verdict-attribution absence, byline missing,
date-mismatch, image-alt missing on charts, OG tag missing. Any fail,
the piece goes to a revision queue and never reaches the site.

The five-voice Council is a review pattern, not separate code paths.
Builder asks does this ship. Skeptic asks where the trip-wire is.
Quant asks what the numbers actually say. Brand asks does this match
the voice. Synthesizer combines and emits a confidence rating. A
human-final layer of safety on top of the lint.

Publish is a `next build && wrangler pages deploy out/` followed by an
IndexNow blast. IndexNow gets the URLs into Bing's index in minutes,
which feeds Copilot, ChatGPT Search, DuckDuckGo, and Brave. Google
takes longer but you can submit to GSC the same way.

## The discipline

The bans matter more than the tools. Em-dashes banned. Banned at the
prompt layer ("never use em-dashes"), banned at the quality-gate layer
(regex reject), banned at the post-strip layer (auto-replace with comma
or period). Triple defense because em-dashes are the single biggest
LLM-tell — readers spot them in two seconds and brand trust collapses.

Atomic-lede locked at 18-32 words, one sentence, exactly one number,
dated, ending with a verdict-anchor. This is what AI Overview / Perplexity
extract verbatim. Every episode opens with it. Every composer enforces
it via regex gate before output is accepted.

FAQ schema enforced. Twelve questions per closing-bell-flash episode,
rotating from a 240-question master bank (`lib/faq_bank.py`), keyed by
market state (bull / bear / flat / expiry / IPO-rush). Each Q+A is
35-55 words with at least one specific number. Perplexity extracts
FAQ entries verbatim — verified across stackoverflow, healthline. This
is citation gold.

ClaimReview wraps every signed verdict. Schema.org ClaimReview tells
Google Fact-Check Tools, Bing News fact-check carousel, and AIO that
this is an attributable, dated, claim-style stance from a named editor.
Zero competitors in Indian finance emit ClaimReview because they
structurally don't issue claims. We do. Vacant slot.

## The cost

Roughly 50-80 LLM calls per day across all ten shows, ranging from
fast cheap models (DeepSeek-V4-Flash for setup briefs) to premium
(Opus 4.7 for the back-half synthesis on long-form pieces). Total
inference cost: 30-80 cents/day at retail rates. Free-tier models
on OpenRouter cover the bulk of drafting; paid models are gated to
chart-anchored composition where quality matters most.

Editor time: ~90 minutes / day reviewing, editing, signing. Less than
one good Twitter doom-scroll session.

Infra: Cloudflare Pages free. Site builds in 90 seconds. Total
hosting cost zero.

## What works

The quality gate. Catching thin content before publish is the single
most valuable discipline. It is harder to write a piece that passes
the gate than to write a generic piece — and that is the point. The
gate forces depth.

The Council pattern. Even when it runs entirely in the editor's head
without separate API calls, naming the four voices forces a wider
review surface than a single-pass edit.

The cadence. Ten episodes a day looks insane until you realize each is
800-1100 words with auto-generated chart embed. Editorial overhead per
episode is the verdict, not the body.

## What does not work

Chained image-to-video generation for sketch animation — entirely
different project, lessons noted. AI voice for editorial commentary —
authenticity matters more than coverage; we still record real voice.

Composer prompts that are too loose. Every time we relaxed an
output-structure constraint, drift crept back in. Lock everything that
can be locked.

## What you can copy

Five things port to any niche newsroom you want to build.

1. **The quality gate** — 16 separate checks, parallel-runnable, fail-fast.
   Adapt the checks for your domain (medical citations? legal references?
   sports stats verification?). The pattern transfers.

2. **The atomic lede discipline** — 18-32 words, one number, dated,
   verdict-anchor. AI engines extract this verbatim. Works for any
   beat where readers want a quick answer.

3. **The Council review pattern** — name the voices, route every piece
   through all four. Catches what single-pass misses.

4. **Em-dash ban as policy** — triple defense (prompt + gate + strip).
   Smallest detail with biggest brand-trust effect.

5. **Composer-per-beat architecture** — don't write one Composer god
   class. One composer per show, one prompt per composer, one schema
   per show. Concerns isolated. Easy to evolve one beat without
   destabilizing others.

## Closing

The reason this works is not the AI. The AI is the typewriter. The
reason this works is editorial discipline encoded as code — voice
rules in regex, structure rules in templates, fact-check rules in
linters. Once that is in code, one editor is enough.

If you build a niche newsroom on this stack, write to me.

— Aditya Sharma, [@Declan142](https://x.com/Declan142),
[bazaarbaazi.com](https://bazaarbaazi.com)
