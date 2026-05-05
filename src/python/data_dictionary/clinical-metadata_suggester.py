import pandas as pd
import json
from typing import List, Dict, Any

def suggest_metadata(file_path: str, sample_rows: int = 5) -> List[Dict[str, Any]]:
    """
    Analyzes a raw data file and generates a skeleton for the clinical_registry_master.csv.
    In a real-world scenario, this would be passed to an LLM to refine the generalized names.
    
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
                "generalized_variable_name": col.lower().replace(" ", "_").replace("-", "_"), # Placeholder for LLM refinement
                "datatype": datatype,
                "levels": json.dumps([str(v) for v in sample_vals[:10]]) if datatype in ['nominal', 'ordinal'] else "[]",
                "sample_values": str(sample_vals[:3])
            }
            suggestions.append(suggestion)

        return suggestions
    except Exception as e:
        return [{"error": str(e)}]

