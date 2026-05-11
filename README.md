# STRATUM: Agent-driven orchestration of multimodal clinical data

The STRATUM architecture is a multi-modal clinical data processing pipeline that helps address constraints inherent in large cohort research and data collection.

## Architecture Overview
...
The STRATUM architecture is built on a high-performance orchestration layer that connects clinical researchers with deep-learning-ready data objects.

### 1. AI Interaction Layer
Researchers interact with the pipeline using the **Model Context Protocol (MCP)**. This allows for natural language data discovery and automated tool execution.

### 2. STRATUM Core Engine
The `StratumEngine` manages the transition of data across the three tiers, coordinating with modality-specific plugins for Neuroimaging, Multi-Omics, and Wearables (currently available).

### 3. Medallion Data Tiers
*   **Bronze (Source)**: Immutable, de-identified raw clinical inputs.
*   **Silver (Harmonized)**: Domain-specific metrics mathematically validated against the `clinical_registry_master`.
*   **Gold (Analytics)**: High-dimensional, longitudinal dataset containing all processed data.


## Data Types and General Information
...
STRATUM is an object oriented pipeline (`StratumEngine`) with the following architecture:

*   **Bronze Tier (Raw Ingestion)**: NIfTI, DICOM, fastq-derived CSVs, REDCap exports, raw wearable JSONs
*   **Silver Tier (Harmonization)**: Zero-trust schema mapping via isolated plugins. Domain-specific metrics are validated against the `clinical_registry_master`, uniformity across sites.
*   **Gold Tier (Structure)**: Data is aligned along Subject (`participant_id`) and Time (`visit_session`) axes.

---

## Supported Modalities & Pipelines

The architecture handles data processing through high-efficiency batching, allowing simultaneous evaluation of data structures.

*   **Neuroimaging (MRI, fMRI, DTI)**: Natively processes 4D NIfTI tensors and DICOM bundles (via `dcm2niix`). Utilizing `nibabel` and `nilearn`, the engine automatically extracts BOLD (Blood-Oxygen-Level-Dependent) time-series metadata and computes functional amplitude variances natively.
*   **Electrophysiology (EEG/MEG)**: Processes BIDS-native arrays and strictly converts raw EDF/BDF formats into BIDS-compliant sidecars and channel matrices via wrappers (`pyedflib`/`mne`).
*   **Clinical EHR (FHIR)**: Dynamically parses HL7 FHIR R4 Bundles to securely extract Patient demographics, LOINC-coded diagnostics, ICD-10/SNOMED ontological identifiers, and RxNorm/NDC pharmacokinetic records.
*   **Multi-Omics (Genomic / Proteomic)**: Standardizes Variant Call Formats (e.g., resolving `rsid` and zygosity) and maps proteomic abundances (UniProt) securely into the cohort timeline.
*   **Clinical NLP**: Translates subjective, unstructured physician free-text into computable numerical features, extracting ontological identifiers.
*   **Digital Biomarkers**: Deconstructs high-frequency time-series arrays representing wearable actigraphy (e.g., Continuous Heart Rate) to extract clinically significant scalar representations such as sleep efficiency.
*   **Biological Specimens & Psychometrics**: Standardizes Laboratory Information Systems (LIMS) assays and clinical survey instruments into standardized statistical bounds.



## Privacy
...
Clinical environments operate under certain compliance constraints (HIPAA, GDPR, EU AI Act). To ensure zero-trust data handling, STRATUM enforces two policies:

**1. PII De-identification Pipeline (HIPAA Safe Harbor)**:
Prior to Gold Tier tensor generation, STRATUM routes all tabular data through a rigorous PII de-identifier. This automatically drops explicit identifiers (Names, MRNs, Phone Numbers, etc.), caps extreme outliers (ages > 89 are bounded at 90), and truncates all birth dates strictly to the `YYYY` scalar.

**2. Cryptographic Provenance**:
During the generation of the Gold Tier data object, STRATUM uses W3C-PROV Compliant Routines to append unique SHA-256 hashes to  row-wise entries. This enforces granular tracking, ensuring every tensor utilized directly connects to raw data. Any variable undetected within the schema registry is isolated and prefixed with `nonstandard_`, helping prevent unapproved PHI leakage.
---

## MCP Protocol

### Connecting to an LLM
The STRATUM Orchestrator is built using **FastMCP**. For the most reliable experience and automatic dependency management, it is recommended to run the server using **`uv`**.

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Run the Server**:
    You can run the server directly or configure it in your AI client (like Claude Desktop or Cursor).
    ```bash
    uv run --with fastmcp python stratum_server.py
    ```

3.  **Configuring Claude Desktop**:
    Add the following to your `claude_desktop_config.json`:
    ```json
    {
      "mcpServers": {
        "stratum": {
          "command": "uv",
          "args": [
            "run",
            "--with",
            "fastmcp",
            "python",
            "/absolute/path/to/stratum_server.py"
          ]
        }
      }
    }
    ```

### LLM Interaction
Once attached, the LLM will automatically index STRATUM's 20 multi-modal tools, including:

**Management & Orchestration:**
*   `ingest_new_subject`: Discovers files across the bronze tier, classifies them by modality signatures, routes them to isolated plugins, and generates the silver tier representation.
*   `generate_gold_tier`: Triggers the final multi-modal longitudinal merge and executes strict PII de-identification rules.
*   `validate_bids`: Executes a compliance validation against the strict BIDS standard (filename conventions, missing JSON sidecars, recommended scalar fields).

**Data Interrogation & Metrics:**
*   `query_gold`: Interrogates the longitudinal Gold matrix filtering by targeted participant IDs, functional modalities, or precise variable names.
*   `export_modality_report`: Generates data quality metrics for specific modalities.
*   `get_pipeline_status`: See what data has been discovered, processed, queued, or discarded.

**Core Processing (Manual Overrides):**
*   `process_imaging` / `process_omics` / `process_wearables` / `process_eeg`: Orchestrate zero-trust processing of specific isolated modalities.

---

## Processing Data

STRATUM is completely agent-driven. Once your raw clinical files are placed in the appropriate `data/bronze/` subdirectories, simply ask your LLM to ingest the data:

1. **Boot Server**: Make sure the MCP server is attached to LLM (using `uv run --with fastmcp python stratum_server.py`).
2. **Discover and Ingest**: Ask LLM to run the `ingest_new_subject` tool. STRATUM will automatically scan the Bronze tier, detect the modalities, convert any DICOM/EDF files, and harmonize everything into the Silver tier.
3. **Generate the Matrix**: Ask your LLM to run `generate_gold_tier` to execute the PII de-identification pipeline and compile the final longitudinal cohort matrix for analysis.

