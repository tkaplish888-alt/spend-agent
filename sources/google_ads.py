"""Stub for a real Google Ads connector. Not built in v1.

What a real version needs to do inside load():
1. Authenticate with OAuth (developer token + refresh token in env vars).
2. Pull daily campaign spend, conversions and conversion value via GAQL,
   grouped by date, and map campaigns to the channel names in config.yaml.
3. Pull conversion paths if the account exposes them; otherwise return an
   empty journeys frame (attribution models then fall back to last touch).
4. Handle rate limits with backoff and cache raw pulls under data/raw/.
5. Return a SpendData with the same columns DemoSource returns.
"""

from __future__ import annotations

from .base import DataSource, SpendData


class GoogleAdsSource(DataSource):
    def __init__(self, config: dict):
        self.config = config

    def load(self) -> SpendData:
        raise NotImplementedError(
            "GoogleAdsSource is a stub in v1. See the module docstring for what it needs."
        )
