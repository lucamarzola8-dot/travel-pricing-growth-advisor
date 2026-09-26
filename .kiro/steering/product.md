# Product

Travel Pricing & Growth Advisor is an event-driven dynamic pricing and international growth
advisory platform for the travel vertical (airlines and online travel agencies).

## What it does

It turns public signals — national holidays and public events (trade fairs, concerts,
sporting events) — into two outputs:

1. **Dynamic pricing** — a recommended price for a route/date/market, derived from a base
   fare adjusted by seasonality, local holidays, and proximity to relevant events.
2. **Growth recommendations** — a per-market opportunity score and a suggested allocation of
   marketing budget / capacity, plus a plain-language "storyline" that explains the reasoning
   to a business decision-maker.

## Who it is for

- Revenue management and commercial teams at airlines / OTAs.
- International growth consultants advising travel clients on where and when to invest.

## Product principles

- **Explainable over clever.** Every price and recommendation must come with a human-readable
  reason ("+18% because national holiday + MWC event + weekend"). Never output a number
  without an explanation the user can repeat to a stakeholder.
- **Deterministic core.** Pricing and scoring are rule-based and reproducible: the same inputs
  always produce the same output. No machine learning in the core path.
- **Offline-first data.** The product must run end-to-end with local seed datasets and the
  `holidays` library, with no paid API keys or live feeds required. External enrichment is an
  optional add-on, never on the critical path.
- **Business storyline is a first-class output**, not an afterthought — insights are written
  in language a non-technical decision-maker can act on.

## Scope discipline (MVP)

In scope for the MVP: holidays + curated events dataset, rule-based pricing engine, market
opportunity scoring + budget allocation, storyline generation, dashboard, CDK infrastructure
validated with `cdk synth`.

Explicitly out of scope (future / optional): ML-based demand forecasting, live event feeds,
multi-currency, real bookings/payments, and live AWS deployment. Do not add these unless a
requirement is added to the spec first.
