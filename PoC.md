
# SOFTWARE REQUIREMENTS SPECIFICATION (PoC)

# Narrative Intelligence & Performance Engine (NIPE)

**Version:** 0.1 (Proof of Concept)  
**Goal:** Validate Audiobook Preprocessing Pipeline in 2–3 days  
**Scope:** Minimal vertical slice of Audiobook Mode

----------

# 1. Objective of PoC

The PoC SHALL demonstrate that:

-   A raw novel text can be ingested
    
-   Characters can be mapped (name → verbalized → gender)
    
-   Text can be segmented into TTS-friendly chunks
    
-   Basic tagging can be applied
    
-   Voice resolution works
    
-   A structured JSON export can be generated
    
-   LLM router abstraction works at least for one task
    

The PoC SHALL NOT attempt to implement full analytics, dashboards, or complete modeling layers.

----------

# 2. Scope of PoC

## INCLUDED

-   Single TXT ingestion
    
-   Basic normalization
    
-   Manual character map
    
-   Pronunciation substitution
    
-   Simple segmentation (≤255 chars)
    
-   Basic dialogue detection
    
-   Basic emotion tagging (simple valence only)
    
-   Simple speaker assignment (rule-based)
    
-   Voice mapping (male/female/narrator)
    
-   JSON export
    
-   Minimal LLM router stub
    
-   Quota tracking stub
    

## EXCLUDED

-   Web scraping
    
-   Full alias merging UI
    
-   Academic mode
    
-   Author mode
    
-   Advanced tension modeling
    
-   Sub-segment pivot detection
    
-   Network graph
    
-   Dashboard UI
    
-   Incremental updates
    

----------

# 3. Functional Requirements (PoC)

----------

## 3.1 Ingestion

### FR-PING-1 Single File Input

The system SHALL accept:

-   One TXT file
    

### FR-PING-2 Basic Chapter Detection

The system SHALL:

-   Detect chapters using simple header pattern (e.g., “Chapter X”)
    
-   If no pattern found, treat entire file as one chapter
    

----------

## 3.2 Basic Normalization

### FR-PNORM-1 Whitespace Normalization

-   Normalize line breaks
    
-   Remove repeated blank lines
    

### FR-PNORM-2 Quote Normalization

-   Convert curly quotes to straight quotes
    
-   Do not attempt complex repair
    

----------

## 3.3 Manual Character Map (No Auto Extraction in PoC)

### FR-PCHAR-1 Character Map Input

User SHALL provide a simple JSON/CSV file:

{  
 "Sunny": { "verbalized": "Sunny", "gender": "male" },  
 "Nephis": { "verbalized": "Ne-fis", "gender": "female" }  
}

### FR-PCHAR-2 Required Fields

Each character MUST have:

-   name
    
-   verbalized_form
    
-   gender
    

No inference required in PoC.

----------

## 3.4 Pronunciation Replacement

### FR-PVERB-1 Simple Replacement

The system SHALL:

-   Replace exact whole-word matches of character names
    
-   Substitute with verbalized_form
    
-   Store both original and phonetic text
    

No advanced alias handling required.

----------

## 3.5 Segmentation (Simplified)

### FR-PSEG-1 Sentence Segmentation

-   Split by punctuation (. ! ?)
    

### FR-PSEG-2 TTS Chunking

-   Combine sentences until:
    
    -   total length approaches 255 characters
        
-   Never exceed 255
    

No micro-segmentation or shift detection.

----------

## 3.6 Basic Tagging

PoC tagging is intentionally minimal.

----------

### FR-PTAG-1 Structural Tag

Each segment SHALL be labeled:

-   dialogue (if contains quotes)
    
-   narration (otherwise)
    

----------

### FR-PTAG-2 Basic Emotion Tag

System SHALL compute:

-   valence score (simple positive/negative heuristic)
    
-   intensity (absolute magnitude)
    
-   no complex emotion categories
    

----------

### FR-PTAG-3 Basic Speaker Assignment

For dialogue segments:

-   Look for pattern: `"..." NAME said`
    
-   If match:
    
    -   speaker = NAME
        
    -   confidence = high
        
-   Else:
    
    -   speaker = unknown
        
    -   confidence = low
        

No complex attribution.

----------

## 3.7 Voice Mapping

### FR-PVOICE-1 Default Voices

System SHALL support:

-   narrator_voice
    
-   male_default_voice
    
-   female_default_voice
    

### FR-PVOICE-2 Resolution Logic

If dialogue:

-   If speaker exists in map:
    
    -   use character voice if defined
        
    -   else use gender default
        
-   If unknown:
    
    -   fallback narrator
        

----------

## 3.8 JSON Export (Core PoC Deliverable)

### FR-PAUD-1 Output Structure

Export SHALL produce:

{  
 "chapter_id": 1,  
 "segment_id": "1-05",  
 "original_text": "...",  
 "phonetic_text": "...",  
 "type": "dialogue",  
 "speaker": "Sunny",  
 "gender": "male",  
 "voice_id": "male_default",  
 "emotion_valence": -0.3,  
 "emotion_intensity": 0.3,  
 "confidence": {  
 "speaker": 0.8,  
 "emotion": 0.6  
 }  
}

----------

# 4. Minimal LLM Router (PoC Version)

PoC SHALL validate architecture only — not full production routing.

----------

## 4.1 Basic LLMRouter Module

-   Accept standardized request
    
-   Call one configured provider
    
-   Log provider name
    
-   Log request count
    
-   Return response
    

No multi-provider failover required in PoC.

----------

## 4.2 Quota Tracking (Basic)

System SHALL:

-   Count requests per provider key
    
-   Stop calling provider if max_calls_per_day reached (configurable)
    
-   Log when limit reached
    

No automatic reset detection required for PoC.

----------

# 5. Non-Functional (PoC)

-   Must process at least 3–5 chapters without crash
    
-   Must produce deterministic export
    
-   Must not exceed free-tier call count during test
    
-   Must log all LLM calls
    

----------

# 6. PoC Acceptance Criteria

PoC is successful if:

1.  Upload 3 Shadow Slave chapters
    
2.  Provide small character map
    
3.  Run pipeline
    
4.  Generate structured JSON export
    
5.  Phonetic replacement visible
    
6.  Dialogue segments identified
    
7.  Speaker resolved in simple tagged lines
    
8.  Voice mapping applied correctly
    
9.  No crash
    
10.  LLM router logs at least one test call
    

----------

# What You’ll Prove in 2–3 Days

-   End-to-end flow works
    
-   Data model is viable
    
-   JSON export format works
    
-   Voice resolution logic works
    
-   Quota-aware routing is structurally sound
    
-   Pipeline concept is not fantasy
    

You will NOT prove:

-   Perfect emotion detection
    
-   Perfect speaker attribution
    
-   Perfect segmentation
    
-   Commercial readiness
