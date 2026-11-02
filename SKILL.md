---
name: residence-route-check
description: Turn "where could I legally move?" into a dated route sheet for one person or family. Use when someone is weighing a move abroad (digital nomad, skilled work, study-to-work, self-employed, passive income, investment residence) and needs each candidate route checked against their passports, real income, documents, deadlines and long-term goal, with every rule tied to an official page read recently. Produces FITS NOW / HYPOTHESIS / AFTER CHANGE / BLOCKED verdicts, a document countdown and a days-on-the-ground tax warning.
---

# Residence Route Check

## What this is

Moving countries is mostly a paperwork and arithmetic problem wearing a lifestyle costume. People pick a country from a video, then discover in month three that their passport is not on the list, that the income bar is per family and not per person, that the police certificate they ordered in spring expired before the appointment, or that the visa they chose cannot turn into permanent residence at all.

This skill makes the agent work like a careful case officer on the household's side. It does not recommend "the best country". It takes the household as it really is, lists the candidate routes, and runs each one through the same gates in the same order. Every rule that matters must point to an official page with the date it was read, because residence rules change often and old guides go stale quickly. The output is a **route sheet**: one verdict per route, what would have to change to flip it, what is still unverified, when each document must be ordered, and when time spent in the new country starts to make you a tax resident.

The helper script `scripts/routecheck.py` does the parts people get wrong by hand: currency conversion with a stress margin, family uplifts on income bars, monthly versus yearly thresholds, document validity windows counted backwards from the submission date, and day counts under calendar-year and rolling-twelve-month rules.

This is not legal, tax or immigration advice, and the skill must say so once, plainly, in the sheet.

## When to use it

- "We want to move to Europe / Asia / anywhere in the next year. Which routes are actually open to us?"
- "Is the digital nomad visa or the skilled-work card better for my family?"
- "Can I still make the March deadline if I start the documents now?"
- "I found a route on a blog. Is it real and does it fit me?"
- "If I spend autumn there and winter at home, do I become a tax resident?"

Do not use it for a tourist visa for a short trip, for an asylum or protection claim (point the person to a qualified lawyer or a recognised legal aid organisation immediately), or for anything that involves hiding facts from an authority.

## The five gates

Run every candidate route through these gates in this order. A route stops being worth detailed work as soon as it hits a gate it cannot pass.

1. **Passport gate.** Which passports in the household are eligible? Many routes publish a nationality list, an exclusion list, or a condition like "employer must be based in a listed country". A second passport, an existing residence permit, or a family tie can open a route the main passport does not. If no passport works and nothing can change that, the route is BLOCKED.
2. **Money gate.** Convert the household's documented income to the route's currency, subtract a currency stress margin (default 10% when currencies differ), apply uplifts for each extra adult and child, and turn yearly bars into monthly ones. Aim for at least 20% headroom: thresholds are revised yearly and exchange rates move. Check whether the route counts gross or net income and how many months of proof it needs. Savings minimums are checked separately.
3. **Requirement gate.** Degree recognition, job offer, clean record, insurance, language, business plan, accommodation. Mark each as met, not met but changeable, not met and unchangeable, or unknown.
4. **Clock gate.** Count backwards from the target move date: the route's submission lead time, then each document's preparation time (notarisation, apostille, sworn translation, credential evaluation, appointment waits) and validity window. A police certificate ordered too early expires; one ordered too late is not ready.
5. **Goal gate.** Does the route lead where the household wants to end up? A one-year nomad visa that cannot be renewed or converted is fine for a trial year and a dead end for someone whose goal is permanent residence. Note years to permanent residence and to citizenship, and whether the current nationality allows dual citizenship.

Then, separately, **days on the ground**: list planned stays and test them against each country's tax residence rule (calendar year or rolling twelve months, usually around 183 days, sometimes much less). A residence permit and tax residence are different questions.

## Evidence rules

- Every key claim (eligibility and the income bar at minimum, plus anything else the decision hinges on, such as fees or processing time) needs a source with: the claim it supports, `official` or `secondary`, the URL, and the date you read it.
- Only official pages (government immigration, tax or consular sites, or the law itself) can make a route FITS NOW. Agent blogs, forums, handbooks and videos are leads, not proof.
- A source older than the stale limit (default 60 days) or read before a known rule change turns the route into a HYPOTHESIS until it is read again.
- Never fill a gap with a remembered number. If you cannot fetch the official page, write the claim as unknown.
- Record the household's facts exactly as given. Do not round income up, invent months of proof, or soften a refusal history.

## Verdicts

| Verdict | Meaning |
|---|---|
| FITS NOW | Every gate passes on fresh official evidence and the documents can be ready in time. |
| HYPOTHESIS | Nothing blocks it, but something is unverified, stale, or recorded on a different income basis. Lists exactly what to check. |
| AFTER CHANGE | Works only if something real changes: more income, more months of proof, a job offer, a later move date, a second route to convert into. Lists each change. |
| BLOCKED | A gate the household cannot change, most often nationality. |

A single unchangeable block wins over everything else. Among routes with the same verdict, sort by the household's goal: fastest permanent residence, fastest citizenship, or simply earliest possible submission for a trial move.

## Step by step

1. **Household card.** Ask once, in one batch, for: every passport held by each person, number of adults and children, income (amount, currency, gross or net, months of proof available), savings, current residence, goal (`try`, `permanent_residence`, `citizenship`), target move date, and any prior refusals or criminal records. A prior refusal, a record, a custody question or sanctions exposure means: say early that a licensed specialist should look at the case.
2. **Candidate routes.** Gather three to six candidates from the household's real situation (income source decides most of it: local employer, remote employer or clients, own business, passive income, study, investment). Include at least one the person did not mention if it plausibly fits.
3. **Read the official pages.** For each route, fetch the official page and record eligibility, income bar (amount, currency, basis, per month or year, family uplifts, months of proof), savings minimum, other requirements, what happens at expiry, years to permanent residence and citizenship, and how long before moving the application must go in. Note the date you read each page.
4. **Write the case file.** Use `python3 scripts/routecheck.py template > case.json` as a starting point. Add current exchange rates (state where they came from), the documents list with lead times and validity, planned trips, and the tax residence rule for each country you will spend time in.
5. **Run the sheet.** `python3 scripts/routecheck.py check case.json --out route-sheet.md`. Read every "Still to verify" line and go fetch what is missing before you present anything as settled.
6. **Present.** Lead with the verdict table. For each route: what blocks it, what would have to change, what is still unverified. Then the document countdown for the leading route, then the days-on-the-ground table. Close with the next three concrete actions and their dates.
7. **Revisit.** Re-run whenever the household's facts change, a source passes the stale limit, or the person is about to pay for anything (lawyer, translations, flights, a lease).

## Example

A family of two adults and one child, Chinese passports, 36,000 CNY gross per month with four months of payslips, aiming for permanent residence and a June move. Three candidates come back:

- A skilled-work card: AFTER CHANGE. It needs a local job offer, the income is 283 EUR a month short once the currency stress is applied, and the eligibility page was read before a rule change, so it must be read again.
- A remote-work residence: AFTER CHANGE. The money passes with only 11% headroom (flagged thin), two more months of income proof are needed, and insurance is unconfirmed. Police certificates should be ordered between early January and late February.
- A digital nomad visa found on a blog: BLOCKED. The nationality list does not include the household's passport, it ends in leaving, and its only source is secondary.

The days-on-the-ground table shows that the planned June to December stay crosses a 183-day calendar-year threshold on 1 December, so tax residence planning starts now, not after arrival.

The complete input and output live in `examples/` and use invented countries and numbers on purpose.

## Tips

- The income source decides the route family far more than the destination does. Start there.
- "Per family" bars are the most common surprise. Always enter every adult and child.
- Gross versus net mismatches are not rounding errors. Convert before trusting a pass.
- Ask which apostille, translation and validity rules the receiving office applies; joining a convention does not stop a country adding its own format rules.
- Keep names spelled identically across passports, degrees, contracts and bank records. Mismatches cause more delays than missing documents.
- A route that fits now with thin headroom deserves a plan B, because thresholds are usually updated every year.
- Never help anyone misstate facts, fake documents or arrange a sham job or marriage. Say no and explain the risk of a ban.
