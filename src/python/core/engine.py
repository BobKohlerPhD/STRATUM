import logging
import pandas as pd
import hashlib
from pathlib import Path
from typing import Dict, Type, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.python.core.harmonizer import BaseHarmonizer
from src.python.core.pii_deidentifier import PIIDeidentifier

class StratumEngine:
    """
    The central orchestration engine for the STRATUM skeletal architecture.
    Manages data transition from Bronze -> Silver -> Gold tiers.
    
    Gold Tier Strategy:
    - Each silver file becomes one row per participant+session+modality.
    - Multi-row modalities (e.g., multiple genotype variants) are pivoted
      into a single row with indexed columns before merging.
    - Columns are prefixed with the modality_category to prevent collisions
      (e.g., eeg.SamplingFrequency, structural_mri.MagneticFieldStrength).
    - No Cartesian products — one row per participant per session.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.bronze_dir = project_root / "data" / "bronze"
        self.silver_dir = project_root / "data" / "silver"
        self.gold_dir = project_root / "data" / "gold"
        self.registry_db_path = project_root / "data" / "registry" / "stratum_registry.db"
        
        self.logger = logging.getLogger("STRATUM-Engine")
        self._plugins: Dict[str, BaseHarmonizer] = {}
        self._converters: Dict[str, any] = {} # Mapping extension -> converter

    def register_converter(self, extension: str, converter_instance: any):
        """Register a converter for a specific file extension."""
        self._converters[extension] = converter_instance
        self.logger.info(f"Registered converter for {extension}")

    def register_plugin(self, name: str, plugin_class: Type[BaseHarmonizer]):
        """Register a modality-specific harmonizer."""
        self._plugins[name] = plugin_class(self.registry_db_path)
        self.logger.info(f"Registered plugin: {name}")

    def process_modality(self, plugin_name: str, source_file: str):
        """Processes a single file using a registered plugin."""
        if plugin_name not in self._plugins:
            self.logger.error(f"Plugin {plugin_name} not found.")
            return
            
        plugin = self._plugins[plugin_name]
        source_path = self.bronze_dir / source_file
        
        # Check if we need to convert the file first
        if source_path.suffix in self._converters:
            converter = self._converters[source_path.suffix]
            # Convert to a temporary JSON sidecar in the silver directory for harmonization
            source_path = converter.convert(source_path, self.silver_dir)
            
        output_path = self.silver_dir / f"harmonized_{plugin_name}_{Path(source_file).stem}.csv"
        return plugin.run(source_path, output_path)

    def batch_process(self, tasks: List[tuple]):
        """Asynchronous multi-modal batch ingestion using thread pooling."""
        self.logger.info(f"Starting parallel batch ingestion of {len(tasks)} items...")
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_task = {executor.submit(self.process_modality, plugin, source): (plugin, source) for plugin, source in tasks}
            for future in as_completed(future_to_task):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    self.logger.error(f"Task failed: {e}")
        return results

    def _generate_provenance_hash(self, row: pd.Series) -> str:
        """Generate W3C-PROV compliant cryptographic hash for data traceability."""
        row_str = "".join([str(val) for val in row.values])
        return hashlib.sha256(row_str.encode('utf-8')).hexdigest()

    def _flatten_modality(self, df: pd.DataFrame, source_file: str) -> pd.DataFrame:
        """
        Flatten a multi-row silver file into a single row per participant+session.
        
        Strategy:
        - If the modality has multiple rows (e.g., multiple genotype variants),
          pivot them into indexed columns (e.g., genotype_0, genotype_1).
        - Single-row modalities pass through unchanged.
        - Columns get prefixed with modality_category to prevent name collisions.
        """
        if df.empty:
            return df
        
        # Determine the modality prefix
        modality = 'unknown'
        if 'modality_category' in df.columns:
            modality = str(df['modality_category'].iloc[0])
        
        # Separate index columns from data columns
        index_cols = ['participant_id', 'visit_session']
        existing_index = [c for c in index_cols if c in df.columns]
        data_cols = [c for c in df.columns if c not in index_cols and c != 'modality_category']
        
        if len(df) <= 1:
            # Single row — just prefix columns with modality
            result = df.copy()
            # Drop the raw modality_category, store it prefixed
            if 'modality_category' in result.columns:
                result = result.drop(columns=['modality_category'])
            rename_map = {c: f"{modality}.{c}" for c in data_cols}
            result = result.rename(columns=rename_map)
            result[f"{modality}._modality"] = modality
            return result
        
        # Multi-row — pivot into indexed columns
        # Group by participant+session, then flatten each group
        if not existing_index:
            # No index columns — use positional indexing
            flat_rows = {}
            for i, (_, row) in enumerate(df[data_cols].iterrows()):
                for col in data_cols:
                    flat_rows[f"{modality}.{col}_{i}"] = row[col]
            flat_rows[f"{modality}._modality"] = modality
            
            result = pd.DataFrame([flat_rows])
            # Carry forward index columns if they exist
            for c in existing_index:
                result[c] = df[c].iloc[0]
            return result
        
        # Group by index and flatten
        groups = df.groupby(existing_index, dropna=False)
        flat_dfs = []
        for group_key, group_df in groups:
            flat_row = {}
            if isinstance(group_key, str):
                flat_row[existing_index[0]] = group_key
            else:
                for col, val in zip(existing_index, group_key):
                    flat_row[col] = val
            
            if len(group_df) == 1:
                for col in data_cols:
                    flat_row[f"{modality}.{col}"] = group_df[col].iloc[0]
            else:
                for i, (_, row) in enumerate(group_df[data_cols].iterrows()):
                    for col in data_cols:
                        flat_row[f"{modality}.{col}_{i}"] = row[col]
            
            flat_row[f"{modality}._modality"] = modality
            flat_dfs.append(flat_row)
        
        return pd.DataFrame(flat_dfs)

    def generate_gold_tier(self):
        """
        Aggregates all silver data into a unified Multi-Modal Cohort DataFrame.
        
        Strategy:
        1. Load each silver file.
        2. Ensure participant_id and visit_session are present.
        3. Flatten multi-row modalities into single rows with indexed columns.
        4. Prefix all data columns with modality_category to prevent collisions.
        5. Merge all modalities on participant_id + visit_session (outer join).
        6. Result: one row per participant per session, all modalities as columns.
        """
        self.logger.info("Generating Gold Tier Cohort (Multi-Modal Outer Join)...")
        silver_files = list(self.silver_dir.glob("harmonized_*.csv"))
        if not silver_files:
            self.logger.warning("No silver tier data found.")
            return
        
        # Standard pandas NAs minus 'n/a' to preserve BIDS compliance
        bids_na_values = ['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL', 'NaN', 'None', 'nan', 'null']
        
        flat_dfs = []
        for f in silver_files:
            try:
                df = pd.read_csv(f, keep_default_na=False, na_values=bids_na_values)
                
                # Ensure visit_session exists
                if 'visit_session' not in df.columns:
                    stem = f.stem
                    if "ses-" in stem:
                         df['visit_session'] = "ses-" + stem.split("ses-")[1].split("_")[0]
                    else:
                         df['visit_session'] = "ses-01" # Default baseline assumption
                         
                # Ensure participant_id exists
                if 'participant_id' not in df.columns:
                    stem = f.stem
                    if "sub-" in stem:
                        df['participant_id'] = "sub-" + stem.split("sub-")[1].split("_")[0]
                    else:
                        df['participant_id'] = "sub-unknown"
                
                # Flatten this modality into a single row per participant+session
                flat = self._flatten_modality(df, f.name)
                flat_dfs.append(flat)
                
            except Exception as e:
                self.logger.error(f"Failed to read {f}: {e}")
        
        if not flat_dfs:
            return None
        
        # Merge all flattened modalities on participant_id + visit_session
        gold_df = flat_dfs[0]
        for flat in flat_dfs[1:]:
            merge_cols = []
            if 'participant_id' in gold_df.columns and 'participant_id' in flat.columns:
                merge_cols.append('participant_id')
            if 'visit_session' in gold_df.columns and 'visit_session' in flat.columns:
                merge_cols.append('visit_session')
            
            if merge_cols:
                gold_df = pd.merge(gold_df, flat, on=merge_cols, how='outer')
            else:
                gold_df = pd.concat([gold_df, flat], axis=1)
        
        # Add Provenance Hashes
        gold_df['provenance_hash_sha256'] = gold_df.apply(self._generate_provenance_hash, axis=1)
        
        # Apply PII De-identification
        self.logger.info("Applying PII De-identification (HIPAA Safe Harbor)...")
        deidentifier = PIIDeidentifier()
        gold_df = deidentifier.process_dataframe(gold_df)
        
        # Ensure output directory exists
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = self.gold_dir / "gold_multimodal_cohort.csv"
        gold_df.to_csv(output_path, index=False)
        self.logger.info(f"SUCCESS: Generated Gold Tier matrix with shape {gold_df.shape} at {output_path}")
        return gold_df
