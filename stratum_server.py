import asyncio
import logging
import json
import os
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from pydantic import BaseModel, Field

# Import the core Engine
from src.python.core.engine import StratumEngine

# Import Plugins
from src.python.plugins.imaging_bids import BIDSHarmonizer
from src.python.plugins.multi_omics import MultiOmicsHarmonizer
from src.python.plugins.wearables import WearableHarmonizer
from src.python.plugins.clinical_nlp import ClinicalNLPHarmonizer
from src.python.plugins.biospecimens import BiospecimenHarmonizer
from src.python.plugins.clinical_assessments import ClinicalAssessmentHarmonizer
from src.python.plugins.fmri_nilearn import fMRINilearnHarmonizer
from src.python.plugins.eeg_bids import EEGBIDSHarmonizer
from src.python.plugins.eeg_mne import EEGMNEHarmonizer
from src.python.plugins.ehr_fhir import FHIRHarmonizer

# Import Converters
from src.python.plugins.converter_nibabel import NibabelConverter
from src.python.plugins.converter_edf_to_bids import EDFToBIDSConverter
from src.python.plugins.converter_dicom_to_bids import DICOMToBIDSConverter

# Import Tool Implementations
from src.python.data_dictionary.registry_integrity_check import check_integrity
import importlib
_metadata_mod = importlib.import_module('src.python.data_dictionary.clinical-metadata_suggester')
suggest_metadata = _metadata_mod.suggest_metadata
_variables_mod = importlib.import_module('src.python.variables.clinical-variables_list')
get_filtered_variable_names = _variables_mod.get_filtered_variable_names
from src.python.variables.generate_test_data import generate_synthetic_cohort_data
from src.python.variables.clinical_variables_gather import gather_clinical_variables

# Import New Tool Modules
from src.python.core.discovery import discover_subjects, build_task_list, get_processing_status as _get_processing_status
from src.python.core.bids_validator import validate_bids_subject
from src.python.core.query import query_gold_tier as _query_gold_tier, get_available_modalities
from src.python.core.quality_report import generate_modality_report as _generate_modality_report

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/stratum_audit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("STRATUM-Orchestrator")

# Initialize the STRATUM MCP Server
mcp = FastMCP("STRATUM Orchestrator", instructions="STRATUM: Agent-driven orchestration of multimodal clinical data. BIDS-first harmonization across neuroimaging, EEG, omics, wearables, and clinical data.")

# Initialize the Engine
PROJECT_ROOT = Path(os.environ.get("STRATUM_PROJECT_ROOT", Path(__file__).parent.resolve()))
engine = StratumEngine(PROJECT_ROOT)

# Register All Plugins
engine.register_plugin("bids", BIDSHarmonizer)
engine.register_plugin("omics", MultiOmicsHarmonizer)
engine.register_plugin("wearables", WearableHarmonizer)
engine.register_plugin("nlp", ClinicalNLPHarmonizer)
engine.register_plugin("biospecimens", BiospecimenHarmonizer)
engine.register_plugin("assessments", ClinicalAssessmentHarmonizer)
engine.register_plugin("fmri_signal", fMRINilearnHarmonizer)
engine.register_plugin("eeg", EEGBIDSHarmonizer)
engine.register_plugin("eeg_signal", EEGMNEHarmonizer)
engine.register_plugin("ehr_fhir", FHIRHarmonizer)

# Register Converters
engine.register_converter(".nii", NibabelConverter())
engine.register_converter(".edf", EDFToBIDSConverter())
engine.register_converter(".bdf", EDFToBIDSConverter())
engine.register_converter(".dcm", DICOMToBIDSConverter())
engine.register_converter(".DCM", DICOMToBIDSConverter())

# Models
class SuggestMetadataInput(BaseModel):
    file_path: str = Field(..., description="Path to the raw CSV file to analyze")
    sample_rows: Optional[int] = Field(default=5, description="Number of rows to sample", ge=1, le=100)

class ListVariablesInput(BaseModel):
    keyword: Optional[str] = Field(default=None, description="Keyword to search for in variable names")

class QueryGoldInput(BaseModel):
    participants: Optional[List[str]] = Field(default=None, description="Filter by participant IDs, e.g. ['sub-001', 'sub-120']")
    modalities: Optional[List[str]] = Field(default=None, description="Filter by modality names, e.g. ['eeg', 'genomics']")
    variables: Optional[List[str]] = Field(default=None, description="Filter by variable name substring, e.g. ['SamplingFrequency']")
    exclude_nonstandard: bool = Field(default=False, description="If true, exclude nonstandard_ prefixed columns")

class IngestSubjectInput(BaseModel):
    subject_id: Optional[str] = Field(default=None, description="Specific subject to ingest (e.g. 'sub-120'). If omitted, discovers and ingests ALL subjects.")
    dry_run: bool = Field(default=False, description="If true, only discover and report — don't process.")

class ValidateBIDSInput(BaseModel):
    subject_id: str = Field(..., description="Subject ID to validate (e.g. 'sub-120')")

class ModalityReportInput(BaseModel):
    modality: Optional[str] = Field(default=None, description="Filter to a specific modality (e.g. 'eeg', 'functional_mri'). If omitted, reports all.")

# --- Modality Processing Tools ---

@mcp.tool()
async def process_imaging(filename: str) -> str:
    """Processes neuroimaging metadata (JSON/sidecars) using the BIDS plugin."""
    return await _run_process("bids", filename)

@mcp.tool()
async def process_fmri_signal(filename: str) -> str:
    """Processes 4D fMRI NIfTI files and computes BOLD signal amplitudes."""
    return await _run_process("fmri_signal", filename)

@mcp.tool()
async def process_omics(filename: str) -> str:
    """Processes multi-omics data (genomics, proteomics, metabolomics)."""
    return await _run_process("omics", filename)

@mcp.tool()
async def process_wearables(filename: str) -> str:
    """Processes digital biomarkers and wearable time-series data."""
    return await _run_process("wearables", filename)

@mcp.tool()
async def process_nlp(filename: str) -> str:
    """Processes unstructured clinical notes and extracts phenotypes."""
    return await _run_process("nlp", filename)

@mcp.tool()
async def process_biospecimens(filename: str) -> str:
    """Processes laboratory readouts and biospecimen metadata."""
    return await _run_process("biospecimens", filename)

@mcp.tool()
async def process_assessments(filename: str) -> str:
    """Processes clinical surveys and psychometric assessments."""
    return await _run_process("assessments", filename)

@mcp.tool()
async def process_eeg(filename: str) -> str:
    """Processes EEG BIDS metadata (JSON)."""
    return await _run_process("eeg", filename)

@mcp.tool()
async def process_eeg_signal(filename: str) -> str:
    """Processes raw EEG signal files (e.g. .set) and computes Global Field Power."""
    return await _run_process("eeg_signal", filename)

async def _run_process(plugin_name: str, filename: str) -> str:
    try:
        result_df = await asyncio.to_thread(engine.process_modality, plugin_name, filename)
        if result_df is not None and not result_df.empty:
            return f"Successfully processed {filename} via {plugin_name} plugin."
        else:
            return f"Failed to process {filename} or no mapped variables found."
    except Exception as e:
        logger.exception(f"Error processing {filename} with {plugin_name}: {e}")
        return f"Error: {str(e)}"

# --- Data Management Tools ---

@mcp.tool()
async def list_data_tiers() -> str:
    """Lists the current contents of Bronze, Silver, and Gold tiers."""
    summary = []
    for tier in ["bronze", "silver", "gold"]:
        tier_path = PROJECT_ROOT / "data" / tier
        if not tier_path.exists():
            continue
        files = list(tier_path.glob("**/*"))
        files = [f for f in files if f.is_file()]
        summary.append(f"### {tier.upper()} TIER")
        summary.append(f"Total Files: {len(files)}")
        for f in files[:5]:
            summary.append(f" - {f.relative_to(tier_path)}")
        if len(files) > 5:
            summary.append(" - ...")
        summary.append("")
    return "\n".join(summary)

@mcp.tool()
async def generate_gold_tier() -> str:
    """Aggregates all silver data into a unified Gold Tier multi-modal cohort."""
    try:
        df = await asyncio.to_thread(engine.generate_gold_tier)
        if df is not None:
            return f"Successfully generated Gold Tier. Shape: {df.shape}. File: data/gold/gold_multimodal_cohort.csv"
        return "Failed to generate Gold Tier (no silver data found?)"
    except Exception as e:
        logger.exception(f"Error generating gold tier: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def check_registry_integrity() -> str:
    """Automated verification of the Master Clinical Registry."""
    try:
        registry_path = PROJECT_ROOT / "clinical_registry_master.csv"
        is_valid, messages = await asyncio.to_thread(check_integrity, str(registry_path))
        return "\n".join(messages)
    except Exception as e:
        logger.exception(f"Error checking registry integrity: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def generate_synthetic_cohort() -> str:
    """High-fidelity orchestration of synthetic digital twins."""
    try:
        registry_path = PROJECT_ROOT / "clinical_registry_master.csv"
        result = await asyncio.to_thread(generate_synthetic_cohort_data, str(registry_path))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error generating synthetic cohort: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def suggest_metadata_from_raw(params: SuggestMetadataInput) -> str:
    """AI-assisted inference of metadata from cryptic raw headers."""
    try:
        full_file_path = PROJECT_ROOT / params.file_path
        if not full_file_path.exists():
            return f"Error: File not found at {full_file_path}"
        result = await asyncio.to_thread(suggest_metadata, str(full_file_path), params.sample_rows)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error suggesting metadata: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def list_registry_variables(params: ListVariablesInput) -> str:
    """Resilient discovery of clinical variables with fuzzy matching."""
    try:
        current_cwd = os.getcwd()
        os.chdir(PROJECT_ROOT)
        try:
            result = await asyncio.to_thread(get_filtered_variable_names, params.keyword)
        finally:
            os.chdir(current_cwd)
        if not result:
            return f"No variables found matching keyword: {params.keyword}" if params.keyword else "No variables found."
        return "\n".join([f"- {v}" for v in result])
    except Exception as e:
        logger.exception(f"Error listing registry variables: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def gather_variables() -> str:
    """Native Python-based statistical aggregation and harmonization."""
    try:
        result = await asyncio.to_thread(gather_clinical_variables)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error gathering variables: {e}")
        return f"Error: {str(e)}"

# --- NEW: Auto-Discovery & Ingestion ---

@mcp.tool()
async def ingest_new_subject(params: IngestSubjectInput) -> str:
    """Auto-discover and process data for a subject (or all subjects). Scans bronze tier, classifies files by modality, routes to correct plugins, and generates silver tier outputs."""
    try:
        manifests = await asyncio.to_thread(discover_subjects, engine.bronze_dir)
        
        if params.subject_id:
            if params.subject_id not in manifests:
                return json.dumps({"error": f"Subject {params.subject_id} not found in bronze tier. Available: {list(manifests.keys())}"})
            manifests = {params.subject_id: manifests[params.subject_id]}
        
        results = []
        for sid, manifest in manifests.items():
            summary = manifest.to_dict()
            
            if not params.dry_run:
                tasks = build_task_list(manifest)
                if tasks:
                    await asyncio.to_thread(engine.batch_process, tasks)
                    summary["status"] = "processed"
                    summary["tasks_executed"] = len(tasks)
                else:
                    summary["status"] = "no_processable_files"
            else:
                summary["status"] = "dry_run"
            
            results.append(summary)
        
        return json.dumps({"subjects_processed": len(results), "results": results}, indent=2)
    except Exception as e:
        logger.exception(f"Error in ingest_new_subject: {e}")
        return json.dumps({"error": str(e)})

# --- NEW: Gold Tier Query ---

@mcp.tool()
async def query_gold(params: QueryGoldInput) -> str:
    """Query the gold tier cohort with filters. Filter by participants, modalities, or specific variables. Returns matching data as structured JSON."""
    try:
        gold_path = engine.gold_dir / "gold_multimodal_cohort.csv"
        result = await asyncio.to_thread(
            _query_gold_tier, gold_path,
            participants=params.participants,
            modalities=params.modalities,
            variables=params.variables,
            exclude_nonstandard=params.exclude_nonstandard,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.exception(f"Error querying gold tier: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
async def list_modalities() -> str:
    """List all modalities and their variables available in the gold tier."""
    try:
        gold_path = engine.gold_dir / "gold_multimodal_cohort.csv"
        result = await asyncio.to_thread(get_available_modalities, gold_path)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- NEW: Processing Status ---

@mcp.tool()
async def get_pipeline_status() -> str:
    """Get comprehensive processing status: what's been discovered, processed, pending, and skipped across all subjects and modalities."""
    try:
        result = await asyncio.to_thread(
            _get_processing_status,
            engine.bronze_dir, engine.silver_dir, engine.gold_dir
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error getting pipeline status: {e}")
        return json.dumps({"error": str(e)})

# --- NEW: BIDS Validation ---

@mcp.tool()
async def validate_bids(params: ValidateBIDSInput) -> str:
    """Validate a subject's data for BIDS compliance. Checks filename conventions, required metadata fields, recommended fields, and companion file presence."""
    try:
        # Find the subject directory in bronze
        subject_dir = None
        for d in engine.bronze_dir.rglob(params.subject_id):
            if d.is_dir():
                subject_dir = d.parent if d.name == params.subject_id else d
                break
        
        # Also check for BIDS-style directory structure (sub-XXX/)
        bids_dir = engine.bronze_dir / "eeg" / params.subject_id
        if bids_dir.exists():
            subject_dir = bids_dir
        
        if not subject_dir or not subject_dir.exists():
            # Fall back: scan all files matching this subject
            all_files = list(engine.bronze_dir.rglob(f"{params.subject_id}*"))
            if all_files:
                subject_dir = all_files[0].parent
            else:
                return json.dumps({"error": f"Subject {params.subject_id} not found in bronze tier"})
        
        report = await asyncio.to_thread(validate_bids_subject, subject_dir, params.subject_id)
        return json.dumps(report.to_dict(), indent=2)
    except Exception as e:
        logger.exception(f"Error validating BIDS: {e}")
        return json.dumps({"error": str(e)})

# --- NEW: Modality Quality Reports ---

@mcp.tool()
async def export_modality_report(params: ModalityReportInput) -> str:
    """Generate per-modality data quality reports. Includes completeness metrics, distributions, outlier detection, and quality scores."""
    try:
        result = await asyncio.to_thread(
            _generate_modality_report,
            engine.silver_dir,
            modality_filter=params.modality,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.exception(f"Error generating modality report: {e}")
        return json.dumps({"error": str(e)})

# --- Resources ---

@mcp.resource("clinical-registry://master")
def get_registry_master() -> str:
    """Returns the contents of the master clinical registry CSV."""
    return (PROJECT_ROOT / "clinical_registry_master.csv").read_text()

@mcp.resource("clinical-registry://db")
def get_registry_db_info() -> str:
    """Returns information about the compiled registry database."""
    db_path = PROJECT_ROOT / "data" / "registry" / "stratum_registry.db"
    if db_path.exists():
        size = db_path.stat().st_size
        return f"SQLite Registry DB: {db_path}\nSize: {size} bytes\nStatus: Compiled and Active"
    return "SQLite Registry DB: Not found. Run compile_registry.py."

@mcp.resource("data://gold-cohort-summary")
def get_gold_summary() -> str:
    """Returns a summary of the gold tier cohort if it exists."""
    path = PROJECT_ROOT / "data" / "gold" / "gold_multimodal_cohort.csv"
    if path.exists():
        df = pd.read_csv(path, nrows=10)
        return f"Gold Tier Summary (First 10 rows):\n{df.to_string()}"
    return "Gold tier not yet generated."

if __name__ == "__main__":
    mcp.run()



