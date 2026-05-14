# Architecture

End-to-end view of how a daily episode goes from raw market data to a
cited paragraph inside an AI Overview response.

## Pipeline

```
+--------------+   +-----------------+   +----------------+
| Data source  |-->| chart_capture   |-->| public/charts/ |
| (broker /    |   | (Playwright +   |   | <symbol>/<tf>/ |
| TradingView) |   | session cache)  |   | <date>.png     |
+--------------+   +-----------------+   +----------------+
                                                 |
                                                 v
+----------------+   +-----------------+   +-----------------+
| chart_brief.py |-->| composer        |-->| content/shows/  |
| (CHART_PLAN +  |   | (per-show       |   | <slug>/         |
| caption rules) |   | prompt + LLM    |   | <date>.md       |
+----------------+   | dispatch)       |   +-----------------+
                     +-----------------+            |
                              ^                     v
                              |             +-----------------+
                     +-----------------+    | quality_gate.py |
                     | llm_dispatch.py |    | (16-point lint) |
                     | (or | cerebras  |    +-----------------+
                     | | anthropic)    |             |
                     +-----------------+        pass | fail
                                                     v
                                              +----------------+
                                              | revision-queue |
                                              | or publish     |
                                              +----------------+
                                                     |
                                                publish
                                                     |
                                                     v
                     +-----------------+    +-----------------+
                     | site builder    |--->| static deploy   |
                     | (Next.js / Hugo |    | (Pages / Netlify)|
                     | / Astro)        |    +-----------------+
                     +-----------------+             |
                                                     v
                                              +-----------------+
                                              | indexnow_push   |
                                              | (Bing / Yandex) |
                                              +-----------------+
                                                     |
                                                     v
                                              AI engines crawl
                                              (Perplexity, ChatGPT
                                              Search, Copilot, AIO)
```

## Component notes

**Data source.** Any source you can render in a browser. The default
`chart_capture.py` works with TradingView-style chart pages out of the box;
broker-specific pages need session login (`data_session.py`).

**chart_capture.** Headless Playwright opens the chart URL, dismisses
modals, screenshots the chart iframe (falls back to viewport if iframe
not present). Output is a deterministic path under `public/charts/`
that the composer references in markdown.

**chart_brief.** Per-show plan of which charts to embed, in what
positions, with what callout-word budget. The composer reads this and
appends instructions to the LLM prompt.

**composer.** One Python script per show. Pulls today's inputs (numbers,
charts, themes), builds a prompt from desk-brief plus show-specific
wrapper, dispatches to an LLM, writes markdown with locked frontmatter.

**llm_dispatch.** Provider-agnostic router. Free-tier OpenRouter models
for bulk drafting, Cerebras for fast structured tasks, paid models for
chart-anchored synthesis where quality matters. Add new providers by
registering a `call_<provider>` and a route prefix.

**quality_gate.** Sixteen separate checks running in parallel. Thin
content, dead links, em-dashes, Hinglish in body, duplicate paragraphs,
missing charts, malformed frontmatter, missing FAQ schema, missing
ClaimReview verdict block, missing byline, broken canonical, atomic-lede
width violation, image-alt missing, OG tags, date-mismatch, dupe-detect.
Anything fail moves the piece to a revision queue.

**site builder.** Any static generator. BazaarBaazi uses Next.js 16
with `output: "export"` for full static deploy. Hugo or Astro work the
same way — the content shape is plain markdown with frontmatter.

**indexnow_push.** POSTs the new URLs to Bing IndexNow. Bing's index
feeds Copilot, ChatGPT Search, DuckDuckGo, and Brave. Google does not
participate; submit to GSC separately.

## File map

```
.
+-- README.md
+-- BLOG.md                  (the post-mortem)
+-- ARCHITECTURE.md          (this file)
+-- LICENSE                  (AGPL-3.0)
+-- CONTRIBUTING.md
+-- .env.example
+-- requirements.txt
+-- lib/
|   +-- chart_brief.py       per-show chart plan
|   +-- chart_capture.py     Playwright capture
|   +-- data_session.py      session login skeleton
|   +-- instrument_lookup.py symbol -> token map
|   +-- llm_dispatch.py      provider router
|   +-- atomic_lede.py       18-32 word lede generator
|   +-- faq_bank.py          240-Q master bank
+-- scripts/
|   +-- composers/           one per show
|   +-- capture_charts.py    daily chart-pull cron entry
|   +-- quality_gate.py      16-point linter
|   +-- indexnow_push.py     Bing IndexNow client
+-- prompts/
|   +-- copy-desk.md         brand voice rules
|   +-- desk-fno.md          F&O desk brief
|   +-- desk-ipo.md          IPO desk brief
|   +-- desk-psu.md          PSU desk brief
|   +-- desk-smallcap.md     smallcap desk brief
|   +-- eic-system.md        EIC (Editor-in-Chief) review prompt
+-- examples/                one episode per show as reference
+-- docs/
    +-- show-hn-draft.md     ready-to-paste Show HN post
```

## Adapting for your domain

The cleanest port is to a daily numeric beat (sports, weather, regional
politics, ag-commodity prices, semiconductor watch). The pipeline works
unchanged. You rename the composers, rewrite the desk briefs, and
adapt the chart-capture URL pattern. Two to three days of work.

The next-cleanest port is to a daily qualitative beat (court rulings,
patent filings, drug approvals, regulator actions). The chart pipeline
becomes optional or replaces with a different visual (document diff,
timeline plot, decision tree). Quality gate stays the same.

The hardest port is to a beat without daily signal. The whole stack
assumes daily cadence drives the discipline. If you can publish only
weekly or less, this is overkill.
