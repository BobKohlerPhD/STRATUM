import pandas as pd
import json
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class WearableHarmonizer(BaseHarmonizer):
    """
    Standard Plugin for Digital Biomarkers and Wearables.
    Pre-processes high-frequency time-series data (e.g., continuous HR)
    and aggregates it into clinically meaningful scalars for the Gold Tier.
    
    Standard modality: field names are mapped to registry-standard names
    where a registry mapping exists. Unmapped fields are preserved with
    a 'nonstandard_' prefix.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if source_path.suffix == '.json':
            with open(source_path, 'r') as f:
                data = json.load(f)
            return pd.DataFrame([data])
        else:
             self.logger.error(f"Unsupported wearable format: {source_path.suffix}")
             return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
            
        # High-Frequency Aggregation Logic
        # Wearables usually output arrays of data rather than scalars.
        # We must reduce these arrays into meaningful biomarkers.
        if 'heart_rate_array' in df.columns:
            # Convert the array to a mean resting heart rate
            hr_series = df['heart_rate_array'].iloc[0]
            if isinstance(hr_series, list) and len(hr_series) > 0:
                df['mean_hr'] = sum(hr_series) / len(hr_series)
            
        if 'sleep_stages_array' in df.columns:
            # Simple heuristic for sleep efficiency calculation
            stages = df['sleep_stages_array'].iloc[0]
            if isinstance(stages, list) and len(stages) > 0:
                deep = stages.count('deep')
                rem = stages.count('rem')
                total = len(stages)
                df['sleep_efficiency'] = ((deep + rem) / total) * 100 if total > 0 else 0

        df['modality_category'] = 'digital_biomarker_wearable'
        
        # Apply registry-standard harmonization (preserve everything, rename mapped fields)
        result = self.harmonize_columns(df)
             
        return result
