from abc import ABC, abstractmethod
import pandas as pd
import re
import logging
from pathlib import Path

class BaseHarmonizer(ABC):
    """
    Abstract Base Class for all modality-specific harmonizers.
    Part of the STRATUM skeletal architecture.
    
    BIDS-First Philosophy:
    - BIDS variable names are the canonical standard.
    - Data arriving in BIDS format keeps its original field names.
    - Non-BIDS data gets renamed to BIDS names where a mapping exists.
    - Fields with no registry mapping are NEVER dropped; they are
      preserved with a 'nonstandard_' prefix to flag them as non-BIDS.
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

    @staticmethod
    def extract_bids_entities(source_path: Path) -> dict:
        """
        Extract BIDS entities (participant_id, visit_session) from a file path.
        Works with both BIDS directory structures and BIDS filenames:
          - Directory: .../sub-001/ses-01/anat/sub-001_T1w.json
          - Flat file: .../sub-001_ses-01_task-rest_bold.json
        """
        full_path = str(source_path)
        entities = {}
        
        # Extract participant_id (sub-XXX)
        sub_match = re.search(r'(sub-[a-zA-Z0-9]+)', full_path)
        if sub_match:
            entities['participant_id'] = sub_match.group(1)
        
        # Extract session (ses-XX)
        ses_match = re.search(r'(ses-[a-zA-Z0-9]+)', full_path)
        if ses_match:
            entities['visit_session'] = ses_match.group(1)
        
        return entities

    def _build_rename_map(self) -> dict:
        """
        Build a mapping from original_variable_name -> bids_standard_name.
        Only includes entries where the two differ (i.e., non-BIDS fields
        that need renaming to their BIDS-compatible canonical name).
        """
        if self.registry.empty:
            return {}
        rename_map = {}
        for _, row in self.registry.iterrows():
            orig = row.get('original_variable_name', '')
            bids = row.get('bids_standard_name', '')
            if orig and bids and orig != bids:
                rename_map[orig] = bids
        return rename_map

    def _get_known_fields(self) -> set:
        """Return all field names the registry knows about (both original and BIDS)."""
        if self.registry.empty:
            return set()
        originals = set(self.registry['original_variable_name'].dropna().tolist())
        bids_names = set(self.registry['bids_standard_name'].dropna().tolist())
        return originals | bids_names

    def harmonize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply BIDS-first harmonization to a DataFrame:
        1. Rename non-BIDS field names to their BIDS equivalents (where mapped).
        2. Preserve ALL fields — unmapped fields get a 'nonstandard_' prefix.
        """
        if df.empty:
            return df

        result = df.copy()

        # Step 1: Rename non-BIDS fields to BIDS names where mapping exists
        rename_map = self._build_rename_map()
        cols_to_rename = {c: rename_map[c] for c in result.columns if c in rename_map}
        if cols_to_rename:
            self.logger.info(f"Renaming non-BIDS fields to BIDS standard: {cols_to_rename}")
            result = result.rename(columns=cols_to_rename)

        # Step 2: Flag unmapped fields with nonstandard_ prefix
        known_fields = self._get_known_fields()
        # Also allow modality_category, participant_id, visit_session — these are system fields
        system_fields = {'modality_category', 'participant_id', 'visit_session'}
        for col in list(result.columns):
            if col not in known_fields and col not in system_fields:
                new_name = f"nonstandard_{col}"
                self.logger.info(f"Preserving unmapped field '{col}' as '{new_name}'")
                result = result.rename(columns={col: new_name})

        return result

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
