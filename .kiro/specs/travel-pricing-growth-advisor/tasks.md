# Implementation Plan — Travel Pricing & Growth Advisor

Built in functioning layers: each phase leaves the project runnable and testable on its own.

- [x] 1. Project scaffold and Kiro artifacts
  - [x] 1.1 Init repo, `.gitignore`, README, steering files
  - [x] 1.2 Write spec (requirements, design, tasks)
  - [x] 1.3 Create `data/` seed datasets (routes, events) — _Req 1.1–1.4_

- [x] 2. Backend core (pure, deterministic) + tests
  - [x] 2.1 `models.py` — dataclasses (Route, Market, Event, Factor, PriceResult, ...) — _Req 2.1_
  - [x] 2.2 `data.py` — offline loaders (holidays lib + `data/` files), skip malformed — _Req 1.1–1.4_
  - [x] 2.3 `pricing.py` — pure pricing engine with clamp + factors — _Req 2.1–2.7_
  - [x] 2.4 `growth.py` — opportunity score, allocation, ranking — _Req 3.1–3.5_
  - [x] 2.5 `storyline.py` — business-language insights from results — _Req 4.1–4.3_
  - [x] 2.6 Example-based `pytest` tests for pricing and growth

- [x] 3. Property-based testing (Lesson 4) — _Req 2.2–2.7, 3.1–3.5_
  - [x] 3.1 `hypothesis` strategies for routes/dates/holidays/events
  - [x] 3.2 Pricing properties P1–P5
  - [x] 3.3 Growth properties G1–G5

- [x] 4. API layer — _Req 5.1–5.3_
  - [x] 4.1 `api.py` handlers: validate input, call core, shape JSON
  - [x] 4.2 Local runner to serve the API for the frontend during dev

- [x] 5. Infrastructure as code (CDK v2, TypeScript) — _Req 7.1–7.3_
  - [x] 5.1 CDK app + `TravelAdvisorStack` (S3, 2 Lambdas, API Gateway, DynamoDB)
  - [x] 5.2 `npm run synth` script; verify a valid template is produced (no creds)

- [x] 6. Frontend dashboard (React + Vite) — _Req 6.1–6.4_
  - [x] 6.1 Route/period/market selector + pricing calendar with factor tooltips
  - [ ] 6.2 Events & demand timeline (basic uplift shown via calendar heat; dedicated timeline is a polish item)
  - [x] 6.3 Growth opportunity board with allocations
  - [x] 6.4 Storyline view

- [x] 7. Kiro feature coverage for the exam
  - [x] 7.1 Hooks: pytest on backend save, tsc on frontend save, cdk synth on infra save — _Lesson 3_
  - [x] 7.2 Custom agents: `travel-data-analyst`, `aws-infra-reviewer` — _Lesson 7_
  - [x] 7.3 MCP: configure a `fetch` server for optional event enrichment — _Lesson 6_
  - [x] 7.4 Power: package skill + MCP as `travel-growth-toolkit` — _Bonus 2_
  - [x] 7.5 Kiro Powers usage documented (Lesson 5); cloud session optional (Bonus 1)

- [x] 8. Presentation polish
  - [x] 8.1 Architecture diagram + screenshots in README
  - [x] 8.2 Final pass: all tests green, `cdk synth` clean, storyline demo-ready
  - [x] 8.3 Richer datasets (12 routes, 41 events Oct 2026 – mid 2027, per-market ads data)

- [ ] 9. Pricing engine v2 — day-to-day differentiation — _Req 2.5, 2.6, 2.8–2.10_
  - [x] 9.1 Day-of-week multipliers (data-driven) so quiet weeks are not flat
  - [x] 9.2 Event proximity gradient (impact fades with distance) instead of an on/off step
  - [x] 9.3 Optional lead-time (advance-purchase) curve kept as a pure capability, not used by
        the calendar (the user compares departure dates, not booking horizons)
  - [x] 9.4 `price_breakdown`: EUR / % contribution per factor + guardrail line; B1 invariant
  - [x] 9.5 Property P4 revised to `[seasonality, day_of_week]`; P6 added

- [ ] 10. Profit optimiser — elasticity + capacity — _Req 2b.1–2b.7, 5.4–5.5_
  - [x] 10.1 `Route.seats` / `Route.segment` in `routes.json`; `elasticity_by_segment`,
        `base_demand_per_seat`, `marginal_cost_ratio` in `pricing-rules.json`
  - [x] 10.2 `demand.py`: constant-elasticity demand, markup `c·e/(e−1)`, market-clearing
        price, profit `(p−c)·min(demand, seats)`, deterministic grid + analytical candidates
  - [x] 10.3 `/optimize` endpoint (single day and `days=N` range), 400 on bad `days`
  - [x] 10.4 Properties D1–D5, C1–C3, E1 + example tests (markup vs clearing, segments)
  - [x] 10.5 Calibrate defaults so leisure routes are capacity-bound and business routes sit
        at the markup (two explainable regimes)
  - [x] 10.6 Spec (requirements/design) aligned with the real model

- [x] 11. Dashboard v2 — explainability for a business stakeholder — _Req 6.5–6.7_
  - [x] 11.1 Calendar toggle: rule-based vs profit-optimal price; capacity-bound badge; load
        factor and uplift (one `/optimize?days=N` call feeds the whole calendar)
  - [x] 11.2 Breakdown ledger (EUR / %) for the selected day
  - [x] 11.3 Scenario compare: second route or date side by side with "why it differs"

- [x] 12. Advisor narrative — _Req 4.1–4.3_
  - [x] 12.1 `advisor_insights`: insight + action + evidence (peak → campaign date from
        `campaign_lead_days`; capacity-bound days; period profit uplift; weekday pattern;
        quiet window). A peak needs a real event/holiday driver, never just a busy Friday.
  - [x] 12.2 `/report` Markdown one-pager export (consulting-style), download link in UI
