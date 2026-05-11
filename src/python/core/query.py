"""
Gold Tier Query Engine.

Provides filtered, structured access to the gold multimodal cohort
without requiring callers to understand the full column schema.
"""
import pandas as pd
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("STRATUM-Query")


def query_gold_tier(
    gold_path: Path,
    participants: Optional[List[str]] = None,
    modalities: Optional[List[str]] = None,
    variables: Optional[List[str]] = None,
    exclude_nonstandard: bool = False,
    exclude_empty: bool = True,
) -> Dict[str, Any]:
    """
    Query the gold tier cohort with flexible filtering.
    
    Args:
        gold_path: Path to gold_multimodal_cohort.csv
        participants: Filter to specific participant_ids
        modalities: Filter to specific modalities (column prefix match)
        variables: Filter to specific variable names (partial match)
        exclude_nonstandard: If True, exclude nonstandard_ prefixed columns
        exclude_empty: If True, drop columns that are entirely NaN
    
    Returns:
        Dict with query results, metadata, and filtered data as records
    """
    if not gold_path.exists():
        return {"error": "Gold tier not yet generated. Run generate_gold_tier first.", "data": []}
    
    # Standard pandas NAs minus 'n/a'
    bids_na_values = ['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL', 'NaN', 'None', 'nan', 'null']
    df = pd.read_csv(gold_path, keep_default_na=False, na_values=bids_na_values)
    original_shape = df.shape
    
    # Filter participants
    if participants and 'participant_id' in df.columns:
        df = df[df['participant_id'].isin(participants)]
    
    # Filter modalities (by column prefix)
    if modalities:
        keep_cols = ['participant_id', 'visit_session', 'provenance_hash_sha256']
        for mod in modalities:
            keep_cols.extend([c for c in df.columns if c.startswith(f"{mod}.")])
        df = df[[c for c in keep_cols if c in df.columns]]
    
    # Filter variables (partial match)
    if variables:
        keep_cols = ['participant_id', 'visit_session']
        for var in variables:
            keep_cols.extend([c for c in df.columns if var.lower() in c.lower()])
        df = df[[c for c in keep_cols if c in df.columns]]
    
    # Exclude nonstandard
    if exclude_nonstandard:
        df = df[[c for c in df.columns if 'nonstandard_' not in c]]
    
    # Exclude entirely empty columns
    if exclude_empty:
        df = df.dropna(axis=1, how='all')
    
    # Build response
    records = df.to_dict(orient='records')
    
    # Clean NaN values for JSON serialization
    clean_records = []
    for record in records:
        clean = {k: (v if pd.notna(v) else None) for k, v in record.items()}
        clean_records.append(clean)
    
    return {
        "query": {
            "participants": participants,
            "modalities": modalities,
            "variables": variables,
            "exclude_nonstandard": exclude_nonstandard,
        },
        "result_shape": list(df.shape),
        "original_shape": list(original_shape),
        "columns": list(df.columns),
        "data": clean_records,
    }


def get_available_modalities(gold_path: Path) -> Dict[str, List[str]]:
    """List all modalities and their variables from the gold tier."""
    if not gold_path.exists():
        return {"error": "Gold tier not yet generated."}
    
    # Standard pandas NAs minus 'n/a'
    bids_na_values = ['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL', 'NaN', 'None', 'nan', 'null']
    df = pd.read_csv(gold_path, nrows=0, keep_default_na=False, na_values=bids_na_values)
    modalities: Dict[str, List[str]] = {}
    
    for col in df.columns:
        if '.' in col and col not in ('participant_id', 'visit_session', 'provenance_hash_sha256'):
            mod, var = col.split('.', 1)
            if mod not in modalities:
                modalities[mod] = []
            modalities[mod].append(var)
    
    return modalities
