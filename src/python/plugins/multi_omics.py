import pandas as pd
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class MultiOmicsHarmonizer(BaseHarmonizer):
    """
    Standard Plugin for Multi-Omics datasets (Genomics, Proteomics, Metabolomics).
    Handles tabular data ingestion (VCF-parsed CSV or Mass-Spec reports).
    
    Non-BIDS modality: field names are mapped to BIDS-compatible names
    where a registry mapping exists. Unmapped fields are preserved with
    a 'nonstandard_' prefix.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if source_path.suffix == '.csv':
            return pd.read_csv(source_path)
        elif source_path.suffix == '.parquet':
            return pd.read_parquet(source_path)
        else:
            self.logger.error(f"Unsupported Omics format: {source_path.suffix}")
            return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Logic to infer omics sub-modality (before harmonization so the column exists)
        if 'rsid' in df.columns:
            df['modality_category'] = 'genomics'
        elif 'protein_id' in df.columns:
            df['modality_category'] = 'proteomics'
        elif 'metabolite_name' in df.columns:
            df['modality_category'] = 'metabolomics'
        
        # Apply BIDS-first harmonization (preserve everything, rename non-BIDS)
        result = self.harmonize_columns(df)
            
        return result
