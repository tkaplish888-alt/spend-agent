from pathlib import Path

from .base import DataSource, SpendData
from .demo import DemoSource
from .google_ads import GoogleAdsSource


def get_source(config: dict, data_dir: Path) -> DataSource:
    """Pick the data source named in config.yaml."""
    name = config["data_source"]
    if name == "demo":
        return DemoSource(config, data_dir)
    if name == "google_ads":
        return GoogleAdsSource(config)
    raise ValueError(f"Unknown data_source: {name}")


__all__ = ["DataSource", "SpendData", "DemoSource", "GoogleAdsSource", "get_source"]
