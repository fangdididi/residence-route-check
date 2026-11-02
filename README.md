# Residence Route Check

**English** | [简体中文](README.zh-CN.md)

An agent skill that turns "where could we legally move?" into a dated route sheet for one person or one family. Each candidate residence route (digital nomad, skilled work, study-to-work, self-employed, passive income, investment) is run through the same five gates, every key rule must point to an official page read recently, and the result is a clear verdict with the exact changes, checks and dates that would move it.

> Not legal, tax or immigration advice. The skill helps you organise facts and spot problems early; always confirm on the official page, and talk to a licensed specialist when the case is complicated.

## Why it exists

Most failed or delayed moves are not about choosing the wrong country. They come from small, checkable things:

- the passport is not on the route's nationality list;
- the income bar is per family, counted gross, and needs six months of proof, not three;
- a police certificate expired before the appointment;
- the route cannot be renewed or converted, so it is a dead end for someone who wants permanent residence;
- a long first stay quietly makes you a tax resident.

Residence Route Check makes the agent catch these before anyone pays for translations, lawyers or flights.

## Features

- **Five gates in a fixed order:** passport, money, requirements, clock, goal.
- **Four honest verdicts:** FITS NOW, HYPOTHESIS, AFTER CHANGE, BLOCKED, each with the reasons listed.
- **Evidence discipline:** key claims need an official source with a read date; stale sources and rules that changed after you read them are flagged automatically.
- **Money arithmetic done right:** currency conversion with a stress margin, family uplifts, yearly-to-monthly bars, gross versus net mismatch warnings, months of proof, savings minimums.
- **Document countdown:** for each document, the earliest useful order date (so it has not expired) and the latest start date (so it is ready), counted back from the submission date.
- **Days on the ground:** calendar-year and rolling-twelve-month day counts against each country's tax residence threshold, with the date you would cross it.
- **Goal-aware ranking:** routes sorted by fastest permanent residence, fastest citizenship, or earliest submission for a trial move.
- **No dependencies:** one standard-library Python script with 54 tests.

## Installation

Copy the folder into the place your agent reads skills from.

| Agent | Where to put it |
|---|---|
| Claude Code | `~/.claude/skills/residence-route-check/` (personal) or `.claude/skills/residence-route-check/` (project) |
| Codex CLI | `~/.codex/skills/residence-route-check/` or reference `SKILL.md` from your `AGENTS.md` |
| Cursor | `.cursor/skills/residence-route-check/`, or point a project rule at `SKILL.md` |
| Other agents | Load `SKILL.md` (or `SKILL.zh-CN.md`) as instructions and make `scripts/routecheck.py` available |

```bash
git clone https://github.com/fangdididi/residence-route-check.git ~/.claude/skills/residence-route-check
```

Python 3.9 or newer is enough for the script.

## Usage

Ask your agent in plain words, for example:

- "We are two adults and a kid with Chinese passports, earning about 36k CNY a month remotely. Which residence routes in Europe could actually work for a move next summer?"
- "Check whether this nomad visa from a blog fits me, and what I must verify on the official site."
- "When do I need to order my police certificate if I want to submit in March?"

The agent asks for the household facts once, reads the official pages, writes a case file and runs the script:

```bash
python3 scripts/routecheck.py template > case.json      # starting point
python3 scripts/routecheck.py check case.json --out route-sheet.md
python3 scripts/routecheck.py check case.json --json     # machine-readable
```

## Example

`examples/family-of-three.json` uses invented countries and numbers. Part of the resulting sheet:

| Route | Verdict | Why |
|---|---|---|
| Eastvale skilled-work card | AFTER CHANGE | needs a job offer; 283 EUR/month short after currency stress; eligibility page read before a rule change |
| Northland remote-work residence | AFTER CHANGE | two more months of income proof; only 11% headroom; insurance unconfirmed |
| Southmark digital nomad visa | BLOCKED | passport not on the list; ends in leaving; only a blog as source |

It also shows that a June to December stay crosses a 183-day calendar-year threshold on 1 December. The full output is in `examples/family-of-three.sheet.md`.

## Case file at a glance

| Section | What goes in it |
|---|---|
| `as_of`, `stale_days`, `headroom_pct` | the check date, how old a source may be, the income margin you want |
| `rates` | value of one unit of each currency in a shared base, with where you got them |
| `household` | passports, adults, children, income (amount, currency, gross/net, months of proof), savings, goal, target move date, currency stress |
| `routes[]` | eligibility lists, income and savings rules, requirements (met / not met / unknown, changeable or not), exit path, years to PR and citizenship, submission lead time, sources |
| `documents[]` | name, which routes need it, preparation days, validity days, issue date if already issued |
| `trips[]`, `tax_rules[]` | planned stays, and each country's day threshold and counting window |

## File structure

```
residence-route-check/
├── SKILL.md                 # skill instructions (English)
├── SKILL.zh-CN.md           # skill instructions (Chinese)
├── README.md                # this file
├── README.zh-CN.md          # Chinese README
├── LICENSE
├── scripts/
│   └── routecheck.py        # gates, document clock, day counts, Markdown/JSON output
├── examples/
│   ├── family-of-three.json       # example case (invented data)
│   └── family-of-three.sheet.md   # resulting route sheet
└── tests/
    └── test_routecheck.py   # 54 unit and end-to-end tests
```

Run the tests with `python3 -m unittest discover -s tests`.

## License

MIT, see [LICENSE](LICENSE).
