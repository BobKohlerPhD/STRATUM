import pandas as pd
from typing import Tuple

# Simplified integrity check for public framework
# This ensures required columns are present in the master registry

required_columns = [
    'original_variable_name',
    'generalized_variable_name',
    'datatype',
    'levels'
]

def check_integrity(file_path: str = 'clinical_registry_master.csv') -> Tuple[bool, str]:
    """
    Checks if the required columns are present in the clinical registry.
    
    Args:
        file_path (str): Path to the registry CSV file.
        
    Returns:
        Tuple[bool, str]: A boolean indicating success, and a descriptive message.
    """
    try:
        df = pd.read_csv(file_path, nrows=0)
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            return False, f"SCHEMA ERROR: Missing columns: {', '.join(missing)}"
        
        return True, "SCHEMA OK: All required columns present."
    except FileNotFoundError:
        return False, f"ERROR: {file_path} not found."
    except Exception as e:
        return False, f"ERROR: {str(e)}"

