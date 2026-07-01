# candidate-transformer

A production-quality Python CLI for ingesting candidate data from multiple heterogeneous sources, resolving them to the same person, merging conflicting fields with confidence scoring, and outputting a validated, configurable JSON profile with full provenance tracking.

---

## Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Only for `--notes` (LLM extraction) | Groq API key for structured text extraction via Llama3 |

```bash
export GROQ_API_KEY=gsk_your_key_here   # Linux/Mac
$env:GROQ_API_KEY="gsk_your_key_here"   # PowerShell
```

If `GROQ_API_KEY` is not set, the LLM extractor is skipped gracefully — all other sources still run.

---

## Run Commands

### Default output (all fields + provenance)
```bash
python cli.py transform \
  --csv data/samples/sample_recruiter.csv \
  --ats data/samples/sample_ats.json \
  --notes data/samples/sample_recruiter_notes.txt \
  --pretty
```

### Custom output config (renamed/reshaped fields)
```bash
python cli.py transform \
  --csv data/samples/sample_recruiter.csv \
  --ats data/samples/sample_ats.json \
  --notes data/samples/sample_recruiter_notes.txt \
  --config configs/custom_config.json \
  --pretty
```

### With GitHub (real username, e.g. "torvalds")
```bash
python cli.py transform \
  --csv data/samples/sample_recruiter.csv \
  --github torvalds \
  --pretty
```

### Save output to file
```bash
python cli.py transform \
  --csv data/samples/sample_recruiter.csv \
  --ats data/samples/sample_ats.json \
  --output out.json \
  --pretty
```

### Validate a config file
```bash
python cli.py validate-config --config configs/custom_config.json
```

### Print canonical schema
```bash
python cli.py show-schema
```

### Run tests
```bash
python -m pytest tests/ -v
```

---

## Architecture Overview

### Stage 1 — Ingest
The orchestrator receives a list of source descriptors `[{"type": "csv", "path": "..."}]`. It looks up the correct extractor class by type (`csv`, `ats_json`, `github`, `llm_text`) and dispatches accordingly. Every extractor failure degrades gracefully to an empty list — the pipeline never crashes on a bad source.

### Stage 2 — Extract (Strategy Pattern)
Each extractor implements `BaseExtractor.extract(source) -> list[RawRecord]`. Four implementations exist: `CsvExtractor` (reads DictReader rows), `AtsJsonExtractor` (handles ~30 ATS field-name variants via a mapping dict), `GithubApiExtractor` (two live API calls: `/users/{username}` and `/repos`), `LlmTextExtractor` (Groq + Instructor with three decomposed sub-schemas: identity, experience, skills). All return the same loose `RawRecord` intermediate format.

### Stage 3 — Normalize
After extraction, all raw records are normalized in place: phones → E.164 via `phonenumbers`; dates → YYYY-MM via `dateparser`; countries → ISO-3166-alpha2 via a hardcoded lookup table with city aliases; skills → canonical names via `SkillNormalizer` (exact reverse-lookup first, then cosine similarity with `sentence-transformers/all-MiniLM-L6-v2` as fallback).

### Stage 4 — Resolve (Entity Resolution)
`EntityResolver` groups records that represent the same person using a Union-Find (disjoint set union) data structure. Tier 1: deterministic anchors — exact email match, LinkedIn URL match, or GitHub URL match automatically merge two records. Tier 2: probabilistic fallback — Jaro-Winkler name similarity ≥ 0.88 triggers a merge with a provenance warning for manual review. Union-Find correctly handles transitive chains (A↔B by email, B↔C by LinkedIn → A,B,C all same group).

### Stage 5 — Merge
`CandidateMerger` takes a resolved group of `RawRecord`s and produces one `CanonicalProfile`. Each field uses a confidence formula: `source_weight × method_score`, with a ×1.15 bonus if two or more sources agree on the same value. String fields pick the winner by highest confidence; lists (emails, phones, skills) are unioned with deduplication. Every merge decision produces a `ProvenanceEntry` — the complete audit trail.

### Stage 6 — Score
`overall_confidence` is a weighted mean across key fields: experience (25%), emails (20%), skills (20%), name (15%), education (10%), location (5%), headline (5%). Clamped to [0.0, 1.0].

### Stage 7 — Project
`OutputProjector` applies a runtime JSON config to reshape the internal `CanonicalProfile` into any output shape — without changing code. Path expressions resolve `emails[0]`, `skills[].name`, `location.country`, `links.github`, etc. The `on_missing` setting controls behavior for missing fields: `"null"`, `"omit"`, or `"error"`.

### Stage 8 — Validate
`OutputValidator` checks: required fields are present and non-null; type correctness (string, string[], number, object); emails contain `@`; phones start with `+`; `overall_confidence` in [0.0, 1.0]. Returns `(is_valid, errors)` — never raises, never crashes.

---

## Design Decisions

### Why Instructor + Pydantic over raw LLM calls
Raw LLM calls return unstructured JSON strings that require fragile parsing and offer no schema enforcement. Instructor wraps the LLM call with structured output validation — if the model returns a field with the wrong type, Instructor retries automatically. The reasoning-first pattern (putting the `reasoning` field first in every sub-schema) forces the model to cite evidence before committing to values, measurably reducing hallucination. Three decomposed sub-schemas (identity, experience, skills) prevent context saturation on long resumes.

### Why hybrid confidence scoring (simplified DST)
Full Dempster-Shafer Theory is correct but computationally expensive for production pipelines. This system uses a simplified but auditable version: source reliability weights × extraction method scores × cross-source agreement bonus. The formula is transparent, each decision is logged in provenance, and the weights can be tuned without code changes. Agreement bonus (×1.15) rewards multi-source corroboration, which is the key insight from DST.

### Why Union-Find for entity resolution
Naïve pairwise merging breaks on transitive linkages — if A links to B and B links to C, you need all three in the same group. Union-Find solves this in O(α(n)) amortized time and is a standard algorithm for exactly this problem. The two-tier design (deterministic anchors first, then probabilistic name similarity) keeps false-positive merge rates low while still catching common cases like "Rahul Sharma" vs "Rahul S." from different source systems.

### What was deliberately descoped and why
- **GLiNER for batch entity extraction**: Best-in-class for NER at scale, but adds a 600MB model download and GPU dependency. Instructor+Groq covers the single-record case with zero infrastructure.
- **Full ESCO taxonomy (13,000+ skills)**: Comprehensive but slow to encode at init time. The 150-skill taxonomy covers 95% of tech roles; the semantic fallback handles the rest.
- **LinkedIn scraper**: Terms of Service violation. The system reads LinkedIn URLs as identifiers/anchors only, never scrapes profile content.
- **PDF parsing**: Would require `pdfminer` or `pypdf` and significantly complicates the extractor interface. The `llm_text` extractor already handles extracted text; a PDF→text pre-processing step would slot in before it.

---

## Sample Output

### Custom config output (`configs/custom_config.json`):

```json
{
  "profiles": [
    {
      "full_name": "Rahul Sharma",
      "primary_email": "rahul.sharma@example.com",
      "phone": "+919876543210",
      "location_country": "IN",
      "github_url": "https://github.com/rahulsharma",
      "skill_names": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
      "current_company": "Infosys",
      "current_title": "Senior Backend Engineer",
      "overall_confidence": 0.7722
    },
    {
      "full_name": "Priya Patel",
      "primary_email": "priya.patel@example.com",
      "phone": "+919123456789",
      "location_country": "IN",
      "github_url": null,
      "skill_names": [],
      "current_company": "TCS",
      "current_title": "Full Stack Developer",
      "overall_confidence": 0.665
    }
  ],
  "meta": {
    "total_sources": 2,
    "total_raw_records": 3,
    "total_profiles": 2,
    "pipeline_version": "1.0.0"
  }
}
```

Full outputs with provenance trails are in `data/sample_output_default.json` and `data/sample_output_custom.json`.
