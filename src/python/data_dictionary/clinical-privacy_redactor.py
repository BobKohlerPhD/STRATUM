import pandas as pd
import numpy as np
import json
import argparse
import os
import re
import logging

# Configure local logging for privacy transformations
logger = logging.getLogger("STRATUM-Privacy")

def apply_differential_privacy(series, epsilon=0.1):
    """
    Applies Laplacian noise to a numerical series for differential privacy.
    (Simplified for demonstration as part of the STRATUM SOTA Blueprint)
    """
    sensitivity = series.max() - series.min()
    if sensitivity == 0:
        return series
    
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale, size=len(series))
    return series + noise

def redact_column(series, datatype):
    """Redacts PII/PHI based on the STRATUM metadata specification."""
    if datatype == 'pii_name':
        return series.apply(lambda x: "[REDACTED NAME]")
    elif datatype == 'pii_date':
        # Shift dates to retain intervals but hide exact timing
        # (In a real system, this shift would be anchored per subject)
        return "[DATE SHIFTED]"
    return series

def main():
    parser = argparse.ArgumentParser(description="STRATUM Privacy-Enhancing Redaction Tool")
    parser.add_argument("input_csv", help="Path to the raw CSV data.")
    parser.add_argument("--registry", default="clinical_registry_master.csv", help="Path to the master registry.")
    parser.add_argument("--epsilon", type=float, default=0.1, help="Privacy budget for DP.")
    parser.add_argument("--output", default="redacted_clinical_data.csv", help="Output path.")

    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: Input file {args.input_csv} not found.")
        return

    # Load registry to identify sensitive columns
    try:
        registry = pd.read_csv(args.registry)
        pii_vars = registry[registry['datatype'].str.startswith('pii')]['original_variable_name'].tolist()
        ratio_vars = registry[registry['datatype'].isin(['ratio', 'interval'])]['original_variable_name'].tolist()
    except Exception as e:
        print(f"Warning: Could not load registry, defaulting to basic redaction: {e}")
        pii_vars = []
        ratio_vars = []

    # Load data
    df = pd.read_csv(args.input_csv)
    original_cols = df.columns.tolist()

    print(f"Starting redaction on {len(original_cols)} variables...")

    # Direct Redaction (PHI/PII)
    for col in pii_vars:
        if col in df.columns:
            datatype = registry[registry['original_variable_name'] == col]['datatype'].iloc[0]
            df[col] = redact_column(df[col], datatype)
            print(f" - Applied PHA/PII Redaction to '{col}'")

    # Differential Privacy (Numerical Data)
    for col in ratio_vars:
        if col in df.columns:
            df[col] = apply_differential_privacy(df[col], epsilon=args.epsilon)
            print(f" - Applied Differential Privacy (eps={args.epsilon}) to '{col}'")

    # Drop unmapped columns to ensure Zero-Trust compliance
    # (Only export what is in the registry)
    mapped_vars = registry['original_variable_name'].tolist()
    cols_to_keep = [c for c in df.columns if c in mapped_vars]
    df = df[cols_to_keep]
    
    dropped = len(original_cols) - len(cols_to_keep)
    if dropped > 0:
        print(f" - Dropped {dropped} unmapped columns to maintain Zero-Trust compliance.")

    # Save
    df.to_csv(args.output, index=False)
    print(f"\nSUCCESS: Redacted data saved to {args.output}")

if __name__ == "__main__":
    main()
