# Audiobook Creator UI-to-API Mapping

Reference sources:
- [SRS.md](/Users/elhamdev/work/nipe/SRS.md) sections `### 2.1 Personas` and `### 2.2 Primary Use Cases`
- [SRS_Expanded_Implementation_Checklist.md](/Users/elhamdev/work/nipe/SRS_Expanded_Implementation_Checklist.md) item `USE-002`

Purpose:
- Map the Audiobook Creator flow to concrete UI actions and backend API endpoints.
- Provide implementation-facing traceability for UC-1 style execution.

## USE-002 Audiobook Flow Mapping

### Step 01: Create Project
- ui_screen: Project setup/upload
- user_action: Enter project title and create a new audiobook processing project.
- api_endpoint: POST /api/projects
- expected_outcome: Project is created and returns a stable project ID.

### Step 02: Upload Novel TXT
- ui_screen: Project setup/upload
- user_action: Upload Shadow Slave (or another novel) TXT source file for ingestion.
- api_endpoint: POST /api/projects/{project_id}/ingest/txt
- expected_outcome: Ingestion and chapterization metadata are persisted for the project.

### Step 03: Import Character Map
- ui_screen: Character map upload
- user_action: Upload JSON/CSV character map with required name/verbalized/gender fields.
- api_endpoint: POST /api/projects/{project_id}/characters/import
- expected_outcome: Character entries are validated and stored for downstream tagging/voice mapping.

### Step 04: Configure Voices
- ui_screen: Run pipeline
- user_action: Set narrator and gender-default voice IDs before processing.
- api_endpoint: PUT /api/projects/{project_id}/voices
- expected_outcome: Voice configuration is saved and available to resolver logic.

### Step 05: Start Audiobook Pipeline Run
- ui_screen: Run pipeline
- user_action: Set run options and start processing for TTS-ready output generation.
- api_endpoint: POST /api/projects/{project_id}/runs
- expected_outcome: A run record is created and returns run ID for status tracking.

### Step 06: Monitor Run Status
- ui_screen: Export/logs
- user_action: Poll run status until processing is completed or failed.
- api_endpoint: GET /api/projects/{project_id}/runs/{run_id}
- expected_outcome: UI receives deterministic run status and progress metadata.

### Step 07: Download TTS-Ready Export
- ui_screen: Export/logs
- user_action: Download the final structured audiobook export file.
- api_endpoint: GET /api/projects/{project_id}/exports/{run_id}.json
- expected_outcome: User obtains TTS-ready structured JSON export.
