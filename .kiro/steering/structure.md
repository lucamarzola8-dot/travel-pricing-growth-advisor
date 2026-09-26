# Structure

## Repository layout

```
travel-pricing-growth-advisor/
  backend/
    src/
      travel_advisor/
        __init__.py
        models.py         # dataclasses: Route, Market, Event, PriceResult, Factor, ...
        data.py           # load holidays + events + routes from data/ (no network)
        pricing.py        # pure dynamic-pricing engine
        growth.py         # pure market opportunity scoring + budget allocation
        storyline.py      # turn results into business-language insights
        api.py            # thin handlers wiring the above for Lambda/local
    tests/
      test_pricing.py
      test_growth.py
      properties/         # hypothesis property-based tests (Lesson 4)
  infra/                  # AWS CDK v2 (TypeScript)
    bin/
    lib/
    package.json
  frontend/               # React + Vite dashboard
    src/
  data/                   # seed datasets (JSON/CSV): holidays overrides, events, routes
  .kiro/
    steering/             # this folder
    specs/
    hooks/
    agents/
```

## Placement rules

- New analytical/business logic goes under `backend/src/travel_advisor/`, split by concern
  (pricing vs growth vs storyline). Keep pure logic separate from I/O and handlers.
- Tests mirror the module they cover; property-based tests go under `backend/tests/properties/`.
- Infrastructure changes go in `infra/lib/`. One stack; group resources by purpose with
  clear construct ids.
- Seed data goes in `data/` as plain JSON/CSV, loaded by `data.py`. No data files under
  `backend/src`.
- Kiro artifacts (steering, specs, hooks, agents) live under `.kiro/`.

## Naming

- Python: `snake_case` modules/functions, `PascalCase` dataclasses.
- TypeScript (infra/frontend): `PascalCase` types/components, `camelCase` values.
- CDK construct ids: `PascalCase` and descriptive (e.g. `PricingLambda`, `ResultsTable`).
