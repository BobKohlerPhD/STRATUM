from abc import ABC, abstractmethod
import pandas as pd
import re
import logging
from pathlib import Path

import sqlite3

class BaseHarmonizer(ABC):
    """
    Abstract Base Class for all modality-specific harmonizers.
    Part of the STRATUM skeletal architecture.
    """
    def __init__(self, registry_db_path: Path):
        self.db_path = registry_db_path
        self.logger = logging.getLogger(f"STRATUM-{self.__class__.__name__}")
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _get_standard_name_by_code(self, code: str, code_column: str = 'loinc_code') -> str:
        """Lookup a standard_name by a code (e.g., LOINC) using indexed SQLite."""
        try:
            cursor = self.conn.cursor()
            query = f"SELECT standard_name FROM variables WHERE {code_column} = ?"
            cursor.execute(query, (str(code),))
            result = cursor.fetchone()
            return result['standard_name'] if result else None
        except Exception as e:
            self.logger.error(f"Registry lookup failed: {e}")
            return None

    def get_categorical_label(self, standard_name: str, code: str) -> str:
        """Get the human-readable label for a categorical code."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT label FROM categorical_lookups WHERE standard_name = ? AND code = ?",
                (standard_name, str(code))
            )
            result = cursor.fetchone()
            return result['label'] if result else None
        except Exception as e:
            self.logger.error(f"Categorical lookup failed: {e}")
            return None

    @staticmethod
    def extract_bids_entities(source_path: Path) -> dict:
        """
        Extract BIDS entities (participant_id, visit_session) from a file path.
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
        Build a mapping from original_variable_name -> standard_name using SQLite.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT original_variable_name, standard_name FROM variables")
            rename_map = {}
            for row in cursor.fetchall():
                orig = row['original_variable_name']
                std = row['standard_name']
                if orig and std and orig != std:
                    rename_map[orig] = std
            return rename_map
        except Exception as e:
            self.logger.error(f"Failed to build rename map: {e}")
            return {}

    def _get_known_fields(self) -> set:
        """Return all field names the registry knows about from SQLite."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT original_variable_name, standard_name FROM variables")
            known = set()
            for row in cursor.fetchall():
                if row['original_variable_name']: known.add(row['original_variable_name'])
                if row['standard_name']: known.add(row['standard_name'])
            return known
        except Exception as e:
            self.logger.error(f"Failed to get known fields: {e}")
            return set()

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
