# Show HN draft

**Submit at 09:00 IST Tuesday (03:30 UTC, ~earliest US morning) for best front-page reach.**
Tuesday morning HN is the highest-discovery window. Avoid Mondays (lower retention) and
weekends (smaller HN crowd).

---

## Title

```
Show HN: Newsroom-as-Code – AI-augmented daily newsroom stack, one editor, 10 shows
```

(80-char limit. This is 76 chars. Keep "Show HN:" prefix; HN ranks Show HN
posts in their own queue.)

## URL

```
https://github.com/Declan142/bazaarbaazi-newsroom
```

## Text (the comment that becomes the post body)

```
Hi HN — I run BazaarBaazi (https://bazaarbaazi.com), a daily Indian-
markets publication. Ten chart-anchored, signed-verdict episodes per
trading session. One editor. Zero staff. The stack is what I built to
make that possible, and I am open-sourcing it.

What's in the repo:

- 11 composer scripts (one per show) that drive the daily pipeline
- Quality gate with 16 separate checks (thin content, dead links, em-dash
  detection, dupe match, missing chart, atomic-lede width, schema gaps)
- Provider-agnostic LLM dispatcher (OpenRouter, Cerebras, drop-in for
  Anthropic/OpenAI)
- Playwright session manager + chart capture skeleton
- The 240-question FAQ master bank, rotated by market state, that feeds
  FAQPage schema for AI-engine citation
- Atomic-lede generator locked to 18-32 words with one number, one date,
  one verdict-anchor (this is what Perplexity and AI Overview extract verbatim)
- The five-voice Council review pattern documented in prompts/

Why I built it this way: Indian retail-finance media hedges everything.
Nobody commits. Readers who actually trade get no signal. The bet was
that AI does the typing and a human owns the editorial discipline.
The discipline is in the code — voice rules in regex, structure in
templates, fact-checks in linters.

Cost: ~30-80 cents/day inference, ~90 minutes/day editorial. Static
hosting free. The repo is AGPL-3.0 with an attribution rider.

Where this ports cleanly: any niche daily beat. Sports stats, weather,
regional politics, semiconductor watch, drug approvals, regulator
actions. Anywhere a domain has daily signal and an underserved reader.

Repo: https://github.com/Declan142/bazaarbaazi-newsroom
Full post-mortem: https://github.com/Declan142/bazaarbaazi-newsroom/blob/main/BLOG.md
Site: https://bazaarbaazi.com

Happy to answer questions about composer design, quality-gate checks,
the Council pattern, or anything else.
```

(~330 words. Targets HN sweet spot. Avoid emojis. Avoid hype.)

## First-comment prep

Have ready to post immediately as a reply to your own thread:

```
A couple of things I learned that are not in the README:

- Em-dash bans matter more than they sound. Triple-defense (prompt +
  regex gate + post-strip) because a single em-dash collapses brand trust
  for readers who can spot LLM tells. Of all the small details, this one
  produced the biggest reader-trust delta.

- IndexNow is the under-exploited 2026 SEO move. Bing IndexNow → 48-72hr
  citation eligibility in Copilot, ChatGPT Search, DuckDuckGo. Google
  doesn't participate, but for AI-engine surfacing Bing's index is
  actually the more valuable pipe right now.

- Quality gate as parallel checks (16 of them, ThreadPoolExecutor) is
  the leverage point. Each check is 10-30 lines. Together they enforce a
  higher bar than any single-pass review.
```

## Posting checklist

1. **Title under 80 chars.** Keep "Show HN:" prefix.
2. **URL = GitHub repo**, not the site.
3. **Body in the comment-text box** (the "url" field is just the link).
4. **Submit at 09:00 IST Tuesday (03:30 UTC).** Set a calendar reminder.
5. **First comment within 5 minutes** of posting (the prep above).
6. **Stay online for 2 hours** to engage with comments.
7. **Do not ask for upvotes anywhere.** HN auto-flags vote-rings.
8. **If front page, prepare follow-up post** on Twitter/Substack 24hr
   later linking back ("HN discussion on the open-source newsroom stack").

## Cross-post timing

- HN: Tuesday 09:00 IST
- ProductHunt: Wednesday 09:00 IST (different audience, same artifact)
- Reddit r/programming + r/python: Wednesday afternoon
- LinkedIn longform: Thursday morning (B2B audience picks it up)
- Twitter thread: same as HN submit time, links to repo + BLOG

## Failure modes to avoid

- Submitting without a working repo (HN audit-checks links)
- AI-generated comments (HN crowd spots them in seconds)
- Treating Show HN as a launch announcement (it's a "show me what you
  made" cultural format)
- Replying defensively to criticism (engage with the technical point
  even when the tone is hostile)
