# Contributing

Forks welcome. Pull requests welcome. The point of this repo is for
other newsrooms to lift the pattern, not just admire it.

## What we want

- Bug fixes
- Adapter modules for new LLM providers or data sources
- Documentation improvements
- Reference recipes for new beats (sports, weather, regional politics,
  scientific instruments, regulator-watch, etc.)
- Quality-gate checks for domains we have not covered

## What we do not want

- Breaking changes to the public composer interface without a
  migration path
- Provider-specific lock-ins (this repo stays provider-agnostic by
  design)
- AI-generated PRs that the author has not read

## How to contribute

1. Fork the repo
2. Branch from main: `git checkout -b feat/your-thing`
3. Make your change with a focused commit
4. Run `python scripts/quality_gate.py` on any sample output
5. Open a PR with a 1-paragraph description of the why

## Forks and attribution

If you build a public newsroom on this stack, the AGPL license requires
your fork to remain open-source. Beyond that, please attribute the
original architecture on your `/masthead`, `/about`, or footer:

```
Built on Newsroom-as-Code by Aditya Sharma, bazaarbaazi.com
```

That is the entire ask. No commercial fee, no consulting required.

## Bug reports

Open an issue. Include:

- What you ran
- What you expected
- What actually happened
- Versions: Python, Node, OS

If it is a quality-gate false-positive, include the markdown file
that triggered the false reject.

## Code style

Plain Python, plain TypeScript. No clever metaprogramming. The point
of this repo is that someone non-expert can read it and ship a
newsroom.

- 4-space indent in Python
- 2-space indent in TS / JSON
- No em-dashes anywhere in code or docs
- Names that describe what, not how
