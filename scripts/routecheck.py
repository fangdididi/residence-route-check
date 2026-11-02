#!/usr/bin/env python3
"""routecheck.py - arithmetic and bookkeeping for a residence route sheet.

Reads one case file (JSON) describing a household, the candidate residence
routes, the documents those routes need and the planned trips. Prints a route
sheet in Markdown (or JSON) with a verdict per route:

  FITS NOW      every gate passes on verified, fresh evidence
  HYPOTHESIS    nothing blocks it, but some fact is unverified or stale
  AFTER CHANGE  it works only if something real changes (income, wait, degree...)
  BLOCKED       a gate the household cannot change (e.g. passport not eligible)

Standard library only. No network access: verifying sources is your job,
this script only checks that you did it and that the dates line up.
"""
import argparse
import datetime as dt
import json
import sys

VERDICT_ORDER = ["BLOCKED", "AFTER CHANGE", "HYPOTHESIS", "FITS NOW"]
DEFAULT_STALE_DAYS = 60
DEFAULT_HEADROOM_PCT = 20
KEY_CLAIMS = ("eligibility", "income")


def parse_date(s):
    return dt.date.fromisoformat(s) if s else None


def fmt_money(x, cur):
    return f"{x:,.0f} {cur}"


# ---------------------------------------------------------------- money gate
def to_currency(amount, src, dst, rates):
    """rates map currency -> value of one unit in a shared base currency."""
    if src == dst:
        return amount
    if src not in rates or dst not in rates:
        raise KeyError(f"missing exchange rate for {src} or {dst}")
    return amount * rates[src] / rates[dst]


def required_income(rule, adults, children):
    factor = 1.0
    factor += rule.get("adult_uplift_pct", 0) / 100.0 * max(adults - 1, 0)
    factor += rule.get("child_uplift_pct", 0) / 100.0 * max(children, 0)
    return rule["amount"] * factor


def income_gate(route, hh, rates, headroom_pct):
    """Return (status, notes, changes). status in ok/thin/short/unknown/na."""
    rule = route.get("income")
    if not rule:
        return "na", [], []
    inc = hh.get("monthly_income")
    if not inc:
        return "unknown", ["household income not recorded"], []
    cur = rule["currency"]
    need = required_income(rule, hh.get("adults", 1), hh.get("children", 0))
    if rule.get("per", "month") == "year":
        need = need / 12.0
    have = to_currency(inc["amount"], inc["currency"], cur, rates)
    stress = hh.get("fx_stress_pct", 10) if inc["currency"] != cur else 0
    stressed = have * (1 - stress / 100.0)
    notes, changes = [], []
    notes.append(
        f"needs {fmt_money(need, cur)}/month for {hh.get('adults', 1)} adult(s) + "
        f"{hh.get('children', 0)} child(ren); you show {fmt_money(stressed, cur)}"
        + (f" after a {stress}% currency stress" if stress else "")
    )
    status = None
    if rule.get("basis") == "net" and inc.get("basis") == "gross":
        notes.append("route counts NET income but yours is recorded GROSS: convert before trusting this")
        status = "unknown"
    months_req = rule.get("months_required", 0)
    months_have = inc.get("months_documented", 0)
    if months_have < months_req:
        changes.append(f"document {months_req - months_have} more month(s) of income (have {months_have}, need {months_req})")
    if stressed < need:
        changes.append(f"raise documented income by {fmt_money(need - stressed, cur)}/month (or add a sponsor the route accepts)")
        return "short", notes, changes
    margin = (stressed / need - 1) * 100 if need else 100.0
    notes.append(f"headroom {margin:.0f}% (target {headroom_pct}%)")
    if status == "unknown":
        return status, notes, changes
    return ("ok" if margin >= headroom_pct else "thin"), notes, changes


def savings_gate(route, hh, rates):
    rule = route.get("savings_min")
    if not rule:
        return "na", [], []
    sv = hh.get("savings")
    if not sv:
        return "unknown", ["household savings not recorded"], []
    have = to_currency(sv["amount"], sv["currency"], rule["currency"], rates)
    if have < rule["amount"]:
        gap = rule["amount"] - have
        return "short", [f"savings {fmt_money(have, rule['currency'])} vs {fmt_money(rule['amount'], rule['currency'])}"], [
            f"show {fmt_money(gap, rule['currency'])} more in savings with a traceable source"]
    return "ok", [f"savings {fmt_money(have, rule['currency'])} cover {fmt_money(rule['amount'], rule['currency'])}"], []


# ------------------------------------------------------------ passport gate
def passport_gate(route, hh):
    passports = set(hh.get("passports", []))
    allowed = route.get("allowed_passports")
    excluded = set(route.get("excluded_passports", []))
    usable = {p for p in passports if (allowed is None or p in allowed) and p not in excluded}
    if usable:
        return "ok", sorted(usable)
    return "blocked", []


# ------------------------------------------------------------- source gate
def source_gate(route, as_of, stale_days):
    """Every key claim needs an official source fetched recently and after any known rule change."""
    problems = []
    srcs = route.get("sources", [])
    for claim in KEY_CLAIMS + tuple(route.get("extra_key_claims", [])):
        if claim == "income" and not route.get("income"):
            continue
        cands = [s for s in srcs if s.get("claim") == claim]
        official = [s for s in cands if s.get("kind") == "official"]
        if not cands:
            problems.append(f"no source at all for '{claim}'")
            continue
        if not official:
            problems.append(f"'{claim}' rests only on secondary sources (agent blog, forum, handbook)")
            continue
        best = max(official, key=lambda s: s.get("fetched", ""))
        fetched = parse_date(best.get("fetched"))
        if fetched is None:
            problems.append(f"official source for '{claim}' has no fetched date")
            continue
        age = (as_of - fetched).days
        if age > stale_days:
            problems.append(f"official source for '{claim}' is {age} days old (limit {stale_days})")
        changed = parse_date(best.get("rule_changed_after"))
        if changed and changed > fetched:
            problems.append(f"rules for '{claim}' changed on {changed}, after you last read them on {fetched}")
    return problems


# --------------------------------------------------------- document clock
def document_clock(docs, route_id, submit_date, as_of):
    rows = []
    for d in docs:
        scope = d.get("routes", "*")
        if scope != "*" and route_id not in scope:
            continue
        lead = d.get("lead_days", 0)
        valid = d.get("valid_days")
        start_by = submit_date - dt.timedelta(days=lead)
        not_before = submit_date - dt.timedelta(days=valid) if valid else None
        issued = parse_date(d.get("issued"))
        status = "todo"
        if issued:
            if valid and issued + dt.timedelta(days=valid) < submit_date:
                status = "expires before submission"
            else:
                status = "ready"
        elif as_of > start_by:
            status = "late"
        elif not_before and not_before > start_by:
            status = "window too narrow"
        rows.append({
            "document": d["name"],
            "order_after": str(not_before) if not_before else "any time",
            "start_by": str(start_by),
            "status": status,
        })
    return rows


# --------------------------------------------------------- presence/tax
def days_by_country(trips):
    days = {}
    for t in trips:
        a, b = parse_date(t["from"]), parse_date(t["to"])
        d = a
        while d <= b:
            days.setdefault(t["country"], set()).add(d)
            d += dt.timedelta(days=1)
    return days


def presence_report(trips, tax_rules):
    days = days_by_country(trips)
    out = []
    for rule in tax_rules:
        c = rule["country"]
        ds = sorted(days.get(c, set()))
        thr = rule.get("threshold_days", 183)
        window = rule.get("window", "calendar")
        crossed = None
        if window == "calendar":
            per_year = {}
            for d in ds:
                per_year[d.year] = per_year.get(d.year, 0) + 1
                if per_year[d.year] > thr and crossed is None:
                    crossed = d
            peak = max(per_year.values()) if per_year else 0
        else:
            peak, j = 0, 0
            for i, d in enumerate(ds):
                while ds[j] <= d - dt.timedelta(days=365):
                    j += 1
                n = i - j + 1
                peak = max(peak, n)
                if n > thr and crossed is None:
                    crossed = d
        out.append({"country": c, "window": window, "threshold": thr, "peak_days": peak,
                    "crosses_on": str(crossed) if crossed else None})
    return out


# --------------------------------------------------------------- verdict
def check_route(route, case, as_of):
    hh = case["household"]
    rates = case.get("rates", {})
    stale = case.get("stale_days", DEFAULT_STALE_DAYS)
    headroom = case.get("headroom_pct", DEFAULT_HEADROOM_PCT)
    blocks, changes, unknowns, notes = [], [], [], []

    p_status, usable = passport_gate(route, hh)
    if p_status == "blocked":
        blocks.append("no passport in the household is eligible for this route")
    else:
        notes.append("eligible passport(s): " + ", ".join(usable))

    s, n, c = income_gate(route, hh, rates, headroom)
    notes += n
    changes += c
    if s == "unknown":
        unknowns.append("income cannot be compared yet")
    if s == "thin":
        notes.append("THIN MARGIN: a pay cut, currency swing or annual threshold update could tip this over")

    s, n, c = savings_gate(route, hh, rates)
    notes += n
    changes += c
    if s == "unknown":
        unknowns.append("savings not recorded")

    for req in route.get("requirements", []):
        met = req.get("met")
        if met is False:
            if req.get("changeable", True):
                changes.append(f"meet: {req['text']}")
            else:
                blocks.append(f"cannot meet: {req['text']}")
        elif met is None:
            unknowns.append(f"unconfirmed: {req['text']}")

    goal = hh.get("goal")
    exit_path = route.get("exit", "unknown")
    if goal in ("permanent_residence", "citizenship") and exit_path == "leave":
        changes.append("this route ends in leaving; pair it with a second route that converts, or accept it as a trial year")
    if exit_path == "unknown":
        unknowns.append("what happens when the permit ends (renew / convert / leave) is not known")

    unknowns += source_gate(route, as_of, stale)

    if blocks:
        verdict = "BLOCKED"
    elif changes:
        verdict = "AFTER CHANGE"
    elif unknowns:
        verdict = "HYPOTHESIS"
    else:
        verdict = "FITS NOW"

    target = parse_date(hh.get("target_move"))
    submit = target - dt.timedelta(days=route.get("submit_days_before_move", 0)) if target else None
    docs = document_clock(case.get("documents", []), route["id"], submit, as_of) if submit else []
    if verdict == "FITS NOW" and any(d["status"] in ("late", "expires before submission", "window too narrow") for d in docs):
        verdict = "AFTER CHANGE"
        changes.append("move the target date: at least one document cannot be ready in time")

    clock = {}
    if target:
        for k in ("pr_years", "citizenship_years"):
            if route.get(k) is not None:
                y = route[k]
                clock[k] = str(target.replace(year=target.year + int(y))) if float(y).is_integer() else f"~{y} years after arrival"
    return {
        "id": route["id"], "name": route.get("name", route["id"]), "country": route.get("country", "?"),
        "verdict": verdict, "blocks": blocks, "changes": changes, "unknowns": unknowns, "notes": notes,
        "submit_by": str(submit) if submit else None, "documents": docs, "clock": clock, "exit": exit_path,
    }


def goal_key(r, goal):
    rank = VERDICT_ORDER.index(r["verdict"])
    if goal == "permanent_residence":
        return (-rank, r["clock"].get("pr_years", "9999"))
    if goal == "citizenship":
        return (-rank, r["clock"].get("citizenship_years", "9999"))
    return (-rank, r["submit_by"] or "9999")


def run(case):
    as_of = parse_date(case.get("as_of")) or dt.date.today()
    goal = case["household"].get("goal", "try")
    results = [check_route(r, case, as_of) for r in case.get("routes", [])]
    results.sort(key=lambda r: goal_key(r, goal))
    results.sort(key=lambda r: -VERDICT_ORDER.index(r["verdict"]))
    presence = presence_report(case.get("trips", []), case.get("tax_rules", []))
    return {"as_of": str(as_of), "household": case["household"].get("label", "household"), "goal": goal,
            "routes": results, "presence": presence}


# --------------------------------------------------------------- render
def render(rep):
    L = [f"# Route sheet: {rep['household']}", "",
         f"As of {rep['as_of']} · goal: {rep['goal']} · not legal or tax advice; every rule must be re-read on the official page before acting.", "",
         "| Route | Country | Verdict | Submit by | PR from | Citizenship from | Exit |", "|---|---|---|---|---|---|---|"]
    for r in rep["routes"]:
        L.append(f"| {r['name']} | {r['country']} | **{r['verdict']}** | {r['submit_by'] or '-'} | "
                 f"{r['clock'].get('pr_years', '-')} | {r['clock'].get('citizenship_years', '-')} | {r['exit']} |")
    for r in rep["routes"]:
        L += ["", f"## {r['name']} ({r['country']}): {r['verdict']}", ""]
        for title, key in (("Blocks", "blocks"), ("What would have to change", "changes"),
                           ("Still to verify", "unknowns"), ("Working", "notes")):
            if r[key]:
                L.append(f"**{title}**")
                L += [f"- {x}" for x in r[key]]
                L.append("")
        if r["documents"]:
            L += ["| Document | Order after | Start by | Status |", "|---|---|---|---|"]
            L += [f"| {d['document']} | {d['order_after']} | {d['start_by']} | {d['status']} |" for d in r["documents"]]
    if rep["presence"]:
        L += ["", "## Days on the ground and tax residence", "",
              "| Country | Window | Threshold | Peak days | Crosses on |", "|---|---|---|---|---|"]
        for p in rep["presence"]:
            L.append(f"| {p['country']} | {p['window']} | {p['threshold']} | {p['peak_days']} | {p['crosses_on'] or 'not crossed'} |")
        L += ["", "A residence permit and tax residence are separate questions: crossing a day threshold can make you taxable even on a visitor stay."]
    return "\n".join(L) + "\n"


TEMPLATE = {
    "as_of": "2026-11-02",
    "stale_days": 60,
    "headroom_pct": 20,
    "rates": {"EUR": 1.0, "USD": 0.9},
    "household": {"label": "EXAMPLE household", "passports": ["AA"], "adults": 1, "children": 0,
                  "monthly_income": {"amount": 4000, "currency": "USD", "basis": "gross", "months_documented": 6},
                  "savings": {"amount": 20000, "currency": "EUR"}, "goal": "permanent_residence",
                  "target_move": "2027-04-01", "fx_stress_pct": 10},
    "routes": [{"id": "example-remote", "name": "EXAMPLE remote-work permit", "country": "Exampleland",
                "allowed_passports": None, "excluded_passports": [],
                "income": {"amount": 2500, "currency": "EUR", "basis": "gross", "per": "month",
                           "adult_uplift_pct": 50, "child_uplift_pct": 20, "months_required": 6},
                "requirements": [{"text": "clean criminal record", "met": True}],
                "exit": "renew", "pr_years": 5, "citizenship_years": 10, "submit_days_before_move": 45,
                "sources": [{"claim": "eligibility", "kind": "official", "url": "https://example.org/permit", "fetched": "2026-10-30"},
                            {"claim": "income", "kind": "official", "url": "https://example.org/permit#income", "fetched": "2026-10-30"}]}],
    "documents": [{"name": "police certificate", "routes": "*", "lead_days": 30, "valid_days": 90}],
    "trips": [{"country": "Exampleland", "from": "2027-04-01", "to": "2027-12-31"}],
    "tax_rules": [{"country": "Exampleland", "threshold_days": 183, "window": "calendar"}],
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a case file and print the route sheet")
    c.add_argument("case")
    c.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    c.add_argument("--out", help="also write the output to this file")
    sub.add_parser("template", help="print a blank example case file")
    a = ap.parse_args(argv)
    if a.cmd == "template":
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    with open(a.case, encoding="utf-8") as f:
        case = json.load(f)
    rep = run(case)
    text = json.dumps(rep, indent=2, ensure_ascii=False) if a.json else render(rep)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
