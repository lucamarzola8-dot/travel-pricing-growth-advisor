# Tech

## Stack

- **Backend / core logic:** Python 3.12+ (the dev machine has 3.14). Pricing engine, growth
  advisor, and data loading. This is the analytical core (aligns with Python/SQL data work).
- **Infrastructure:** AWS CDK v2 in **TypeScript**. Resources: S3 (seed data), Lambda
  (pricing + growth handlers), API Gateway (REST), DynamoDB (results/cache).
- **Frontend:** React + TypeScript with Vite. Charts for pricing calendar, demand timeline,
  and opportunity board.
- **Testing:** `pytest` for unit tests and **`hypothesis`** for property-based tests (Kiro
  Lesson 4). Property tests live alongside example-based tests.

## Conventions

- **Language boundary:** business/analytical logic in Python; infrastructure in TypeScript
  CDK; UI in React/TS. Do not implement pricing logic in the frontend or in CDK.
- **Pure functions for the core.** The pricing and scoring functions must be pure: inputs in,
  result out, no I/O, no global state, no wall-clock reads inside the calculation (pass the
  reference date in). This keeps them deterministic and property-testable.
- **Every result carries its explanation.** Pricing/scoring functions return the value *and*
  the list of factors that produced it, never a bare number.
- **Advertising data drives growth scoring.** Per-market signals (search-demand index,
  cost-per-click, margin) live in `data/markets.json`. The opportunity score is ROI of ad
  spend: `demand * (1 + margin) / cpc`. Keep it deterministic and offline; the optional
  Google Trends MCP enrichment may refresh the demand index but must never be on the
  critical path.
- **CDK is validated, not necessarily deployed.** Correctness is proven with `cdk synth`.
  Live deploy (`cdk deploy`) is optional and must never be a prerequisite for tests passing.
  CDK is a project dev-dependency (`npx cdk` / `npm` scripts), never assumed globally installed.
- **No secrets in the repo.** No API keys, credentials, or account IDs committed. Use
  environment variables / `.env` (git-ignored) for anything sensitive.
- **Money as integers.** Represent monetary amounts in minor units (cents) or use `Decimal`;
  never accumulate prices in binary floats.

## Commands

- Backend tests: `pytest` from `backend/`.
- Infra validation: `npm run synth` from `infra/` (wraps `cdk synth`).
- Frontend dev: `npm run dev` from `frontend/`.

## Example: an explainable pricing result

Enforce that core functions return value + reasons. For example, a pricing call returns:

```python
PriceResult(
    price=Decimal("236.00"),
    base=Decimal("200.00"),
    factors=[
        Factor("seasonality", 1.05, "shoulder season"),
        Factor("holiday", 1.06, "national holiday in ES"),
        Factor("event", 1.06, "Mobile World Congress within 3 days"),
    ],
)
```

so the frontend can render "+18% vs base" with the exact reasons, and never shows an
unexplained number.
