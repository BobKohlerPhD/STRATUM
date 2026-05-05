from abc import ABC, abstractmethod
import pandas as pd
import logging
from pathlib import Path

class BaseHarmonizer(ABC):
    """
    Abstract Base Class for all modality-specific harmonizers.
    Part of the STRATUM skeletal architecture.
    """
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.logger = logging.getLogger(f"STRATUM-{self.__class__.__name__}")
        self.registry = self._load_registry()

    def _load_registry(self):
        try:
            return pd.read_csv(self.registry_path)
        except Exception as e:
            self.logger.error(f"Failed to load registry: {e}")
            return pd.DataFrame()

    @abstractmethod
    def ingest(self, source_path: Path) -> pd.DataFrame:
        """Read raw data from the bronze tier."""
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map raw data to the STRATUM registry schema."""
        pass

    def run(self, source_path: Path, output_path: Path):
        """Standard execution flow for harmonization."""
        self.logger.info(f"Starting harmonization for {source_path}")
        raw_df = self.ingest(source_path)
        harmonized_df = self.transform(raw_df)
        
        # Save to silver tier
        harmonized_df.to_csv(output_path, index=False)
        self.logger.info(f"Harmonized data saved to {output_path}")
        return harmonized_df
