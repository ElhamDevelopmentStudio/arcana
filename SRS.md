# SOFTWARE REQUIREMENTS SPECIFICATION (SRS)

# Narrative Intelligence & Performance Engine (NIPE)

**Version:** 1.0 (MVP)  
**Primary MVP Target:** Shadow Slave (later: any novel)  
**Core Differentiator:** Audiobook/TTS-ready normalization + tagging + character/voice mapping with confidence & review loops  
**Document Type:** SRS (“WHAT” the system must do; not implementation algorithms)

----------

## 0. Glossary

-   **Novel**: A long-form narrative text (web novel, book, serialized fiction).
    
-   **Corpus**: Full text of a novel (all chapters).
    
-   **Chapter Unit**: A single chapter (index + title + content).
    
-   **Segment**: A short, digestible chunk of text intended for analysis and TTS feeding (target: ≤ 255 characters for audiobook mode).
    
-   **Sub-segment**: A smaller unit inside a segment representing a detected shift (emotion shift, narration/dialogue shift, thought shift).
    
-   **Character Map**: User-editable table mapping `name -> verbalized form -> gender`, plus aliases and metadata.
    
-   **Verbalized Form**: Pronunciation-oriented representation for TTS (e.g., “Aegis” → “EE-jis”).
    
-   **Voice Map**: Mapping from character (or gender/default) to TTS voice profile identifiers.
    
-   **Tagging**: Assigning labels and scores to segments/sub-segments (emotion, speaker, type, tension contribution).
    
-   **Confidence**: A numeric score representing reliability of a label (0.0–1.0).
    
-   **Evidence Trace**: Stored pointers to text spans and feature signals that justified a label.
    
-   **Mode**: One of the product workflows (Audiobook / Academic / Author / Other).
    

----------

## 1. Introduction

### 1.1 Purpose

NIPE is a system that ingests long-form narrative text and produces structured, traceable narrative metadata. It supports multiple workflows:

-   **Audiobook creators** using TTS who require:
    
    -   stable segmentation
        
    -   correct names pronunciation
        
    -   character-to-voice mapping
        
    -   speaker/gender tagging
        
    -   emotion/tone tagging with smoothing readiness
        
-   **Academic/research** users who require:
    
    -   reproducible metrics
        
    -   narrative curves and structural features
        
    -   exports for analysis and comparison
        
-   **Authors** who require:
    
    -   narrative health diagnostics
        
    -   pacing issues detection
        
    -   character balance warnings
        

### 1.2 Scope

NIPE SHALL:

-   ingest large novels (3,500+ chapters)
    
-   normalize text and structure
    
-   extract characters and build a character map
    
-   support user review and overrides
    
-   produce segmented text suitable for TTS (audiobook mode)
    
-   generate multi-layer tags (speaker, type, emotion, tension, dominance contribution)
    
-   output structured exports (JSON/CSV/time series)
    
-   provide dashboards/visualizations (where enabled)
    

NIPE SHALL NOT:

-   rewrite or generate new story text
    
-   produce final audio output directly (optional integration later, but not required in v1)
    
-   claim emotional labels are ground-truth
    
-   require manual per-chapter labeling
    

### 1.3 Success Criteria (Product-Level)

-   A user can take Shadow Slave input and obtain:
    
    -   a clean chapterized corpus
        
    -   a validated character map (name → verbalized → gender)
        
    -   a segmented, phonetic-normalized, tagged export suitable to feed into a TTS pipeline
        
    -   basic tension/emotion/dominance time-series and charts
        
-   The system is deterministic enough to reproduce results with pinned configuration.
    

----------

## 2. User Personas & Use Cases

### 2.1 Personas

1.  **Audiobook Creator (TTS)**
    
    -   wants speaker assignment, correct pronunciation, emotion tags, voice mapping
        
2.  **Academic Researcher**
    
    -   wants reproducible exports, narrative curves, network graphs, comparisons
        
3.  **Fiction Author**
    
    -   wants pacing diagnostics, monotony detection, character imbalance alerts
        
4.  **Community Reader**
    
    -   wants interactive dashboards and exploration of arcs/characters
        

### 2.2 Primary Use Cases

-   UC-1: Upload Shadow Slave → choose Audiobook Mode → generate TTS-ready export
    
-   UC-2: Upload any novel → choose Academic Mode → export metrics and graphs
    
-   UC-3: Upload draft novel → choose Author Mode → get health report
    

----------

## 3. System Modes & Mode Selection

### FR-MODE-1 Mode Prompt

After successful ingestion, the system SHALL prompt the user to select a mode:

-   Audiobook (TTS)
    
-   Academic / Research
    
-   Author / Writing Improvement
    
-   Custom / Other (future)
    

### FR-MODE-2 Mode Configuration Profiles

Each mode SHALL load a default configuration profile:

-   segmentation targets
    
-   tagging depth
    
-   required outputs
    
-   review steps
    

### FR-MODE-3 Mode Switching

The user SHALL be able to switch modes without re-uploading text, as long as the corpus is already ingested.

----------

## 4. Functional Requirements

### 4.1 Ingestion & Project Setup

#### FR-ING-1 Project Creation

The system SHALL create a project per novel ingestion containing:

-   project id
    
-   novel title (user-provided or detected)
    
-   ingestion timestamp
    
-   selected mode(s)
    
-   configuration snapshot
    

#### FR-ING-2 Input Formats

The system SHALL support ingestion from:

-   single TXT file
    
-   directory of chapter files
    
-   Markdown file(s)
    
-   EPUB (MVP optional; v1.1 required if prioritized)
    

#### FR-ING-3 Encoding Handling

The system SHALL:

-   detect encoding issues
    
-   convert to UTF-8 internally
    
-   record any conversion warnings in logs
    

#### FR-ING-4 Incremental Input

The system SHALL support incremental addition of chapters:

-   append new chapters
    
-   detect if chapters overlap or duplicate existing chapters
    
-   re-run only affected downstream steps (delta processing)
    

----------

### 4.2 Deep Normalization

Normalization is a mandatory step for all modes.

#### FR-NORM-1 Chapter Boundary Detection

The system SHALL divide the corpus into chapters using:

-   file boundaries (if chapter files)
    
-   header patterns (if single file)
    
-   fallback heuristics (if ambiguous)
    

#### FR-NORM-2 Chapter Title Deduplication

The system SHALL detect and resolve duplicated chapter titles by:

-   assigning unique internal identifiers
    
-   preserving original titles
    
-   recording deduplication actions in logs
    

#### FR-NORM-3 Text Cleanup

The system SHALL normalize:

-   whitespace
    
-   Unicode variants
    
-   curly quotes → consistent quotes
    
-   ellipsis normalization
    
-   line breaks normalization
    
-   removal of obvious copy artifacts (e.g., repeated separators)
    

#### FR-NORM-4 Dialogue Formatting Normalization

The system SHALL normalize dialogue formatting including:

-   smart quotes vs straight quotes
    
-   em-dash dialogue style (if present)
    
-   mismatched quote repair (best-effort) with warnings if uncertain
    

#### FR-NORM-5 Offset & Traceability Preservation

The system SHALL preserve traceability by storing:

-   original text
    
-   normalized text
    
-   mapping between original offsets and normalized offsets (at least at chapter + segment level)
    
-   evidence pointers to original text spans
    

#### FR-NORM-6 Normalization Report

The system SHALL output a report including:

-   chapters detected count
    
-   suspected duplicates
    
-   quote repair count
    
-   encoding issues
    
-   any potentially lossy transformations
    

----------

### 4.3 Character & Entity Extraction

#### FR-CHAR-1 Character Map Creation

The system SHALL maintain a **Character Map** with at minimum:

-   `name` (canonical)
    
-   `verbalized_form` (TTS-friendly)
    
-   `gender` (manual or inferred)
    
-   `aliases[]`
    
-   `notes` (optional)
    
-   `source` (user provided / inferred / scraped)
    
-   `confidence` fields where applicable
    

#### FR-CHAR-2 Character List Input Methods

The system SHALL support multiple ways to create/populate the character list:

1.  **User Upload**
    
    -   structured file (CSV/JSON)
        
2.  **Manual Entry UI**
    
    -   add/edit rows
        
3.  **Auto Extraction from Text**
    
    -   propose candidate names/entities
        
4.  **Optional Web Scrape**
    
    -   user-triggered, with warnings about potential inaccuracies
        
5.  **Hybrid Merge**
    
    -   combine sources and deduplicate
        

#### FR-CHAR-3 Review & Approval Workflow

When auto-extraction or scraping is used, the system SHALL provide:

-   “proposed characters” list
    
-   merge suggestions (aliases → canonical)
    
-   user approval / rejection
    
-   a “finalize character map” action
    

#### FR-CHAR-4 Alias Handling

The system SHALL allow:

-   multiple aliases per character
    
-   alias → canonical mapping
    
-   conflict detection when one alias maps to multiple canonicals
    

#### FR-CHAR-5 Character Occurrence Tracking

The system SHALL compute and store:

-   mention counts per chapter
    
-   first appearance chapter
    
-   last appearance chapter
    
-   mentions per 1,000 words (normalized)
    
-   (optional) dialogue line counts when attribution exists
    

----------

### 4.4 Gender Tagging and Ambiguity Handling

You requested dual verification. This is explicitly required.

#### FR-GEN-1 Gender Column in Character Map

The character map SHALL include a gender column. Minimum structure:

-   `name -> verbalized_form -> gender`
    

Accepted gender values:

-   male
    
-   female
    
-   neutral
    
-   unknown
    
-   custom (user-defined label)
    

#### FR-GEN-2 Manual Gender Override

If the user sets gender in the map, the system SHALL treat it as authoritative.

#### FR-GEN-3 Automatic Gender Inference

The system SHALL optionally infer gender for characters using textual signals and produce:

-   inferred gender value
    
-   confidence score
    
-   evidence trace (where found)
    

#### FR-GEN-4 Double-Check Mechanism

If manual gender exists AND inferred gender exists:

-   system SHALL compare them
    
-   system SHALL flag contradictions
    
-   system SHALL request user review before final export if contradiction severity exceeds a threshold
    

#### FR-GEN-5 Unknown/Neutral Fallback Behavior

If gender remains unknown/neutral:

-   system SHALL allow assignment of a default voice category (neutral/unknown)
    
-   system SHALL not block export
    
-   export SHALL include gender as unknown and confidence as low/undefined
    

#### FR-GEN-6 Update Propagation

When gender is edited in the map:

-   system SHALL update dependent outputs (voice resolution previews, export metadata)
    
-   previously generated exports SHALL be marked “outdated” unless regenerated
    

----------

### 4.5 Pronunciation and Verbalization

#### FR-VERB-1 Verbalized Form Field

Each character MUST have:

-   canonical name
    
-   verbalized form suitable for TTS
    

#### FR-VERB-2 Pronunciation Overrides

The system SHALL support a user-editable dictionary:

-   term → verbalized form
    
-   scope: global (whole novel) and per-character
    

#### FR-VERB-3 Preview & Validation

The system SHALL provide a way to validate pronunciations by:

-   showing before/after text substitution previews
    
-   optionally producing a short “pronunciation preview snippet” (text-only output in v1; audio preview integration optional later)
    

#### FR-VERB-4 Safe Substitution Rules

The system SHALL provide controls to avoid wrong replacements:

-   whole-word matching
    
-   case sensitivity options
    
-   alias-aware substitution
    
-   warnings for ambiguous terms
    

#### FR-VERB-5 Non-Character Pronunciation

The system SHALL allow verbalization for:

-   places
    
-   artifacts
    
-   special terminology
    
-   invented words
    

----------

### 4.6 Segmentation for TTS and Analysis

Segmentation exists for all modes, but **Audiobook Mode** has strict constraints.

#### FR-SEG-1 Chapter → Paragraph → Sentence segmentation

The system SHALL segment the corpus into:

-   chapters
    
-   paragraphs
    
-   sentences
    
-   dialogue blocks (when detectable)
    
-   narration blocks
    

#### FR-SEG-2 Audiobook Segment Length Target

In Audiobook Mode, system SHALL produce segments:

-   preferably ≤ 255 characters
    
-   configurable target length
    
-   segments MUST remain intelligible (not random splits)
    

#### FR-SEG-3 Segment Boundary Constraints

Segments SHALL respect:

-   dialogue quote boundaries (avoid splitting inside a quoted utterance unless required by length constraints)
    
-   punctuation boundaries preference
    
-   avoid splitting inside abbreviations and initials where possible
    

#### FR-SEG-4 Segment Metadata

Each segment SHALL store:

-   chapter id
    
-   segment index
    
-   original text span pointer
    
-   normalized text
    
-   phonetic-ready text (after substitutions)
    
-   parent paragraph/sentence references
    

#### FR-SEG-5 Segment Reconstitution

The system SHALL support reconstructing:

-   full chapter text from segments
    
-   full corpus from chapters  
    …for auditing and reproducibility.
    

----------

### 4.7 Tagging System

Tagging is the core that feeds analytics AND audiobook exports.

#### FR-TAG-1 Tagging Layers

The system SHALL generate multi-layer tags, at minimum:

1.  **Structural Type**
    
    -   narration / dialogue / internal thought / mixed / description / action
        
2.  **Speaker Attribution**
    
    -   speaker id + confidence (for dialogue)
        
3.  **Emotion**
    
    -   valence, intensity, primary/secondary label, confidence
        
4.  **Shift Markers**
    
    -   detect changes inside segments and mark sub-boundaries
        
5.  **Tension Contribution**
    
    -   per-segment and aggregated metrics
        
6.  **Dominance Contribution**
    
    -   who is active or referenced
        

#### FR-TAG-2 Intra-Segment Change Detection

The system SHALL detect and represent changes within a segment, including:

-   emotion shift (sadness → euphoria)
    
-   narration ↔ internal thought shift
    
-   internal ↔ external speech shift
    
-   tone reversal / dark irony markers (when detected)
    

#### FR-TAG-3 Sub-Segment Representation

When a change is detected:

-   system SHALL create a sub-segment boundary marker
    
-   each sub-segment SHALL have its own tags
    
-   parent segment SHALL include a summary tag (e.g., dominant tone)
    

#### FR-TAG-4 Confidence & Evidence for Tags

For every tag produced, the system SHALL store:

-   confidence score
    
-   evidence trace pointing to text spans or signals used
    
-   “unknown/uncertain” state when confidence is low
    

#### FR-TAG-5 User Review of Tags

The system SHALL provide optional review workflows:

-   review speakers
    
-   review emotional tags at peaks/troughs
    
-   review flagged low-confidence regions
    

(Review is optional; the system must still function without manual review.)

----------

### 4.8 Voice Mapping for Audiobook Mode

#### FR-VOICE-1 Voice Map Definition

The system SHALL maintain a Voice Map that supports:

-   per-character voice assignment
    
-   default narrator voice
    
-   default male/female/neutral/unknown voices
    
-   per-character overrides
    

#### FR-VOICE-2 Voice Resolution Output

For each dialogue segment, export SHALL include:

-   resolved voice id
    
-   speaker id
    
-   gender used for resolution
    
-   confidence levels (speaker + gender)
    

#### FR-VOICE-3 Internal Thought Voice Policy

The system SHALL support configurable policy for internal thoughts:

-   use character voice (softened)
    
-   use narrator voice
    
-   use separate “thought voice”  
    (Policy selection required in audiobook mode setup.)
    

----------

### 4.9 Audiobook Mode Outputs

This is the MVP core.

#### FR-AUD-1 TTS-Ready Export Package

The system SHALL output an export package containing:

-   ordered segments for the entire novel
    
-   per-segment phonetic-ready text
    
-   per-segment voice resolution
    
-   per-segment tags (type, emotion, speaker, confidence)
    
-   project configuration snapshot
    
-   logs/reports
    

#### FR-AUD-2 Export Formats

The system SHALL support:

-   JSON (primary)
    
-   CSV (secondary)
    
-   time-series arrays for charts
    

#### FR-AUD-3 Export Integrity

Exports SHALL:

-   preserve ordering (chapter → segment)
    
-   be resumable (support continuation from a given chapter/segment index)
    
-   store stable IDs for segments so downstream pipelines can reference them
    

#### FR-AUD-4 Emotion Smoothing Metadata

Even if smoothing is applied later (in TTS pipeline), NIPE SHALL output metadata that enables smoothing, such as:

-   adjacent segment emotional deltas
    
-   scene state
    
-   volatility markers
    
-   “avoid abrupt change” flags
    

(NIPE may optionally provide pre-smoothed recommended tags, but must preserve raw tags as well.)

----------

### 4.10 Academic Mode Outputs

#### FR-ACAD-1 Emotional Polarity Curves

System SHALL output:

-   chapter-level valence mean
    
-   chapter-level valence variance
    
-   volatility index
    
-   rolling window curves
    

#### FR-ACAD-2 Tension Modeling Outputs

System SHALL output:

-   raw tension per chapter
    
-   smoothed tension curve
    
-   peak markers (major/minor)
    
-   plateau regions
    

#### FR-ACAD-3 Character Dominance Outputs

System SHALL output:

-   chapter-level dominance per key characters
    
-   character co-occurrence network graph
    
-   centrality metrics table
    

#### FR-ACAD-4 Export Formats

Academic exports SHALL support:

-   JSON
    
-   CSV
    
-   graph format (nodes/edges JSON)
    
-   reproducible run snapshot
    

#### FR-ACAD-5 Comparative Analysis

System SHALL support comparing multiple novels in a workspace:

-   aligned curve comparisons
    
-   normalized pacing signature comparisons
    
-   export of comparative datasets
    

----------

### 4.11 Author Mode Outputs

#### FR-AUTH-1 Narrative Health Report

System SHALL produce a report including:

-   tension flatline detection
    
-   emotional monotony detection
    
-   over-dominant character warnings
    
-   disappearing character warnings
    
-   dialogue density anomalies
    

#### FR-AUTH-2 Actionable Flags

Author mode SHALL generate “flags” with:

-   where it occurs (chapter range)
    
-   what metric triggered it
    
-   severity score
    
-   evidence trace
    

#### FR-AUTH-3 Chapter Type Classification

System SHALL classify chapters into:

-   Setup, Build-up, Confrontation, Resolution, Transitional  
    and provide:
    
-   confidence
    
-   reasons/features used
    

----------

### 4.12 LLM Routing & Quota Management System (NEW)

This section defines how NIPE SHALL interact with external AI/LLM providers when semantic interpretation beyond rule-based logic is required.

----------

##### 4.12.1 Purpose

NIPE SHALL implement an optional LLM integration layer to assist with:

-   ambiguous character extraction
    
-   ambiguous speaker attribution
    
-   complex emotional classification refinement
    
-   edge-case structural interpretation
    
-   scene classification when confidence is below threshold
    

LLM usage SHALL be:

-   optional
    
-   minimized
    
-   quota-aware
    
-   provider-agnostic
    
-   failover-capable
    
-   compliant with provider usage policies
    

----------

##### 4.12.2 Supported Providers

The system SHALL support integration with:

-   SiliconFlow
    
-   Groq
    
-   OpenRouter
    

The system SHALL treat all providers as interchangeable via abstraction.

----------

##### 4.12.3 Usage Minimization Policy

The system SHALL:

-   Attempt rule-based processing first.
    
-   Escalate to LLM only when:
    
    -   confidence score < configurable threshold
        
    -   ambiguity flags raised
        
    -   user explicitly enables “deep semantic refinement”
        
-   Avoid unnecessary repeated LLM calls for identical inputs.
    

----------

##### 4.12.4 Quota Awareness

The system SHALL track per provider key:

-   request count
    
-   estimated token usage
    
-   last known rate-limit status
    
-   last successful call timestamp
    
-   last reset timestamp (if known)
    

The system SHALL:

-   Stop sending requests when provider signals rate-limit or quota exhaustion.
    
-   Automatically mark provider as temporarily unavailable.
    
-   Resume usage only after reset window detected or manually re-enabled.
    

The system SHALL NOT:

-   Attempt to bypass rate limiting mechanisms.
    
-   Attempt to circumvent provider safeguards.
    
-   Automate behavior intended to violate provider terms.
    

----------

##### 4.12.5 Multi-Key Configuration

The system SHALL allow:

-   Multiple API keys per provider.
    
-   Separate configuration of provider priority order.
    
-   Manual enabling/disabling of providers.
    

When one provider becomes unavailable:

-   System SHALL failover to next available provider.
    

----------

#### 4.12.6 Caching

All LLM responses SHALL be cached based on:

-   hashed input text
    
-   task type
    
-   configuration snapshot
    
-   model identifier
    

If identical request occurs:

-   cached result SHALL be returned
    
-   no provider call SHALL be executed
    

----------

#### 4.12.7 Deterministic Mode

When deterministic mode enabled:

-   identical input + identical configuration + identical model version  
    → SHALL produce identical outputs (subject to provider determinism).
    

System SHALL log:

-   provider used
    
-   model identifier
    
-   timestamp
    
-   token usage
    

----------

### 4.13 Provider Abstraction Layer (WHAT-Level Architecture) (NEW)

This section defines the required abstraction between NIPE core logic and external AI providers.

----------

#### 4.13.1 LLM Router Module

The system SHALL implement an internal module named:

**LLMRouter**

Responsibilities:

-   Accept standardized request object.
    
-   Select provider based on:
    
    -   availability
        
    -   quota status
        
    -   priority configuration
        
-   Dispatch request.
    
-   Handle response.
    
-   Handle failure.
    
-   Handle retry and failover.
    
-   Log usage metrics.
    
-   Return standardized response object.
    

----------

#### 4.13.2 Standardized Request Object

The system SHALL define a provider-agnostic request format containing:

-   request_id
    
-   project_id
    
-   task_type (emotion_refinement, speaker_resolution, etc.)
    
-   input_text
    
-   max_tokens (if applicable)
    
-   expected_schema
    
-   configuration_snapshot_id
    

----------

#### 4.13.3 Standardized Response Object

The system SHALL return:

-   provider_used
    
-   model_identifier
    
-   raw_output
    
-   parsed_output
    
-   confidence (if derivable)
    
-   token_usage_estimate
    
-   success_flag
    
-   error_code (if failure)
    
-   timestamp
    

----------

#### 4.13.4 Provider Failover Behavior

If provider returns:

-   rate-limit error
    
-   quota exceeded
    
-   timeout
    
-   service unavailable
    

System SHALL:

1.  Log event
    
2.  Mark provider temporarily unavailable
    
3.  Attempt next provider
    
4.  Continue workflow if alternate succeeds
    
5.  Surface warning in logs if all providers unavailable
    

----------

#### 4.13.5 Isolation From Core Logic

Core tagging, segmentation, and modeling modules SHALL:

-   Never directly call provider SDKs.
    
-   Only communicate via LLMRouter.
    
-   Remain independent of provider-specific syntax.
    

This ensures:

-   Clean separation of concerns
    
-   Easy future migration to paid tiers or local models
    
-   Provider replacement without rewriting tagging logic
    

----------

#### 4.13.6 Future Extensibility

Provider abstraction SHALL allow:

-   Adding local self-hosted models
    
-   Adding paid-tier providers
    
-   User-supplied API keys
    
-   Per-project provider configuration



## 5. Visualization Requirements

(Enabled in dashboard experiences; exports must exist regardless.)

### VR-1 Tension Graph

-   chapter axis
    
-   raw + smoothed overlay
    
-   peak markers
    
-   zoom + tooltip
    
-   click → show evidence segments contributing to peak
    

### VR-2 Emotional Polarity Graph

-   valence bands
    
-   rolling mean
    
-   volatility overlay
    
-   top-N extreme chapters list
    

### VR-3 Character Dashboard

-   prominence timeline
    
-   filters by character
    
-   network graph (pan/zoom)
    
-   centrality sortable table
    

### VR-4 Audiobook Prep Dashboard

-   character map editor (name → verbalized → gender)
    
-   voice map editor
    
-   pronunciation dictionary editor
    
-   export preview for a chapter/segment range
    
-   warnings panel (low confidence speaker/gender/emotion)
    

----------

## 6. Data Persistence Requirements

### DR-1 Storage of Raw & Normalized Text

System SHALL store:

-   raw corpus
    
-   normalized corpus
    
-   chapterized representation
    

### DR-2 Storage of Derived Artifacts

System SHALL store:

-   character map versions
    
-   pronunciation dictionary versions
    
-   voice map versions
    
-   tagging outputs
    
-   time-series metrics
    

### DR-3 Versioning & Reproducibility

Each run SHALL store:

-   configuration snapshot
    
-   model versions used (where applicable)
    
-   deterministic seed settings (if enabled)
    
-   timestamped run id
    
-   changelog entries when user edits maps
    

### DR-4 Traceability

Any metric/tag SHALL be traceable to:

-   chapter
    
-   segment/sub-segment
    
-   original text offsets
    
-   evidence trace metadata
    

----------

## 7. Non-Functional Requirements

### NFR-1 Performance

-   Must process 3,500+ chapters
    
-   Must support chunked processing
    
-   Must support incremental updates
    

### NFR-2 Reliability

-   Must not corrupt ordering
    
-   Must not lose chapter content
    
-   Must fail gracefully with recoverable state
    

### NFR-3 Usability

-   Must allow user overrides for:
    
    -   pronunciation
        
    -   gender
        
    -   character merging
        
    -   voice mapping
        

### NFR-4 Transparency

-   Must never claim perfect accuracy
    
-   Must expose confidence scores and allow filtering low-confidence outputs
    

### NFR-5 Security & Privacy (SaaS)

-   user projects isolated
    
-   access control per project
    
-   secure storage of uploaded text
    

### NFR-6 Compliance & Copyright Guardrails

-   system SHALL support user-uploaded text flow as the default
    
-   if web scrape is used, system SHALL warn about potential inaccuracies and legal constraints
    
-   system SHALL provide “do not store source text” mode (store only derived metrics) as an option


### NFR-7 LLM Reliability

-   System SHALL degrade gracefully if all LLM providers unavailable.
    
-   System SHALL allow continuation with rule-based results only.
    
-   System SHALL clearly flag segments refined by LLM vs rule-only.
    

----------

### NFR-8 API Key Security

-   API keys SHALL be stored securely server-side.
    
-   Keys SHALL never be exposed client-side.
    
-   Access SHALL be restricted per project/user.
    
-   Keys SHALL support rotation.
    

----------

## 8. Error Handling & Warnings

### ER-1 Ingestion Errors

-   unsupported format
    
-   encoding failures
    
-   missing chapters
    

### ER-2 Normalization Warnings

-   ambiguous chapter boundaries
    
-   quote mismatch repairs uncertain
    
-   suspected duplicate content
    

### ER-3 Character System Warnings

-   ambiguous alias collisions
    
-   low-confidence extracted characters
    
-   duplicate canonical candidates
    

### ER-4 Gender Warnings

-   contradiction between manual and inferred gender
    
-   too little evidence for inference
    

### ER-5 Tagging Warnings

-   low-confidence speaker attribution
    
-   high ambiguity dialogue blocks
    
-   unstable emotion predictions in rapid shifts
    

----------

## 9. Configuration Requirements

System SHALL expose configuration for:

-   segmentation target length (audiobook)
    
-   emotion taxonomy selection (basic vs expanded)
    
-   confidence thresholds for warnings
    
-   whether to enable web scraping
    
-   whether to require review for contradictions
    
-   internal thought handling policy
    
-   export formats and chunk sizes
    
-   deterministic mode toggles
    

----------

## 10. MVP Definition

### MVP Includes (Must-Have)

-   Ingestion (TXT + chapter directory)
    
-   Deep normalization (chapters, dedupe, quote normalization, reports)
    
-   Character map:
    
    -   name → verbalized → gender
        
    -   aliases
        
    -   review UI
        
-   Dual gender system:
    
    -   manual column + optional inference + contradiction flags
        
-   Pronunciation overrides + preview
    
-   Segmentation for TTS (≤255 chars target)
    
-   Tagging (at least structural + emotion + speaker basic + confidence)
    
-   Voice mapping (character + gender defaults + narrator)
    
-   Audiobook export (JSON + CSV)
    
-   Basic dashboards (tension + polarity + character prominence)
    
-   Incremental update (append chapters)
    

### MVP Excludes (Nice-to-Have)

-   full motif recurrence modeling
    
-   advanced comparative clustering
    
-   community sentiment overlay
    
-   automatic web scraping by default
    

----------

## 11. Acceptance Criteria

A build is considered acceptable when:

1.  A Shadow Slave corpus can be ingested and chapterized correctly.
    
2.  Character map can be created/edited with fields:
    
    -   name, verbalized form, gender
        
3.  Pronunciation substitutions appear in preview and export correctly.
    
4.  Export produces ordered segments with:
    
    -   phonetic-ready text
        
    -   speaker/gender/voice tags (where applicable)
        
    -   emotion tags + confidence
        
5.  Contradictory gender results are flagged for review.
    
6.  Outputs are reproducible when configuration and inputs are unchanged.
    
7.  Incremental addition of chapters updates outputs without reprocessing everything.
