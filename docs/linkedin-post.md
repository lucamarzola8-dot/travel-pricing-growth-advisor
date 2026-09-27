# LinkedIn post

---

I built a Travel Pricing & Growth Advisor — a tool that turns public signals into two travel
business decisions: what to charge for a flight, and where to spend a Google Ads budget. 🛫

The idea: airlines and OTAs (think Booking, Expedia) live on two questions.
→ What price should this route sell at on this date?
→ Where should my ad budget go across markets?

Most tools answer these separately. I wanted one tool that does both — and links them.

What it does:
• Dynamic flight pricing from seasonality, national holidays, and public events (e.g. a
  Milan–Dublin fare jumps +47% around St. Patrick's Day — and it tells you exactly why).
• Google Ads allocation by ROI: markets are ranked by demand × margin ÷ cost-per-click, so
  budget follows return on spend, not raw popularity. A high-demand but expensive market
  (London) can rank below a cheaper, high-margin one (Lisbon).
• A breakdown of where each market's budget goes — Search / Performance Max / YouTube, with
  example keywords and CPC.
• A one-click, client-ready one-pager generated straight from the engine.

How I built it:
I used Kiro (spec-driven AI development) end to end — requirements, design, steering, hooks,
property-based tests, custom agents, and a packaged reusable module. The pricing/growth core
is pure and deterministic, proven with property-based tests that hold over hundreds of
generated inputs. Infrastructure is serverless AWS (S3, Lambda, API Gateway, DynamoDB)
defined as code with AWS CDK. Stack: Python, TypeScript, React.

The part I like most: it's explainable. Every price and every euro of budget comes with the
reasoning a consultant could read straight to a client.

Code (open source): https://github.com/lucamarzola8-dot/travel-pricing-growth-advisor

Feedback welcome. 👇

#Travel #DataAnalytics #GoogleAds #AWS #Python #React #AI #ProductBuilding
