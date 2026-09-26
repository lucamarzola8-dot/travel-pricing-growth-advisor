# Implementation Plan — Travel Pricing & Growth Advisor

Built in functioning layers: each phase leaves the project runnable and testable on its own.

- [ ] 1. Project scaffold and Kiro artifacts
  - [x] 1.1 Init repo, `.gitignore`, README, steering files
  - [x] 1.2 Write spec (requirements, design, tasks)
  - [ ] 1.3 Create `data/` seed datasets (routes, events) — _Req 1.1–1.4_

- [ ] 2. Backend core (pure, deterministic) + tests
  - [ ] 2.1 `models.py` — dataclasses (Route, Market, Event, Factor, PriceResult, ...) — _Req 2.1_
  - [ ] 2.2 `data.py` — offline loaders (holidays lib + `data/` files), skip malformed — _Req 1.1–1.4_
  - [ ] 2.3 `pricing.py` — pure pricing engine with clamp + factors — _Req 2.1–2.7_
  - [ ] 2.4 `growth.py` — opportunity score, allocation, ranking — _Req 3.1–3.5_
  - [ ] 2.5 `storyline.py` — business-language insights from results — _Req 4.1–4.3_
  - [ ] 2.6 Example-based `pytest` tests for pricing and growth

- [ ] 3. Property-based testing (Lesson 4) — _Req 2.2–2.7, 3.1–3.5_
  - [ ] 3.1 `hypothesis` strategies for routes/dates/holidays/events
  - [ ] 3.2 Pricing properties P1–P5
  - [ ] 3.3 Growth properties G1–G5

- [ ] 4. API layer — _Req 5.1–5.3_
  - [ ] 4.1 `api.py` handlers: validate input, call core, shape JSON
  - [ ] 4.2 Local runner to serve the API for the frontend during dev

- [ ] 5. Infrastructure as code (CDK v2, TypeScript) — _Req 7.1–7.3_
  - [ ] 5.1 CDK app + `TravelAdvisorStack` (S3, 2 Lambdas, API Gateway, DynamoDB)
  - [ ] 5.2 `npm run synth` script; verify a valid template is produced (no creds)

- [ ] 6. Frontend dashboard (React + Vite) — _Req 6.1–6.4_
  - [ ] 6.1 Route/period/market selector + pricing calendar with factor tooltips
  - [ ] 6.2 Events & demand timeline
  - [ ] 6.3 Growth opportunity board with allocations
  - [ ] 6.4 Storyline view

- [ ] 7. Kiro feature coverage for the exam
  - [ ] 7.1 Hooks: run pytest on backend save, lint frontend on save — _Lesson 3_
  - [ ] 7.2 Custom agents: `travel-data-analyst`, `aws-infra-reviewer` — _Lesson 7_
  - [ ] 7.3 MCP: configure a server (e.g. fetch) for optional event enrichment — _Lesson 6_
  - [ ] 7.4 Power: package steering + hooks + MCP as `travel-growth-toolkit` — _Bonus 2_
  - [ ] 7.5 Kiro Powers usage (Lesson 5) and optional cloud session (Bonus 1)

- [ ] 8. Presentation polish
  - [ ] 8.1 Architecture diagram + screenshots in README
  - [ ] 8.2 Final pass: all tests green, `cdk synth` clean, storyline demo-ready
