"""Generator settings, independent of service credentials."""

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 42
    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    target_rows: int = 100_000
    inject_anomalies: bool = True
    seasonal_peaks: bool = True
    max_discount: float = 0.40

    def validate(self) -> None:
        """Reject invalid configurations before allocating arrays."""
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer.")
        if type(self.target_rows) is not int or self.target_rows <= 0:
            raise ValueError("target_rows must be a positive integer.")
        if type(self.inject_anomalies) is not bool or type(self.seasonal_peaks) is not bool:
            raise ValueError("Anomaly and seasonal-peak options must be booleans.")
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
            if start.isoformat() != self.start_date or end.isoformat() != self.end_date:
                raise ValueError("Use YYYY-MM-DD, including hyphens.")
        except (TypeError, ValueError) as exc:
            raise ValueError("Dates must use valid YYYY-MM-DD format.") from exc
        days = (end - start).days + 1
        if days < 1:
            raise ValueError("end_date must be on or after start_date.")
        if self.inject_anomalies and days < 112:
            raise ValueError("Anomaly injection requires at least 112 days.")
        if not 0 <= self.max_discount <= 0.60:
            raise ValueError("max_discount must be between 0 and 0.60.")
        if self.target_rows > days * 600:
            raise ValueError("Requested rows exceed the 600 distinct series per day.")

    def to_dict(self) -> dict:
        return asdict(self)
