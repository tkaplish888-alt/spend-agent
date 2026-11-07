"""The one contract every data source follows.

To connect a real ad account, write a class with a single method, load(),
that returns a SpendData. Nothing downstream changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SpendData:
    # One row per channel per day: date, channel, spend, conversions, revenue.
    # Conversions here are what platforms report (last tracked click).
    daily: pd.DataFrame
    # One row per conversion: conversion_id, date, last_touch, revenue, self_reported.
    conversions: pd.DataFrame
    # One row per tracked touch: conversion_id, step, channel.
    journeys: pd.DataFrame
    # Anything else the source knows (channel list, date range, labels).
    meta: dict = field(default_factory=dict)


class DataSource(ABC):
    @abstractmethod
    def load(self) -> SpendData:
        """Return the account's spend, conversions and journeys."""
