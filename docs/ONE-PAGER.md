# Travel Pricing & Growth Advisor — One-Pager

*A decision-support tool that turns public signals into flight-pricing and Google Ads
allocation decisions for airlines and OTAs.*

---

## The problem

Travel businesses make two high-stakes decisions constantly, and usually in separate tools
with separate teams:

1. **What price should a flight sell at, on a given date?** Demand swings with seasonality,
   local holidays, and events (a trade fair, a festival, a final) — but the signal is hard to
   see day by day, per market.
2. **Where should a limited Google Ads budget go?** Across dozens of destination markets,
   raw popularity is a poor guide: the most-searched market can also be the most expensive to
   advertise in, so budget chasing popularity quietly wastes spend.

The two decisions are related — the same demand spike that justifies a higher fare also makes
a market worth advertising — yet they are rarely reasoned about together, and the reasoning
is rarely something you can hand to a stakeholder.

## The solution

**Travel Pricing & Growth Advisor** is a single tool with two linked views:

- a **dynamic pricing** view that recommends a fare per route and date from seasonality,
  holidays, and events, and
- a **Google Ads allocation** view that ranks markets by **return on ad spend** and splits a
  budget accordingly.

Every output carries its reasoning in plain language and can be exported as a one-page client
briefing. The demand that lifts a route's fares also boosts that market in the ad allocation,
so the two views tell one coherent story: **signal → price → ad ROI → budget**.

## Who it is for

Commercial and revenue teams at airlines, and growth teams at OTAs (Booking, Expedia,
eDreams) that run Google Ads across many markets. It is a B2B decision-support tool — the
traveller only ever sees the resulting price.

---

## How it works, feature by feature

### 1. Dynamic flight pricing
Given a route and date, the engine starts from a base fare and applies transparent, bounded
multipliers for seasonality, national holidays (in the destination country), and nearby
public events. The result is a recommended price plus the **ordered list of factors** that
produced it — never an unexplained number. Prices are clamped to a per-route floor and
ceiling so recommendations stay sane.

### 2. Pricing calendar
A day-by-day view of the recommended fare over a chosen window, colour-coded by uplift.
Hovering a day reveals the exact factors behind it, so a demand spike (e.g. Dublin at
St. Patrick's Day, +47%) is visible before it happens.

### 3. Google Ads allocation by ROI
For every market the tool computes an opportunity score as **search demand × (1 + booking
margin) ÷ cost-per-click**. A budget is then split proportionally to score. Because CPC is in
the denominator, an expensive market (e.g. London) can rank below a cheaper, high-margin one
(e.g. Lisbon): the budget follows return on spend, not popularity.

### 4. Ad spend breakdown
Each market's allocation is broken down by channel (Search / Performance Max / YouTube) and
shown with example keywords and their CPC, so "allocate €X to Lisbon" becomes concrete: how
much on each channel and which search terms it targets.

### 5. Pricing → allocation link
When a route and period are analysed, the holidays and events that raise its fares also
**demand-boost that market** in the ad allocation. A spike in the pricing calendar pushes the
same market up the ad ranking — one signal driving both decisions.

### 6. Client storyline & one-pager
The tool writes the key insights as plain-language sentences and renders a fixed-layout,
**deterministic** SVG briefing (identical inputs → byte-identical report) — the document a
consultant hands to a client.

### 7. Real-data ready
Signals ship as realistic seed data and are swappable with live sources: the demand index can
be refreshed from **Google Trends**, and CPC/keywords map to the **Google Ads API**. The app
stays offline-first — enrichment updates the seed, never the request path.

---

## How it is built

- **Deterministic core** (Python): pure pricing and growth functions, verified with
  example-based **and property-based tests** (invariants checked over hundreds of generated
  inputs, and over arbitrary rule configurations) — 58 tests in total.
- **Extensible by data, not code**: pricing rules, routes, events, market signals, and ad
  channels all live in editable data files.
- **Serverless AWS, as code**: S3, Lambda, API Gateway, and DynamoDB defined with **AWS CDK**
  (TypeScript), validated with `cdk synth` — no credentials needed to prove it deploys.
- **React + Vite dashboard** with two tabs (Flight Pricing, Ads Growth Allocation).
- Built with **Kiro**: spec-driven development, steering, hooks, MCP, custom agents, and a
  packaged Power.

## What's next

Live Google Ads / Trends feeds via the bundled MCP, per-route revenue simulation, and a
public hosted demo.

**Repository:** https://github.com/lucamarzola8-dot/travel-pricing-growth-advisor
