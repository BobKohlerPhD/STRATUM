import pandas as pd
import re
import os
from typing import Tuple, List

# Enhanced Registry Integrity Check
# Validates both Schema and Data Quality

REQUIRED_COLUMNS = [
    'original_variable_name', 'standard_name', 'loinc_code', 'sdtm_variable',
    'omop_concept_id', 'datatype', 'modality', 'vocabulary'
]

VALID_DATATYPES = ['nominal', 'ordinal', 'ratio', 'interval', 'pii_name', 'pii_date', 'pii_note']

def validate_loinc(code: str) -> bool:
    if pd.isna(code) or code == '': return True
    return bool(re.match(r'^\d{1,7}-\d$', str(code)))

def check_integrity(file_path: str = 'clinical_registry_master.csv') -> Tuple[bool, List[str]]:
    errors = []
    
    if not os.path.exists(file_path):
        return False, [f"CRITICAL: {file_path} not found."]

    try:
        df = pd.read_csv(file_path)
        
        # 1. Schema Check
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            errors.append(f"SCHEMA ERROR: Missing columns: {', '.join(missing_cols)}")

        # 2. Data Quality Check (Row by Row)
        for idx, row in df.iterrows():
            var_name = row.get('original_variable_name', f"Row {idx}")
            
            # Check LOINC format
            loinc = row.get('loinc_code')
            if loinc and not validate_loinc(loinc):
                errors.append(f"DATA ERROR [{var_name}]: Invalid LOINC format '{loinc}'")
            
            # Check OMOP ID type
            omop_id = row.get('omop_concept_id')
            try:
                if pd.notna(omop_id):
                    int(omop_id)
            except:
                errors.append(f"DATA ERROR [{var_name}]: OMOP Concept ID '{omop_id}' must be an integer")
                
            # Check Datatype
            dtype = row.get('datatype')
            if dtype not in VALID_DATATYPES:
                errors.append(f"DATA ERROR [{var_name}]: Invalid datatype '{dtype}'")

        if errors:
            return False, errors
        
        return True, ["SCHEMA & DATA OK: All checks passed."]

    except Exception as e:
        return False, [f"CRITICAL ERROR: {str(e)}"]

if __name__ == "__main__":
    success, messages = check_integrity()
    has_error = False
    for msg in messages:
        print(msg)
        if "ERROR" in msg or "CRITICAL" in msg:
            has_error = True
    if has_error:
        exit(1)
    exit(0)
