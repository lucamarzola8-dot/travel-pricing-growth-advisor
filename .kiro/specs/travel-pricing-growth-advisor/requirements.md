# Requirements — Travel Pricing & Growth Advisor

Requirements use **EARS** (Easy Approach to Requirements Syntax): each is a testable
"WHEN/WHILE/IF ... THE SYSTEM SHALL ..." statement.

## 1. Data ingestion (holidays, events, routes)

**User story:** As an analyst, I want the system to load holidays, events, and routes from
local datasets so that pricing and growth work offline without paid APIs.

- 1.1 WHEN the system starts a calculation THE SYSTEM SHALL load national holidays for the
  requested market using an offline holiday source.
- 1.2 WHEN loading the events dataset THE SYSTEM SHALL read events from the local `data/`
  directory and expose each event's market, date, and demand impact.
- 1.3 IF an event record is missing a required field (market, date, or impact) THE SYSTEM
  SHALL reject that record and continue loading the remaining valid records.
- 1.4 WHEN a route is requested for an unknown route code THE SYSTEM SHALL return a clear
  "unknown route" error rather than a default price.

## 2. Dynamic pricing engine

**User story:** As a revenue manager, I want an explainable recommended price for a
route/date/market so that I can justify it to stakeholders.

- 2.1 WHEN a price is requested for a route, date, and market THE SYSTEM SHALL return a
  recommended price and the ordered list of factors that produced it.
- 2.2 THE SYSTEM SHALL never return a recommended price below the route's configured price
  floor.
- 2.3 THE SYSTEM SHALL never return a recommended price above the route's configured price
  ceiling (cap).
- 2.4 WHEN there is a national holiday in the destination market on the travel date THE
  SYSTEM SHALL apply a non-decreasing adjustment to the price and record a "holiday" factor.
- 2.5 WHEN a relevant event occurs within the configured proximity window of the travel date
  THE SYSTEM SHALL apply a non-decreasing adjustment that is strongest on the event day and
  fades with distance to zero at the edge of the window, and record an "event" factor.
- 2.6 IF no holidays or events apply THE SYSTEM SHALL return the base fare adjusted only by
  the always-present time factors (seasonality and day of week), and the factor list SHALL
  contain exactly those two factors in that order.
- 2.7 WHEN the same inputs are provided again THE SYSTEM SHALL return an identical result
  (determinism).
- 2.8 WHEN a price is computed THE SYSTEM SHALL apply a day-of-week multiplier from the
  pricing rules so that consecutive days in the same season carry different prices
  (weekend departures priced above mid-week ones).
- 2.9 WHEN a price is returned THE SYSTEM SHALL also return a breakdown listing, for each
  factor in order, its contribution in currency and as a percentage of the base fare, plus a
  "guardrail" line when the floor/ceiling changed the price, such that base fare plus the
  sum of contributions equals the final price exactly.
- 2.10 THE SYSTEM SHALL read every pricing parameter (seasonality, day-of-week multipliers,
  holiday boost, event proximity, elasticities, capacity scale, marginal cost) from
  `pricing-rules.json`, falling back to documented defaults when the file is missing.

## 2b. Profit-optimising price (elasticity + capacity)

**User story:** As a revenue manager, I want the price that maximises expected profit given
how price-sensitive my customers are and how many seats I actually have, so that pricing is
an optimisation and not only a rule.

- 2b.1 WHEN an optimal price is requested for a route and date THE SYSTEM SHALL model demand
  as a constant-elasticity function of price, scaled by the same contextual factors used for
  the rule-based price, and return the price in `[floor, ceiling]` that maximises expected
  profit `(price − marginal cost) × min(demand, seats)`.
- 2b.2 THE SYSTEM SHALL use the elasticity configured for the route's demand segment
  (e.g. business vs leisure), falling back to a default elasticity.
- 2b.3 THE SYSTEM SHALL never recommend an optimal price whose expected seats sold exceed the
  route's seat capacity.
- 2b.4 WHEN demand at the unconstrained markup price would exceed the seat capacity THE
  SYSTEM SHALL raise the optimal price to the market-clearing level and flag the result as
  capacity-constrained; capacity SHALL never lower the price below the markup price.
- 2b.5 WHEN the route has more seats, all else equal, THE SYSTEM SHALL NOT return a higher
  optimal price.
- 2b.6 THE SYSTEM SHALL return, alongside the optimal price, the unconstrained markup price,
  the rule-based recommended price, and the expected demand, revenue and profit of each, so
  that the profit uplift of optimising is visible and explainable.
- 2b.7 WHEN the same inputs are provided again THE SYSTEM SHALL return an identical optimal
  price (determinism).

## 3. Growth opportunity advisor

**User story:** As an international growth consultant, I want markets ranked by opportunity
with a suggested budget split so that I can advise where to invest.

- 3.1 WHEN given a set of markets with expected demand THE SYSTEM SHALL compute an opportunity
  score for each market.
- 3.2 WHEN given a total budget and market scores THE SYSTEM SHALL produce a per-market budget
  allocation whose sum equals the total budget (within rounding tolerance).
- 3.3 THE SYSTEM SHALL never allocate a negative budget to any market.
- 3.4 WHEN one market has a strictly higher opportunity score than another THE SYSTEM SHALL
  allocate it a budget greater than or equal to the lower-scored market.
- 3.5 WHEN markets are ranked THE SYSTEM SHALL order them by descending opportunity score.

## 4. Storyline generation

**User story:** As a consultant, I want a plain-language storyline so that I can present the
recommendation to a client.

- 4.1 WHEN pricing and growth results are available THE SYSTEM SHALL generate a storyline of
  the top insights in business language.
- 4.2 WHEN a price differs from the base fare THE SYSTEM SHALL state the percentage difference
  and the reasons in the storyline.
- 4.3 THE SYSTEM SHALL not include any insight that is not backed by a computed factor or
  score.

## 5. API

**User story:** As the frontend, I want HTTP endpoints so that I can retrieve pricing, growth,
and storyline data.

- 5.1 WHEN the client requests a price with valid parameters THE SYSTEM SHALL respond with the
  price result as JSON.
- 5.2 IF required parameters are missing or invalid THE SYSTEM SHALL respond with a 400-style
  error and a message identifying the problem.
- 5.3 WHEN the client requests the growth board THE SYSTEM SHALL respond with ranked markets
  and their allocations as JSON.
- 5.4 WHEN the client requests the optimal price for a route and date THE SYSTEM SHALL respond
  with the profit-optimisation result as JSON; WHEN a `days` parameter (1–31) is supplied THE
  SYSTEM SHALL respond with one result per day in a single response.
- 5.5 IF `days` is outside 1–31 or not an integer THE SYSTEM SHALL respond with a 400-style
  error identifying the problem.

## 6. Dashboard (frontend)

**User story:** As an analyst, I want an interactive dashboard so that I can explore prices,
demand, opportunities, and the storyline.

- 6.1 WHEN the analyst selects a route, period, and market THE SYSTEM SHALL display the
  recommended price per day for that period.
- 6.2 WHEN the analyst hovers a priced day THE SYSTEM SHALL display the factors behind that
  day's price.
- 6.3 THE SYSTEM SHALL display markets ranked by opportunity with their suggested allocation.
- 6.4 THE SYSTEM SHALL display the generated storyline.
- 6.5 WHEN the analyst switches the calendar to "optimal price" THE SYSTEM SHALL display the
  profit-optimal price per day, mark days where seat capacity forced the price up, and show
  the expected load factor and profit uplift versus the rule-based price.
- 6.6 WHEN the analyst selects a priced day THE SYSTEM SHALL display the currency/percentage
  breakdown of that day's price in a form readable by a non-technical stakeholder.
- 6.7 WHEN the analyst picks a second route or date to compare THE SYSTEM SHALL display both
  scenarios side by side with price, profit and the factors that explain the difference.

## 7. Infrastructure

**User story:** As the owner, I want the cloud architecture defined as code so that it is
reviewable and deployable on demand.

- 7.1 THE SYSTEM SHALL define its AWS infrastructure (S3, Lambda, API Gateway, DynamoDB) as
  CDK code in TypeScript.
- 7.2 WHEN `cdk synth` runs THE SYSTEM SHALL produce a valid CloudFormation template without
  requiring AWS credentials or a live deployment.
- 7.3 THE SYSTEM SHALL NOT require live AWS resources for backend unit tests or property tests
  to pass.
