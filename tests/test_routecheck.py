import copy
import datetime as dt
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import routecheck as rc  # noqa: E402

D = dt.date.fromisoformat


def base_case():
    return copy.deepcopy(rc.TEMPLATE)


def route_of(case, **kw):
    r = case["routes"][0]
    r.update(kw)
    return r


class Money(unittest.TestCase):
    def test_same_currency_no_conversion(self):
        self.assertEqual(rc.to_currency(100, "EUR", "EUR", {}), 100)

    def test_conversion_through_base(self):
        self.assertAlmostEqual(rc.to_currency(100, "USD", "EUR", {"USD": 0.9, "EUR": 1.0}), 90)

    def test_missing_rate_raises(self):
        with self.assertRaises(KeyError):
            rc.to_currency(1, "GBP", "EUR", {"EUR": 1})

    def test_uplift_for_family(self):
        rule = {"amount": 1000, "adult_uplift_pct": 50, "child_uplift_pct": 20}
        self.assertAlmostEqual(rc.required_income(rule, 2, 2), 1000 * (1 + 0.5 + 0.4))

    def test_single_adult_no_uplift(self):
        self.assertEqual(rc.required_income({"amount": 1000, "adult_uplift_pct": 50}, 1, 0), 1000)

    def test_fx_stress_applied_only_across_currencies(self):
        case = base_case()
        case["household"]["monthly_income"] = {"amount": 3000, "currency": "EUR", "basis": "gross", "months_documented": 6}
        s, notes, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertIn("3,000 EUR", notes[0])
        self.assertNotIn("stress", notes[0])

    def test_short_income_gives_change(self):
        case = base_case()
        case["household"]["monthly_income"]["amount"] = 2000
        s, _, ch = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertEqual(s, "short")
        self.assertTrue(any("raise documented income" in c for c in ch))

    def test_thin_margin(self):
        case = base_case()
        case["household"]["monthly_income"]["amount"] = 3000  # 3000*0.9*0.9 = 2430 < 2500
        s, _, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertEqual(s, "short")
        case["household"]["monthly_income"]["amount"] = 3300  # 2673 -> 6.9% headroom
        s, _, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertEqual(s, "thin")

    def test_ok_margin(self):
        case = base_case()
        s, _, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertEqual(s, "ok")

    def test_yearly_threshold_divided(self):
        case = base_case()
        case["routes"][0]["income"] = {"amount": 36000, "currency": "EUR", "per": "year"}
        _, notes, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertIn("3,000 EUR/month", notes[0])

    def test_months_documented(self):
        case = base_case()
        case["household"]["monthly_income"]["months_documented"] = 2
        _, _, ch = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertTrue(any("4 more month" in c for c in ch))

    def test_gross_vs_net_mismatch_unknown(self):
        case = base_case()
        case["routes"][0]["income"]["basis"] = "net"
        s, notes, _ = rc.income_gate(case["routes"][0], case["household"], case["rates"], 20)
        self.assertEqual(s, "unknown")
        self.assertTrue(any("NET" in n for n in notes))

    def test_no_income_rule(self):
        case = base_case()
        del case["routes"][0]["income"]
        self.assertEqual(rc.income_gate(case["routes"][0], case["household"], {}, 20)[0], "na")

    def test_missing_household_income(self):
        case = base_case()
        del case["household"]["monthly_income"]
        self.assertEqual(rc.income_gate(case["routes"][0], case["household"], {}, 20)[0], "unknown")

    def test_savings(self):
        case = base_case()
        r = case["routes"][0]
        r["savings_min"] = {"amount": 30000, "currency": "EUR"}
        s, _, ch = rc.savings_gate(r, case["household"], case["rates"])
        self.assertEqual(s, "short")
        self.assertIn("10,000 EUR", ch[0])
        r["savings_min"]["amount"] = 10000
        self.assertEqual(rc.savings_gate(r, case["household"], case["rates"])[0], "ok")


class Passport(unittest.TestCase):
    def test_open_route(self):
        self.assertEqual(rc.passport_gate({"allowed_passports": None}, {"passports": ["AA"]}), ("ok", ["AA"]))

    def test_allow_list(self):
        self.assertEqual(rc.passport_gate({"allowed_passports": ["BB"]}, {"passports": ["AA"]})[0], "blocked")

    def test_second_passport_saves_it(self):
        self.assertEqual(rc.passport_gate({"allowed_passports": ["BB"]}, {"passports": ["AA", "BB"]}), ("ok", ["BB"]))

    def test_exclusion(self):
        self.assertEqual(rc.passport_gate({"excluded_passports": ["AA"]}, {"passports": ["AA"]})[0], "blocked")


class Sources(unittest.TestCase):
    def test_fresh_official_clean(self):
        case = base_case()
        self.assertEqual(rc.source_gate(case["routes"][0], D("2026-11-02"), 60), [])

    def test_stale(self):
        case = base_case()
        p = rc.source_gate(case["routes"][0], D("2027-03-01"), 60)
        self.assertTrue(any("days old" in x for x in p))

    def test_rule_changed_after_reading(self):
        case = base_case()
        case["routes"][0]["sources"][0]["rule_changed_after"] = "2026-10-31"
        p = rc.source_gate(case["routes"][0], D("2026-11-02"), 60)
        self.assertTrue(any("changed on" in x for x in p))

    def test_secondary_only(self):
        case = base_case()
        for s in case["routes"][0]["sources"]:
            s["kind"] = "secondary"
        p = rc.source_gate(case["routes"][0], D("2026-11-02"), 60)
        self.assertEqual(len(p), 2)
        self.assertTrue(all("secondary" in x for x in p))

    def test_missing_claim(self):
        case = base_case()
        case["routes"][0]["sources"] = case["routes"][0]["sources"][:1]
        p = rc.source_gate(case["routes"][0], D("2026-11-02"), 60)
        self.assertEqual(p, ["no source at all for 'income'"])

    def test_no_income_rule_no_income_source_needed(self):
        case = base_case()
        r = case["routes"][0]
        del r["income"]
        r["sources"] = r["sources"][:1]
        self.assertEqual(rc.source_gate(r, D("2026-11-02"), 60), [])

    def test_extra_key_claim(self):
        case = base_case()
        case["routes"][0]["extra_key_claims"] = ["fee"]
        p = rc.source_gate(case["routes"][0], D("2026-11-02"), 60)
        self.assertEqual(p, ["no source at all for 'fee'"])

    def test_missing_fetched_date(self):
        case = base_case()
        del case["routes"][0]["sources"][0]["fetched"]
        p = rc.source_gate(case["routes"][0], D("2026-11-02"), 60)
        self.assertTrue(any("no fetched date" in x for x in p))


class Documents(unittest.TestCase):
    docs = [{"name": "police", "routes": "*", "lead_days": 30, "valid_days": 90}]

    def test_window(self):
        rows = rc.document_clock(self.docs, "x", D("2027-04-01"), D("2026-11-02"))
        self.assertEqual(rows[0]["order_after"], "2027-01-01")
        self.assertEqual(rows[0]["start_by"], "2027-03-02")
        self.assertEqual(rows[0]["status"], "todo")

    def test_late(self):
        rows = rc.document_clock(self.docs, "x", D("2026-11-20"), D("2026-11-02"))
        self.assertEqual(rows[0]["status"], "late")

    def test_expired_before_submission(self):
        d = [dict(self.docs[0], issued="2026-10-01")]
        rows = rc.document_clock(d, "x", D("2027-04-01"), D("2026-11-02"))
        self.assertEqual(rows[0]["status"], "expires before submission")

    def test_ready(self):
        d = [dict(self.docs[0], issued="2027-02-01")]
        rows = rc.document_clock(d, "x", D("2027-04-01"), D("2027-02-02"))
        self.assertEqual(rows[0]["status"], "ready")

    def test_window_too_narrow(self):
        d = [{"name": "bank", "lead_days": 40, "valid_days": 30}]
        rows = rc.document_clock(d, "x", D("2027-04-01"), D("2026-11-02"))
        self.assertEqual(rows[0]["status"], "window too narrow")

    def test_route_scoping(self):
        d = [{"name": "degree", "routes": ["a"], "lead_days": 10}]
        self.assertEqual(rc.document_clock(d, "b", D("2027-04-01"), D("2026-11-02")), [])
        self.assertEqual(len(rc.document_clock(d, "a", D("2027-04-01"), D("2026-11-02"))), 1)


class Presence(unittest.TestCase):
    def test_calendar_split_across_years(self):
        trips = [{"country": "X", "from": "2027-09-01", "to": "2028-02-28"}]
        rep = rc.presence_report(trips, [{"country": "X", "threshold_days": 183, "window": "calendar"}])
        self.assertIsNone(rep[0]["crosses_on"])
        self.assertEqual(rep[0]["peak_days"], 122)

    def test_rolling_catches_it(self):
        trips = [{"country": "X", "from": "2027-09-01", "to": "2028-02-28"}]
        rep = rc.presence_report(trips, [{"country": "X", "threshold_days": 150, "window": "rolling12"}])
        self.assertEqual(rep[0]["crosses_on"], "2028-01-29")

    def test_overlapping_trips_not_double_counted(self):
        trips = [{"country": "X", "from": "2027-01-01", "to": "2027-01-10"},
                 {"country": "X", "from": "2027-01-05", "to": "2027-01-15"}]
        rep = rc.presence_report(trips, [{"country": "X", "threshold_days": 183}])
        self.assertEqual(rep[0]["peak_days"], 15)

    def test_unknown_country_zero(self):
        rep = rc.presence_report([], [{"country": "Y", "threshold_days": 183, "window": "rolling12"}])
        self.assertEqual(rep[0]["peak_days"], 0)


class Verdicts(unittest.TestCase):
    def check(self, case):
        return rc.check_route(case["routes"][0], case, rc.parse_date(case["as_of"]))

    def test_fits_now(self):
        self.assertEqual(self.check(base_case())["verdict"], "FITS NOW")

    def test_blocked_beats_everything(self):
        case = base_case()
        route_of(case, excluded_passports=["AA"])
        case["household"]["monthly_income"]["amount"] = 10
        self.assertEqual(self.check(case)["verdict"], "BLOCKED")

    def test_unchangeable_requirement_blocks(self):
        case = base_case()
        route_of(case, requirements=[{"text": "born before 1960", "met": False, "changeable": False}])
        self.assertEqual(self.check(case)["verdict"], "BLOCKED")

    def test_changeable_requirement(self):
        case = base_case()
        route_of(case, requirements=[{"text": "job offer", "met": False}])
        r = self.check(case)
        self.assertEqual(r["verdict"], "AFTER CHANGE")
        self.assertIn("meet: job offer", r["changes"])

    def test_unknown_requirement_hypothesis(self):
        case = base_case()
        route_of(case, requirements=[{"text": "insurance", "met": None}])
        self.assertEqual(self.check(case)["verdict"], "HYPOTHESIS")

    def test_stale_source_hypothesis(self):
        case = base_case()
        case["as_of"] = "2027-02-01"
        self.assertEqual(self.check(case)["verdict"], "HYPOTHESIS")

    def test_dead_end_for_pr_goal(self):
        case = base_case()
        route_of(case, exit="leave")
        self.assertEqual(self.check(case)["verdict"], "AFTER CHANGE")

    def test_dead_end_fine_for_trial(self):
        case = base_case()
        case["household"]["goal"] = "try"
        route_of(case, exit="leave")
        self.assertEqual(self.check(case)["verdict"], "FITS NOW")

    def test_unknown_exit(self):
        case = base_case()
        route_of(case, exit="unknown")
        self.assertEqual(self.check(case)["verdict"], "HYPOTHESIS")

    def test_late_document_downgrades(self):
        case = base_case()
        case["household"]["target_move"] = "2026-12-01"
        r = self.check(case)
        self.assertEqual(r["verdict"], "AFTER CHANGE")
        self.assertTrue(any("target date" in c for c in r["changes"]))

    def test_clock(self):
        r = self.check(base_case())
        self.assertEqual(r["clock"]["pr_years"], "2032-04-01")
        self.assertEqual(r["submit_by"], "2027-02-15")

    def test_fractional_clock(self):
        case = base_case()
        route_of(case, pr_years=1.5)
        self.assertIn("1.5", self.check(case)["clock"]["pr_years"])


class EndToEnd(unittest.TestCase):
    def test_ordering(self):
        case = base_case()
        good = case["routes"][0]
        bad = dict(copy.deepcopy(good), id="b", name="B", excluded_passports=["AA"])
        mid = dict(copy.deepcopy(good), id="m", name="M", exit="leave")
        case["routes"] = [bad, mid, good]
        rep = rc.run(case)
        self.assertEqual([r["verdict"] for r in rep["routes"]], ["FITS NOW", "AFTER CHANGE", "BLOCKED"])

    def test_pr_goal_prefers_faster_pr(self):
        case = base_case()
        a = case["routes"][0]
        b = dict(copy.deepcopy(a), id="fast", name="Fast", pr_years=2)
        case["routes"] = [a, b]
        self.assertEqual(rc.run(case)["routes"][0]["id"], "fast")

    def test_render_contains_table_and_disclaimer(self):
        md = rc.render(rc.run(base_case()))
        self.assertIn("| Route | Country | Verdict", md)
        self.assertIn("not legal or tax advice", md)
        self.assertIn("tax residence", md)

    def test_example_file_runs(self):
        path = os.path.join(ROOT, "examples", "family-of-three.json")
        with open(path) as f:
            rep = rc.run(json.load(f))
        verdicts = {r["id"]: r["verdict"] for r in rep["routes"]}
        self.assertEqual(verdicts["southmark-nomad"], "BLOCKED")
        self.assertEqual(verdicts["eastvale-bluecard"], "AFTER CHANGE")
        self.assertEqual(verdicts["northland-remote"], "AFTER CHANGE")

    def test_cli_template_and_json(self):
        script = os.path.join(ROOT, "scripts", "routecheck.py")
        out = subprocess.run([sys.executable, script, "template"], capture_output=True, text=True, check=True).stdout
        tmp = os.path.join(HERE, "_tmp_case.json")
        try:
            with open(tmp, "w") as f:
                f.write(out)
            js = subprocess.run([sys.executable, script, "check", tmp, "--json"], capture_output=True, text=True, check=True).stdout
            self.assertEqual(json.loads(js)["routes"][0]["verdict"], "FITS NOW")
        finally:
            os.remove(tmp)


if __name__ == "__main__":
    unittest.main()
