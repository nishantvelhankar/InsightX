"""Vectorized generation of a balanced panel of active daily aggregates."""

from itertools import product

import numpy as np
import pandas as pd

from insightx.data.schema import (
    BUSINESS_COLUMNS, CATEGORIES, PRODUCT_CATEGORIES, REGIONS, SEGMENTS,
)
from insightx.data.settings import GenerationConfig


def monthly_multiplier(dates: pd.DatetimeIndex, peaks: bool) -> np.ndarray:
    """Known normal seasonal mechanism; optional extra November/December peak."""
    factors = np.array([0.90, 0.92, 1.00, 0.98, 1.02, 1.05,
                        1.00, 1.03, 1.06, 1.10, 1.12, 1.15])
    if peaks:
        factors[-2:] = [1.28, 1.40]
    return factors[dates.month.to_numpy() - 1]


def generate_baseline(config: GenerationConfig) -> pd.DataFrame:
    """Generate one row per day for each selected, always-active sales series."""
    config.validate()
    rng = np.random.default_rng(config.seed)
    dates = pd.date_range(config.start_date, config.end_date, freq="D")
    days = len(dates)
    series_count = min(600, max(30, int(config.target_rows / days + 0.5)))

    # Thirty mandatory series ensure every product and all dimensions are present.
    mandatory = [(i, i % 5, i % 4) for i in range(30)]
    mandatory_set = set(mandatory)
    candidates = [cell for cell in product(range(30), range(5), range(4))
                  if cell not in mandatory_set]
    chosen = rng.choice(len(candidates), size=series_count - 30, replace=False)
    cells = np.array(sorted(mandatory + [candidates[i] for i in chosen]))
    product_id = np.tile(cells[:, 0], days)
    region_id = np.tile(cells[:, 1], days)
    segment_id = np.tile(cells[:, 2], days)
    day_id = np.repeat(np.arange(days), series_count)
    row_dates = dates[day_id]
    count = days * series_count

    base_demand = rng.uniform(18, 85, 30)
    base_price = rng.uniform(25, 250, 30)
    cost_fraction = rng.uniform(0.52, 0.70, 30)
    product_returns = rng.uniform(0.015, 0.055, 30)
    category_effect = np.array([0.85, 1.10, 0.95, 1.15, 1.05, 1.20])
    region_effect = np.array([1.12, 1.05, 0.88, 1.18, 0.95])
    segment_effect = np.array([1.00, 1.18, 0.82, 1.35])
    is_weekend = row_dates.dayofweek.to_numpy() >= 5
    weekend_effect = np.where(
        is_weekend, np.array([1.22, 0.72, 0.90, 0.68])[segment_id], 1.0,
    )
    # Both shared daily shocks and individual noise prevent smooth, isolated curves.
    shared_noise = rng.lognormal(-0.07**2 / 2, 0.07, days)[day_id]
    individual_noise = rng.lognormal(-0.15**2 / 2, 0.15, count)
    demand = (
        base_demand[product_id] * category_effect[product_id % 6]
        * region_effect[region_id] * segment_effect[segment_id]
        * monthly_multiplier(row_dates, config.seasonal_peaks)
        * weekend_effect * (1 + 0.08 * day_id / 365.25)
        * shared_noise * individual_noise
    )
    units = np.maximum(1, rng.poisson(demand))
    price = np.round(
        base_price[product_id] * (1 + 0.02 * day_id / 365.25)
        * rng.lognormal(-0.015**2 / 2, 0.015, count), 2,
    )
    # Round down so even very small configured caps cannot be exceeded.
    discount = np.floor(rng.beta(2, 8, count) * config.max_discount * 10_000) / 10_000
    unit_cost = base_price[product_id] * cost_fraction[product_id] * (
        1 + 0.015 * day_id / 365.25
    )
    basket_size = np.array([1.6, 4.0, 2.5, 7.0])[segment_id]
    orders = np.clip(np.rint(units / basket_size).astype(int), 1, units)
    returns = rng.binomial(units, product_returns[product_id])
    frame = pd.DataFrame({
        "record_id": [f"R{i + 1:07d}" for i in range(count)],
        "date": row_dates.strftime("%Y-%m-%d"),
        "region": np.array(REGIONS)[region_id],
        "product": np.array(list(PRODUCT_CATEGORIES))[product_id],
        "category": np.array(CATEGORIES)[product_id % 6],
        "customer_segment": np.array(SEGMENTS)[segment_id],
        "units": units, "price": price, "discount": discount,
        "revenue": np.round(units * price * (1 - discount), 2),
        "cost": np.round(units * unit_cost, 2),
        "orders": orders, "returns": returns,
    })
    return frame[BUSINESS_COLUMNS]
