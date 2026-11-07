"""DemoSource: reads the synthetic account, generating it on first use.

It loads only what a real account would expose. Ground-truth files stay on
disk for scoring and are never handed to the agent.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import DataSource, SpendData
from .demo_generator import PAID, UNTRACKED, generate_history


class DemoSource(DataSource):
    def __init__(self, config: dict, data_dir: Path):
        self.config = config
        self.data_dir = Path(data_dir)

    def load(self) -> SpendData:
        if not (self.data_dir / "daily.csv").exists():
            generate_history(self.config["demo"], self.data_dir)
        daily = pd.read_csv(self.data_dir / "daily.csv", parse_dates=["date"])
        conversions = pd.read_csv(self.data_dir / "conversions.csv", parse_dates=["date"])
        journeys = pd.read_csv(self.data_dir / "journeys.csv")
        return SpendData(
            daily=daily,
            conversions=conversions,
            journeys=journeys,
            meta={
                "label": "synthetic data",
                "paid_channels": PAID,
                "untracked_channel": UNTRACKED,
                "start": daily["date"].min().date().isoformat(),
                "end": daily["date"].max().date().isoformat(),
            },
        )
