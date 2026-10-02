# Phase 2 research methodology

## Purpose and status

Research question: Does adaptive evidence selection and evidence verification improve the reliability of GenAI-generated explanations of anomalies in structured data?

Implemented: synthetic generation, interventions, separated evaluation artifacts, validation, and tests. No analysis tools, detector, agent, GenAI, API, database, or dashboard is implemented. Explanation reliability and ML performance have not been measured.

## Synthetic-data rationale

Controlled generation provides known intervention scopes and factors, reproducibility, and an unchanged counterfactual for evaluation. It avoids using personal customer information. These strengths depend on imposed assumptions and do not prove generalization to real-world datasets.

## Grain and coverage

A row is an active daily product-region-customer_segment aggregate, not an individual transaction. Category is a fixed property of product. All selected series appear on all dates, avoiding accidental missingness as an explanation for a decline.

Thirty products, five regions, and four segments permit 600 series. Thirty mandatory series assign product index i to region i modulo 5 and segment i modulo 4, ensuring coverage. Additional distinct series are sampled without replacement. The selected panel is a coverage design, not a representative sample of a real market.

For D inclusive dates and target T: series count = min(600, max(30, floor(T/D + 0.5))). Requests above 600D fail. Defaults produce 137 x 731 = 100147 rows from 2024-01-01 through 2025-12-31. The first year is a leap year.

## Data dictionary

| Column | Interpretation |
| --- | --- |
| record_id | Stable join key; never a numerical ML predictor |
| date | Aggregate date, YYYY-MM-DD |
| region | North, South, East, West, Central |
| product | P001 through P030 |
| category | Electronics, Home, Office, Clothing, Sports, Personal Care; fixed product mapping |
| customer_segment | Consumer, Corporate, Small Business, Enterprise |
| units | Positive integer units sold; active-only simulation |
| price | Positive unit list price in generic currency units |
| discount | Fractional discount, e.g. 0.10 = 10% |
| revenue | Discounted gross sales before refunds |
| cost | Modeled cost of units sold, not all operating expenses |
| orders | Positive integer count, at most units |
| returns | Returned units associated with this sales cohort, at most units |

Revenue = round(units x price x (1 - discount), 2). Returns are assigned to the sold cohort; delayed return dates and refunds are not modeled. A return increase does not change gross revenue or cost. Profit and return rate can be derived later and are not additional stored features.

## Normal generating process

Randomness uses NumPy default_rng(seed); draw order and source/dependency versions are part of the reproducibility contract.

Poisson demand intensity multiplies:
- Product demand: Uniform(18,85).
- Category factors: [0.85,1.10,0.95,1.15,1.05,1.20].
- Region factors: [1.12,1.05,0.88,1.18,0.95].
- Segment factors: [1.00,1.18,0.82,1.35].
- Monthly factors Jan-Dec: [0.90,0.92,1.00,0.98,1.02,1.05,1.00,1.03,1.06,1.10,1.28,1.40]. Without extra peaks, Nov/Dec are 1.12/1.15.
- Weekend factors by segment: [1.22,0.72,0.90,0.68]; weekdays use 1.
- Trend: 1 + 0.08 x day_index/365.25.
- Shared daily lognormal noise, log standard deviation 0.07, adjusted to mean one.
- Independent row lognormal noise, log standard deviation 0.15, adjusted to mean one.

Units = max(1, Poisson(intensity)). The minimum encodes an active-series assumption. Natural stochastic extremes remain possible without positive intervention labels.

Base product price is Uniform(25,250), with 2% linear annual growth and mean-one row lognormal noise with log standard deviation 0.015. Prices round to cents. Discount is Beta(2,8) times the configured cap, rounded down to four decimal places.

Product unit cost = base price x Uniform(0.52,0.70) x (1 + 0.015 x day_index/365.25). Cost = round(units x unit cost, 2).

Orders = round(units / segment basket size), clipped to [1,units]; basket sizes are [1.6,4.0,2.5,7.0]. Returns are Binomial(units, product probability), with product probabilities drawn from Uniform(0.015,0.055).

These mechanisms are deliberately simple and not calibrated industry estimates.

## Scheduling and anomaly mechanisms

The first half of the dates is free of injected events. The second half is divided into seven blocks, each containing a seven-day window. The first six windows are centered within their blocks. The final window maximizes the average monthly multiplier within its block (earliest tie). Date windows never overlap.

| Type | Scope | Intervention |
| --- | --- | --- |
| sales_decline | All series | units' = max(1, floor(units x 0.50)) |
| regional_decline | North | units' = max(1, floor(units x 0.40)) |
| product_anomaly | P001 | units' = max(1, floor(units x 0.35)) |
| return_anomaly | Electronics | returns' = min(units, returns + ceil(units x 0.25)) |
| price_anomaly | Home | price' = round(price x 1.60, 2) |
| demand_spike | All series | units' = max(1, floor(units x 2.20)) |
| seasonal_deviation | All series | units' = max(1, floor(units x 0.60 / monthly_multiplier)) |

For unit interventions, cost' = round(cost x units' / units, 2), using this fixed operation order for reproducible cent rounding. Orders and returns scale with units'/units, round to integers, and clip to valid ranges. Revenue is recomputed. Price events preserve units/cost/orders/returns: no implicit price elasticity is assumed. Return events preserve all other values.

Severity is a preset experimental label high, not a calculated statistical score. Parameter stores the applied multiplier or additive fraction. The baseline is not mutated. Only genuinely changed records receive positive labels. Empty interventions or overlapping scopes fail validation.

With custom dates, the seasonal event may not occur in a peak month; it still removes that month's normal effect and applies suppression. Changing seed varies the panel/data but not fixed event scopes/dates for a given date range.

## Verified default event ledger

Seed 42; default dates and options:

| ID | Type | Inclusive window | Changed records |
| --- | --- | --- | ---: |
| A001 | sales_decline | 2025-01-23 to 2025-01-29 | 959 |
| A002 | regional_decline | 2025-03-17 to 2025-03-23 | 203 |
| A003 | product_anomaly | 2025-05-08 to 2025-05-14 | 14 |
| A004 | return_anomaly | 2025-06-29 to 2025-07-05 | 161 |
| A005 | price_anomaly | 2025-08-20 to 2025-08-26 | 140 |
| A006 | demand_spike | 2025-10-11 to 2025-10-17 | 959 |
| A007 | seasonal_deviation | 2025-12-01 to 2025-12-07 | 959 |
| Total | Seven events | No overlap | 3395 |

These are actual generation counts, not detection performance.

## Ground truth: detection versus generating factor

Detection truth in evaluation/insightx_record_labels.csv answers whether each record was actually modified. Every record_id appears once; is_anomaly is 0/1 and anomaly_id is A001-A007 or normal.

Event truth in insightx_ground_truth.csv records anomaly_id/type, inclusive dates, region/product/category scope, affected metric, manipulation, true_contributing_factor, parameter, declared severity, affected-record count, and notes. ALL means unrestricted scope.

evaluation/insightx_baseline.csv retains the original random draw before any intervention. It is a simulation counterfactual, not a real-world observed counterfactual. The known generating factor refers only to the variable deliberately manipulated within this simulation; correlation in output data alone does not establish real-world causality.

The business CSV contains only 13 allowlisted observation columns. Tests reject hidden factors, labels, event IDs, baseline columns, and unfamiliar extras. Future tools must ingest that exact file only. Labels, baseline, event definitions, metadata, generator rules, and evaluation summaries must not be passed as evidence to the investigating model. File separation does not itself restrict runtime access; scoped loaders will be required in later phases.

## Validation and reproducibility

Checks cover exact schemas, unique IDs and daily keys, dates, known dimensions, category mapping, integer counts, finite/nonnegative values, price positivity, discounts, returns/units, orders/units, revenue identity, positive active cost, complete panel coverage, event definitions, scopes, changed counts, labels, and replayed interventions.

Saved validation checks all CSV hashes and regenerates the baseline. This catches inconsistent cost economics and accidental edits. Metadata records generator version 0.2.0, source SHA-256, Git revision and dirty status, seed/config, exact row/series count, Python and package versions, and CSV checksums. Dirty builds are not described as committed revisions.

Anomaly-on and anomaly-off outputs are tested for byte-level CSV reproducibility. CLI execution from another working directory is tested. Phase 1 tests are unchanged; health now checks NumPy/Pandas too.

Actual validation on Linux/Python 3.12.14: **67 passed**. Raw outputs and installed dependencies are in docs/phase2_checkpoint/. The default business and ground-truth validation both pass. User-machine timings may vary; no universal laptop benchmark is claimed.

## Limitations and future evaluation precautions

- Fixed active series omit missingness, inactive days, launches, closures, inventory, competition, holidays, and return delays.
- Parameters are chosen assumptions, not empirical estimates.
- Seven high-severity events are insufficient for broad evaluation. Counts are uneven, including just 14 product-event records.
- Some correlated changes are accounting identities, not independent evidence of a cause.
- Labels describe intentional interventions, not every naturally unusual observation.
- Integer rounding and minimum-one clipping can weaken target ratios.
- Fixed dates/scopes permit shortcuts. Future evaluation must vary dates, scopes, strengths, and seeds and hold out independent event scenarios. Never treat record_id as a predictor.
- Overlapping/compound causes are not supported.
- Real-world generalization needs additional generators and real datasets.
- Future work should report row-level detection and event/factor identification with uncertainty over independent scenarios. None of those metrics are computed in Phase 2.
- Checksums detect changes but do not authenticate an attacker-modified dataset and metadata pair.

## Research-paper wording

Supported: "We constructed a controlled synthetic daily sales panel with known injected interventions and stored detection labels and generating-factor ground truth separately from observable measurements."

Supported: "The known factor is the deliberately manipulated variable within the simulation."

Not established: real-world causal discovery, improved ML accuracy, explanation-reliability gains, novelty, patentability, or statistical significance.

Stop at Phase 2.
