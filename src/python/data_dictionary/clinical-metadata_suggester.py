import pandas as pd
import json
from typing import List, Dict, Any

def suggest_metadata(file_path: str, sample_rows: int = 5) -> List[Dict[str, Any]]:
    """
    Analyzes a raw data file and generates a skeleton for the clinical_registry_master.csv.
    
    Args:
        file_path (str): Path to the raw CSV file.
        sample_rows (int): Number of rows to analyze.
        
    Returns:
        List[Dict[str, Any]]: A list of metadata suggestion dictionaries.
    """
    try:
        # Read only a few rows to analyze structure
        df = pd.read_csv(file_path, nrows=sample_rows)
        suggestions = []

        for col in df.columns:
            sample_vals = df[col].dropna().unique().tolist()
            
            # Basic type inference
            if df[col].dtype in ['int64', 'float64']:
                datatype = 'ratio' if len(sample_vals) > 10 else 'ordinal'
            else:
                datatype = 'nominal'

            # Build a suggestion object
            suggestion = {
                "original_variable_name": col,
                "standard_name": col.lower().replace(" ", "_").replace("-", "_"),
                "loinc_code": "",
                "sdtm_variable": "",
                "accession_id": "",
                "hed_tags": "",
                "omop_concept_id": "0",
                "cde_id": "",
                "phenx_id": "",
                "umls_cui": "",
                "datatype": datatype,
                "levels": json.dumps([str(v) for v in sample_vals[:10]]) if datatype in ['nominal', 'ordinal'] else "[]",
                "units": "",
                "description": f"Auto-generated suggestion for {col}",
                "modality": "unknown",
                "vocabulary": "STRATUM",
                "sample_values": str(sample_vals[:3])
            }
            suggestions.append(suggestion)

        return suggestions
    except Exception as e:
        return [{"error": str(e)}]
