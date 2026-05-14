# Newsroom-as-Code

An open-source template for an AI-augmented daily editorial newsroom.
Built and battle-tested on [BazaarBaazi](https://bazaarbaazi.com), a one-editor
Indian-markets publication shipping 10 chart-anchored, signed-verdict episodes
per session.

This is the actual stack. Not a slide deck. Not a wrapper. The composers,
the quality gate, the chart pipeline, the prompts, the Council review
pattern — all here.

## What this is

A working pipeline for running a daily publication with one human editor
and AI doing the typing. Every episode passes a 16-point quality gate
(thin-content reject, dead-link reject, em-dash strip, dupe detect,
chart presence, atomic-lede width, voice violations) before it goes live.

If you've ever wanted to build a niche daily, this is the scaffold.

## What you can build with it

- Daily markets / sports / weather / regional-news desk
- Niche industry tracker (semiconductor watch, biotech earnings desk, ag-commodity wire)
- Local-government accountability beat
- Domain-specific Q-and-A surface with daily signal
- Verticalized AI Overview citation surface (because every piece carries
  ClaimReview + FAQPage + atomic-lede schema — adapt at your peril)

The pattern works wherever a beat is publishable daily and signal compounds
with consistency.

## Quick start (30 minutes)

```bash
git clone https://github.com/Declan142/bazaarbaazi-newsroom.git
cd bazaarbaazi-newsroom
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # fill in your LLM key + data source creds
python lib/data_session.py login # adapt selectors first for your source
python scripts/composers/show-opening-move.py 2026-05-14
python scripts/quality_gate.py   # 16-point lint
```

If the composer produces a markdown file in `examples/opening-move/`
that survives the quality gate, you have a working newsroom.

## Architecture

```
   data source           LLM provider
   (chart + numbers)     (Anthropic / OR / Cerebras)
        |                    |
        v                    v
   chart_capture --> composer  --> quality_gate --> publish (Next.js / Hugo / your-static)
        |               (per-show     (16-point             |
   instrument_lookup     prompt)       lint)                v
                                                       IndexNow ping
                                                       (Bing + Yandex + Naver)
                                                            |
                                                            v
                                                       AI engines pick up
                                                       (Perplexity, ChatGPT
                                                       Search, Copilot, AIO)
```

Detail at `ARCHITECTURE.md`.

## The 5-voice Council

Every signed verdict passes through a five-voice editorial review:
Builder (does this ship?), Skeptic (where's the trip-wire?), Quant (what do
the numbers actually say?), Brand (does this match the voice?), and
Synthesizer (final call + confidence). The pattern is documented in
`prompts/eic-system.md`. It catches what a single-author pass misses
without slowing the cadence.

Origin and full reasoning in `BLOG.md`.

## Stack

- **Composer**: Python 3.10+, plain stdlib + `requests` + `pyyaml`
- **Site**: any static generator (Next.js 16 in the original, Hugo or
  Astro work fine, just adapt the `content/` shape)
- **Hosting**: Cloudflare Pages, Netlify, GitHub Pages — your call
- **LLM**: any chat-completions API (OpenRouter / Cerebras / Anthropic /
  OpenAI). See `lib/llm_dispatch.py` for the router.
- **Data**: Playwright session manager + your broker / data vendor.
  See `lib/data_session.py` for the skeleton.
- **Backend** (optional, for forms / subscriptions): PocketBase, anywhere.

## Personalization checklist

Before you run this in your own newsroom, grep-and-replace:

- `Aditya Sharma` → your byline
- `Declan142` → your handle
- `bazaarbaazi.com` → your domain
- `BazaarBaazi` → your publication name
- LinkedIn URL in composers → your LinkedIn (or remove the line)

Then adapt:

- `lib/data_session.py` form selectors for your data provider
- `lib/instrument_lookup.py` CSV shape for your provider's symbol list
- `lib/chart_capture.py` chart URL pattern
- `prompts/*.md` desk briefs for your domain
- `lib/faq_bank.py` Q-set for your reader's questions
- `scripts/composers/` rename and rewrite for your daily beats

## License

AGPL-3.0. Forks must remain open-source under the same license. If you
build a public newsroom on this stack, attribute it in your `/masthead`
or `/about` page. That is the entire deal.

## Credits

Original architecture and editorial pattern by Aditya Sharma,
[bazaarbaazi.com](https://bazaarbaazi.com). If you build something with
this, I would love to read it. Find me at
[@Declan142](https://x.com/Declan142).
