# CV entry — STAR method

## One-line résumé bullet (condensed STAR)

> **Travel Pricing & Growth Advisor** — Built a full-stack decision-support tool that turns
> public demand signals (holidays, events) into dynamic flight pricing and Google Ads budget
> allocation by ROI; shipped an explainable, deterministic engine (Python) with
> property-based tests, a React dashboard, and serverless AWS infrastructure (CDK), producing
> a client-ready one-pager that recommends where each advertising euro returns most.

## Two-line variant

> **Travel Pricing & Growth Advisor (personal project)** — Designed and built a B2B tool for
> airlines/OTAs that recommends dynamic flight fares and allocates a Google Ads budget across
> markets by return on ad spend (demand × margin ÷ CPC).
> Delivered a deterministic Python engine (property-based tested), a React + AWS CDK
> serverless stack, and an auto-generated client one-pager — making every pricing and budget
> decision explainable end to end.

## Full STAR breakdown (for interviews)

**Situation.** Airlines and online travel agencies make two high-stakes decisions — how to
price flights and where to spend advertising budget across markets — usually in separate
tools, with reasoning that's hard to hand to a stakeholder.

**Task.** Build a single tool that produces both decisions from public demand signals, ranks
markets by advertising ROI (not raw popularity), and explains every recommendation in
business language.

**Action.** Designed a deterministic pricing engine (base fare × seasonality × holidays ×
events) and an ROI-based growth allocator (demand × (1 + margin) ÷ cost-per-click), keeping
the core pure and offline-first. Proved correctness with example-based and property-based
tests (invariants over hundreds of generated inputs). Exposed it via an API, built a React
dashboard with a pricing calendar and an ads-allocation view, generated a deterministic
client one-pager, and defined serverless AWS infrastructure (S3, Lambda, API Gateway,
DynamoDB) as code with AWS CDK. Made signals swappable with live Google Trends / Google Ads
data.

**Result.** A working, open-source product with 58 passing tests and validated cloud
infrastructure that recommends where each advertising euro returns the most — surfacing, for
example, that a high-demand but high-CPC market can be a worse investment than a cheaper,
high-margin one.

---

*Tip: on a résumé use the one-line bullet; keep the STAR breakdown for interview prep.
Repo: https://github.com/lucamarzola8-dot/travel-pricing-growth-advisor*
