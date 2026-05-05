import logging
import pandas as pd
import hashlib
from pathlib import Path
from typing import Dict, Type, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.python.core.harmonizer import BaseHarmonizer

class StratumEngine:
    """
    The central orchestration engine for the STRATUM skeletal architecture.
    Manages data transition from Bronze -> Silver -> Gold tiers.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.bronze_dir = project_root / "data" / "bronze"
        self.silver_dir = project_root / "data" / "silver"
        self.gold_dir = project_root / "data" / "gold"
        self.registry_path = project_root / "clinical_registry_master.csv"
        
        self.logger = logging.getLogger("STRATUM-Engine")
        self._plugins: Dict[str, BaseHarmonizer] = {}
        self._converters: Dict[str, any] = {} # Mapping extension -> converter

    def register_converter(self, extension: str, converter_instance: any):
        """Register a converter for a specific file extension."""
        self._converters[extension] = converter_instance
        self.logger.info(f"Registered converter for {extension}")

    def register_plugin(self, name: str, plugin_class: Type[BaseHarmonizer]):
        """Register a modality-specific harmonizer."""
        self._plugins[name] = plugin_class(self.registry_path)
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
            
        output_path = self.silver_dir / f"harmonized_{Path(source_file).stem}.csv"
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

    def generate_gold_tier(self):
        """Aggregates all silver data into a unified Multi-Modal Tensor DataFrame."""
        self.logger.info("Generating Gold Tier Cohort (Multi-Modal Outer Join)...")
        silver_files = list(self.silver_dir.glob("*.csv"))
        if not silver_files:
            self.logger.warning("No silver tier data found.")
            return
            
        dfs = []
        for f in silver_files:
            try:
                df = pd.read_csv(f)
                
                # Basic Longitudinal Temporal Alignment
                # If visit_session is missing, attempt to extract from filename or default to ses-01
                if 'visit_session' not in df.columns:
                    stem = f.stem
                    if "ses-" in stem:
                         df['visit_session'] = "ses-" + stem.split("ses-")[1].split("_")[0]
                    else:
                         df['visit_session'] = "ses-01" # Default baseline assumption
                         
                if 'participant_id' not in df.columns:
                    # Attempt to gracefully impute participant_id from file name if missing
                    # Standard BIDS/Omics: sub-001...
                    stem = f.stem
                    if "sub-" in stem:
                        extracted_id = "sub-" + stem.split("sub-")[1].split("_")[0]
                        df['participant_id'] = extracted_id
                    else:
                        df['participant_id'] = "sub-unknown"
                        
                dfs.append(df)
            except Exception as e:
                self.logger.error(f"Failed to read {f}: {e}")
        
        # Outer merge all dataframes longitudinally
        if dfs:
            gold_df = dfs[0]
            for df in dfs[1:]:
                # Merge on participant_id AND visit_session for true longitudinal tracking
                if 'participant_id' in gold_df.columns and 'participant_id' in df.columns:
                     gold_df = pd.merge(gold_df, df, on=['participant_id', 'visit_session'], how='outer', suffixes=('', '_dup'))
                else:
                     gold_df = pd.concat([gold_df, df], axis=1) # Fallback
            
            # Clean duplicated columns if any
            gold_df = gold_df.loc[:, ~gold_df.columns.str.endswith('_dup')]
            
            # Add Provenance Hashes to every harmonized patient record
            gold_df['provenance_hash_sha256'] = gold_df.apply(self._generate_provenance_hash, axis=1)
            
            output_path = self.gold_dir / "gold_multimodal_cohort.csv"
            gold_df.to_csv(output_path, index=False)
            self.logger.info(f"SUCCESS: Generated Gold Tier matrix with shape {gold_df.shape} at {output_path}")
            return gold_df
