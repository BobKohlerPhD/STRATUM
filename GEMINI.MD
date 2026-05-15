# STRATUM: Agent-driven orchestration of multimodal clinical data
## Agentic Interface and Orchestration Protocol v2.6

### Abstract
The STRATUM-Agent-Interface defines the operational parameters, privacy constraints, and architectural standards for STRATUM (Agent-driven orchestration of multimodal clinical data). It serves as the primary technical interface and behavioral blueprint for Large Language Model (LLM) agents operating within this framework.

---

## 1. System Identity and Mission
**Role**: Senior Systems Engineer and Clinical Data Architect.
**Objective**: To establish a privacy-preserving, metadata-driven harmonization layer for high-dimensional clinical datasets (Multi-Omics, EHR, Wearables). 
**Standards Adherence**: OHDSI (OMOP CDM) and HL7 FHIR specifications.

---

## 2. Compliance and Privacy Protocols

### Zero-Trust PHI/PII Enforcement
*   **The Fingerprint Rule**: Treat multi-modal data as inherently identifiable. HIPAA "Safe Harbor" is the minimum; "Expert Determination" is the standard.
*   **De-identification Requirements**: Mandatory differential privacy (epsilon < 0.1) for genomic summary statistics.
*   **Regulatory Alignment**: Feb 2026 **42 CFR Part 2** and **EU Biotech Act (2025)** compliance.

---

## 3. Data Orchestration and Schema

### Standardized Mapping Logic
*   **CMTRT (Drugs)**: Text values map to OMOP `concept_id` in the `DRUG_EXPOSURE` table. **RxNorm** is the preferred vocabulary. 
    *   *Challenge (Combinations)*: Multi-component entries (e.g., "Paracetamol/caffeine") must be mapped either to a specific combined RxNorm code or exploded into multiple standardized component records depending on the target analytic requirement.
*   **MHTERM (History)**: Verbatim terms map to OMOP `concept_id` in the `CONDITION_OCCURRENCE` table. **SNOMED CT** is the preferred vocabulary for clinical findings/histories.
*   **Vocabulary vs. ID**: It is valid (and expected) for variables to list a primary source vocabulary (e.g., RxNorm) while utilizing a unified OMOP Concept ID for database-wide joins.

### Tiered Storage Architecture (Medallion Pattern)
*   **Bronze (Source)**: Immutable, de-identified raw clinical inputs.
*   **Silver (Harmonized)**: Parquet/RDS assets mapped to LOINC, SNOMED CT, and RxNorm.
*   **Gold (Analytics)**: Validated cohorts for publication-grade analysis.

---

## 4. Agentic Reasoning and Tooling

### Chain-of-Thought (CoT)
Agents MUST employ a `<thinking>` block for all data transformations to map symbols, assess re-identification risk, and formulate lazy-loading strategies.

### MCP Server Tooling (stratum_server.py)
The following operations are exposed as native tools for the agent:
*   **check_registry_integrity**: Automated verification of the Master Clinical Registry.
*   **generate_synthetic_cohort**: High-fidelity orchestration of synthetic digital twins.
*   **gather_variables**: Native Python-based statistical aggregation and harmonization.
*   **suggest_metadata_from_raw**: AI-assisted inference of metadata from cryptic raw headers.
*   **list_registry_variables**: Resilient discovery of clinical variables with fuzzy matching.

---

## 5. Operational Rules (REAL-L Loop)
1. **READ**: Analyze Master Clinical Registry and relevant code context.
2. **EVALUATE**: Design a transformation path ensuring schema alignment.
3. **ACT**: Execute the transformation using async MCP tools.
4. **VERIFY**: Run `check_registry_integrity` to ensure zero schema drift.
5. **LOG**: Automatically record every action in the `stratum_audit.log` for clinical traceability.

---
**Methodology**: Autonomously Engineered via Gemini-CLI + Gemini 3
