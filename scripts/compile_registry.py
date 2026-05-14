import pandas as pd
import sqlite3
import os
import json
import re
from pathlib import Path

REGISTRY_SRC = 'clinical_registry_master.csv'
REGISTRY_DIR = Path('data/registry')
DB_PATH = REGISTRY_DIR / 'stratum_registry.db'

def modularize_and_compile():
    print(f"Reading source registry: {REGISTRY_SRC}")
    df = pd.read_csv(REGISTRY_SRC)
    
    # 1. Modularize by Modality
    modalities = df['modality'].unique()
    for mod in modalities:
        mod_file = REGISTRY_DIR / f"{mod}.csv"
        mod_df = df[df['modality'] == mod]
        mod_df.to_csv(mod_file, index=False)
        print(f"  - Created modular registry: {mod_file}")

    # 2. Extract Categorical Levels to Lookup Table
    print("Extracting categorical levels...")
    levels_data = []
    for idx, row in df.iterrows():
        levels_str = row['levels']
        if pd.isna(levels_str) or levels_str == '[]':
            continue
        
        try:
            # Parse the list string
            levels_list = json.loads(levels_str.replace("'", '"'))
            for item in levels_list:
                if '=' in item:
                    code, label = item.split('=', 1)
                    levels_data.append({
                        'standard_name': row['standard_name'],
                        'code': code.strip(),
                        'label': label.strip()
                    })
        except Exception as e:
            print(f"  - Error parsing levels for {row['standard_name']}: {e}")

    levels_df = pd.DataFrame(levels_data)
    levels_df.to_csv(REGISTRY_DIR / 'categorical_lookups.csv', index=False)
    print(f"  - Created categorical lookups: {REGISTRY_DIR / 'categorical_lookups.csv'}")

    # 3. Compile to SQLite for High Performance
    print(f"Compiling to SQLite: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Clean column names for SQL
    df.columns = [c.replace(' ', '_') for c in df.columns]
    df.to_sql('variables', conn, if_exists='replace', index=False)
    
    levels_df.to_sql('categorical_lookups', conn, if_exists='replace', index=False)
    
    # Create indexes for speed
    conn.execute("CREATE INDEX idx_orig_name ON variables (original_variable_name)")
    conn.execute("CREATE INDEX idx_std_name ON variables (standard_name)")
    conn.execute("CREATE INDEX idx_loinc ON variables (loinc_code)")
    conn.execute("CREATE INDEX idx_omop ON variables (omop_concept_id)")
    
    conn.close()
    print("Compilation complete.")

if __name__ == "__main__":
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    modularize_and_compile()
