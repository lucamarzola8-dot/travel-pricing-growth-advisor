---
name: travel-growth-toolkit
description: >-
  Build event-driven travel pricing and international growth features. Use when
  implementing or changing dynamic pricing, market opportunity scoring, budget
  allocation, or the seed datasets for a travel-vertical product. Triggers on:
  travel pricing, dynamic fare, revenue management, growth opportunity, market
  allocation, seasonality, holiday/event uplift.
---

# Travel Growth Toolkit

Guidance for building explainable, deterministic travel pricing and growth logic.

## Core principles

1. **Explainable over clever.** Every price or score returns the value *and* the
   ordered factors that produced it. Never emit a bare number a consultant cannot
   justify to a client.
2. **Deterministic core.** Pricing and scoring are pure rule-based functions:
   same inputs → same output. No machine learning, no wall-clock reads inside the
   calculation (pass the reference date in), no network, no globals.
3. **Offline-first data.** Run end-to-end from local seed data plus an offline
   holidays source. External enrichment (e.g. a fetch MCP server) is optional and
   never on the critical path.
4. **Money is Decimal.** Represent monetary amounts with `Decimal` (or integer
   minor units); never accumulate prices in binary floats.

## Pricing recipe

- Start from a base fare; apply bounded multipliers in order: seasonality, then
  national-holiday uplift, then per-event uplift for events within a proximity
  window of the travel date.
- Holiday and event multipliers are `>= 1` so they can only hold or raise the
  pre-clamp price. Clamp the final price to the route's `[floor, ceiling]`.
- Record one `Factor(kind, multiplier, reason)` per applied adjustment.

## Growth recipe

- `opportunity_score` must be monotonic non-decreasing in demand and margin, and
  always `>= 0`.
- `allocate` splits a budget proportionally to score: non-negative amounts that
  sum exactly to the total (give rounding remainder to the highest-scored market
  so a higher score never receives less). All-zero scores → even split.

## Testing (do this every time)

Add or update tests when you touch the core, and run them before declaring done:

- Example-based `pytest` tests for concrete scenarios (a known holiday, a known
  event, clamping at floor/ceiling).
- **Property-based tests** (hypothesis) for the general rules:
  - Pricing: price within `[floor, ceiling]`; holiday/event never lower the
    pre-clamp price; no-signal case yields only the seasonality factor;
    determinism.
  - Growth: allocations sum to budget; non-negative; higher score ≥ lower score;
    score monotonic in demand; rank sorted descending.

## Anti-patterns to reject

- Pricing logic in the frontend or in infrastructure code.
- A default declared but silently not applied.
- Fabricated storyline insights not backed by a real factor or score.
- Introducing a paid API or live feed on the pricing critical path.
