import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

class CohortExplorer:
    """
    Advanced analytics tool for querying and exploring the STRATUM Gold Tier.
    Provides filtering, statistical summaries, and cohort discovery logic.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.gold_path = project_root / "data" / "gold" / "gold_multimodal_cohort.csv"
        self.logger = logging.getLogger("STRATUM-Explorer")
        self._df: Optional[pd.DataFrame] = None

    def _load_data(self) -> pd.DataFrame:
        if self._df is None:
            if not self.gold_path.exists():
                raise FileNotFoundError(f"Gold Tier data not found at {self.gold_path}. Run orchestration first.")
            self._df = pd.read_csv(self.gold_path)
        return self._df

    def find_participants(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """
        Filter the cohort based on variable conditions.
        Example filters: {'clinical_survey_psychometrics.PHQ-9 Total Score': ('>', 10)}
        """
        df = self._load_data()
        mask = pd.Series([True] * len(df))

        for col, condition in filters.items():
            if col not in df.columns:
                self.logger.warning(f"Column {col} not found in Gold Tier.")
                continue

            op, val = condition
            if op == '>':
                mask &= (df[col] > val)
            elif op == '<':
                mask &= (df[col] < val)
            elif op == '==':
                mask &= (df[col] == val)
            elif op == 'contains':
                mask &= (df[col].astype(str).str.contains(str(val), case=False))

        return df[mask]

    def get_cohort_stats(self, columns: List[str]) -> Dict[str, Any]:
        """Returns descriptive statistics for requested columns."""
        df = self._load_data()
        valid_cols = [c for c in columns if c in df.columns]
        if not valid_cols:
            return {}
        
        stats = df[valid_cols].describe().to_dict()
        # Add missingness
        for col in valid_cols:
            stats[col]['missing_percent'] = (df[col].isna().sum() / len(df)) * 100
        
        return stats

    def list_correlations(self, target_col: str, threshold: float = 0.3) -> Dict[str, float]:
        """Finds variables that correlate with the target column above a threshold."""
        df = self._load_data()
        if target_col not in df.columns:
            return {}
        
        # Only numeric columns
        numeric_df = df.select_dtypes(include=[np.number])
        if target_col not in numeric_df.columns:
            return {}
            
        corr_matrix = numeric_df.corr()
        corrs = corr_matrix[target_col].dropna().to_dict()
        
        return {k: v for k, v in corrs.items() if abs(v) >= threshold and k != target_col}
