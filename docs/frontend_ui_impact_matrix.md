# Frontend UI Impact Matrix

This matrix maps SRS sections to concrete frontend routes/pages/components so UI impact is explicit for each product area.

## UI Impact Matrix: SRS sections to frontend pages/components

| Mapping ID | SRS section | Product scope | Routes/pages | Key components/modules | Evidence artifact | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FEUI-001 | §2.1 | Persona workflow progression and step-by-step route sequencing. | `/projects/new`, `/projects/:project_id/mode`, `/projects/:project_id/characters`, `/projects/:project_id/pipeline-setup`, `/projects/:project_id/run-monitor`, `/projects/:project_id/export`, `/projects/:project_id/dashboards` | `MainShell`, `mainRouter`, `project-route.ts` | `frontend/tests/e2e/workflow-happy-path.e2e.spec.ts` | implemented |
| FEUI-002 | §3 | System mode selection and mode snapshot visibility. | `/projects/:project_id/mode` | `ProjectModePage`, `workflow-hooks.ts` | `frontend/tests/unit/mode-catalog-schema.unit.test.ts` | implemented |
| FEUI-003 | §4.1, §4.2 | Ingestion source flow for TXT/directory/Markdown/EPUB and project bootstrap. | `/projects/new`, `/projects/:project_id/pipeline-setup` | `ProjectNewPage`, `ProjectPipelineSetupPage`, `workflow-hooks.ts` | `frontend/tests/integration/project-new-directory-ingestion.integration.test.tsx` | partial |
| FEUI-004 | §4.3, §4.4, §4.5 | Character map operations and adjacent pronunciation/gender/voice setup surfaces. | `/projects/:project_id/characters`, `/projects/:project_id/pipeline-setup` | `ProjectCharactersPage`, `ProjectPipelineSetupPage`, `workflow-hooks.ts` | `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts` | partial |
| FEUI-005 | §4.6, §4.7 | Tagging/speaker/emotion review workflow and low-confidence guidance. | `/projects/:project_id/review/speakers`, `/projects/:project_id/review/emotions`, `/projects/:project_id/review/low-confidence`, `/projects/:project_id/guide/low-confidence-review` | `ProjectSpeakerReviewPage`, `ProjectEmotionReviewPage`, `ProjectLowConfidenceReviewPage`, `ProjectLowConfidenceReviewGuidePage` | `frontend/tests/regression/pipeline-mode-lock.regression.test.tsx` | partial |
| FEUI-006 | §4.9, §4.10, §4.11 | Run monitoring and multi-mode export consumption surfaces. | `/projects/:project_id/run-monitor`, `/projects/:project_id/export` | `ProjectRunMonitorPage`, `ProjectExportPage`, `workflow-hooks.ts` | `frontend/tests/e2e/backend-endpoint-contract.e2e.spec.ts` | implemented |
| FEUI-007 | §4.12, §4.13 | LLM/provider/deterministic controls and contract-driven run payload fields. | `/projects/:project_id/pipeline-setup` | `ProjectPipelineSetupPage`, `workflow-hooks.ts`, `api.ts` | `frontend/tests/unit/run-request-schema.unit.test.ts` | implemented |
| FEUI-008 | §5 | Dashboard visualizations and snapshot/export interactions. | `/projects/:project_id/dashboards` | `ProjectDashboardsPage` | `frontend/tests/integration/project-dashboards-page.integration.test.tsx` | implemented |
