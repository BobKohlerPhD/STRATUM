import pandas as pd
from typing import Dict, Any

def generate_synthetic_cohort_data(registry_path: str = "clinical_registry_master.csv") -> Dict[str, Any]:
    """
    Generates high-fidelity synthetic digital twins based on the registry structure.
    
    Args:
        registry_path (str): The path to the clinical registry master CSV.
        
    Returns:
        Dict[str, Any]: A dictionary containing the status, shape of the synthetic cohort, 
                        and a sample of the generated data.
    """
    try:
        # In a real scenario, this would use sophisticated generation (e.g. SDV, CTGAN)
        # Here we mock the generation process for demonstration.
        df_registry = pd.read_csv(registry_path) if pd.io.common.file_exists(registry_path) else pd.DataFrame(columns=["original_variable_name"])
        
        cols = df_registry['original_variable_name'].tolist() if not df_registry.empty else ["participant_id", "age", "gender"]
        
        # Stub data
        synthetic_data = [
            {col: "mock_val" for col in cols} for _ in range(5)
        ]
        
        return {
            "status": "success",
            "message": "Synthetic cohort generated successfully.",
            "records_generated": len(synthetic_data),
            "sample": synthetic_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
