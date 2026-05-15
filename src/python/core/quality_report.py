"""
Modality Quality Report Generator.

Produces per-modality data quality summaries across all subjects,
including completeness metrics, value distributions, and anomaly flags.
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("STRATUM-QualityReport")


def generate_modality_report(
    silver_dir: Path,
    modality_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a data quality report for each modality in the silver tier.
    
    Args:
        silver_dir: Path to the silver directory
        modality_filter: Optional modality category to filter to
    
    Returns:
        Dict with per-modality quality metrics
    """
    silver_files = list(silver_dir.glob("harmonized_*.csv"))
    
    if not silver_files:
        return {"error": "No silver tier files found. Run processing first."}
    
    reports: Dict[str, Any] = {}
    
    # Standard clinical NAs
    stratum_na_values = ['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL', 'NaN', 'None', 'nan', 'null']

    for f in silver_files:
        try:
            df = pd.read_csv(f, keep_default_na=False, na_values=stratum_na_values)
            if df.empty:
                continue
            
            modality = df.get('modality_category', pd.Series(['unknown'])).iloc[0]
            
            if modality_filter and modality != modality_filter:
                continue
            
            # Build quality metrics
            report = _analyze_dataframe(df, f.name, modality)
            
            if modality not in reports:
                reports[modality] = {
                    "modality": modality,
                    "files": [],
                    "total_records": 0,
                    "combined_metrics": {},
                }
            
            reports[modality]["files"].append(report)
            reports[modality]["total_records"] += len(df)
            
        except Exception as e:
            logger.error(f"Failed to analyze {f.name}: {e}")
    
    # Add combined metrics per modality
    for mod, data in reports.items():
        data["file_count"] = len(data["files"])
        subjects = set()
        for file_report in data["files"]:
            if file_report.get("subject_id"):
                subjects.add(file_report["subject_id"])
        data["unique_subjects"] = list(subjects)
    
    return {
        "modality_count": len(reports),
        "total_silver_files": len(silver_files),
        "modalities": reports,
    }


def _analyze_dataframe(df: pd.DataFrame, filename: str, modality: str) -> Dict[str, Any]:
    """Analyze a single silver-tier DataFrame for quality metrics."""
    
    # Extract subject from filename
    import re
    sub_match = re.search(r'sub-([a-zA-Z0-9]+)', filename)
    subject_id = f"sub-{sub_match.group(1)}" if sub_match else None
    
    report = {
        "filename": filename,
        "subject_id": subject_id,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": {},
    }
    
    # Per-column analysis
    for col in df.columns:
        if col == 'modality_category':
            continue
        
        col_report = {
            "dtype": str(df[col].dtype),
            "non_null_count": int(df[col].notna().sum()),
            "null_count": int(df[col].isna().sum()),
            "completeness": round(df[col].notna().mean(), 3),
            "is_standard_field": not col.startswith('nonstandard_'),
        }
        
        # Numeric stats
        if pd.api.types.is_numeric_dtype(df[col]):
            non_null = df[col].dropna()
            if len(non_null) > 0:
                col_report["min"] = float(non_null.min())
                col_report["max"] = float(non_null.max())
                col_report["mean"] = round(float(non_null.mean()), 4)
                col_report["std"] = round(float(non_null.std()), 4) if len(non_null) > 1 else 0.0
                
                # Anomaly detection: values > 3 std from mean
                if len(non_null) > 2 and non_null.std() > 0:
                    z_scores = np.abs((non_null - non_null.mean()) / non_null.std())
                    col_report["outlier_count"] = int((z_scores > 3).sum())
        else:
            # Categorical stats
            non_null = df[col].dropna()
            if len(non_null) > 0:
                col_report["unique_values"] = int(non_null.nunique())
                col_report["sample_values"] = non_null.unique()[:5].tolist()
                
                # Flag potential PII
                na_like = ['n/a', 'na', 'none', 'null', '']
                na_count = non_null.astype(str).str.lower().isin(na_like).sum()
                col_report["na_like_values"] = int(na_count)
        
        report["columns"][col] = col_report
    
    # Overall quality score
    completeness_scores = [v["completeness"] for v in report["columns"].values()]
    report["overall_completeness"] = round(sum(completeness_scores) / max(len(completeness_scores), 1), 3)
    
    # Flag quality issues
    issues = []
    for col_name, col_data in report["columns"].items():
        if col_data["completeness"] < 0.5:
            issues.append(f"Low completeness ({col_data['completeness']:.0%}) for '{col_name}'")
        if col_data.get("outlier_count", 0) > 0:
            issues.append(f"{col_data['outlier_count']} outlier(s) in '{col_name}'")
    report["quality_issues"] = issues
    
    return report
