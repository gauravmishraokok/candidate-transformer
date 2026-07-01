# Demo Recording Cheatsheet

## Commands to run in order

```
1. python demo/demo_runner.py
   (full staged demo — main video content, ~6 min)
```

**Fallback if anything breaks mid-demo:**
```bash
python cli.py transform \
  --csv data/samples/sample_recruiter.csv \
  --ats data/samples/sample_ats.json \
  --notes data/samples/sample_recruiter_notes.txt \
  --pretty
```

---

## Files to have open in editor (for b-roll)

| File | What to highlight |
|---|---|
| `pipeline/extractors/llm_extractor.py` | `reasoning` field first in every sub-schema — forces LLM to cite evidence before committing to values |
| `pipeline/resolver.py` | Union-Find class + Jaro-Winkler Tier 2 fallback |
| `pipeline/merger.py` | `_base_confidence()` formula + `_pick_winner()` + agreement bonus |
| `configs/custom_config.json` | Shows how output shape changes with zero code edits |

---

## Key numbers to mention

- **51 tests** passing
- **4 source types**: CSV, ATS JSON, GitHub API, LLM text
- **150+ canonical skills** in taxonomy
- **8 pipeline stages**: Ingest → Extract → Normalize → Resolve → Merge → Score → Project → Validate
- **Confidence formula**: `source_weight × method_score × 1.15 (if 2+ sources agree)`
- **Source weights**: CSV 0.90 · ATS JSON 0.88 · GitHub 0.85 · LLM 0.70

---

## Demo script (what each step shows)

| Step | What it demonstrates |
|---|---|
| 1 | Four raw heterogeneous input formats side by side |
| 2 | Staged pipeline log — all 8 stages named + timed |
| 3 | Field-level conflict: "Rahul Sharma" vs "Rahul S." — CSV wins on confidence |
| 4 | Full merged profile with `overall_confidence: 0.77` |
| 5 | Custom config: `emails[0]` → `primary_email`, `skills[].name` → `skill_names[]` — zero code changes |
| 6 | Provenance table — full audit trail of every field |
| 7 | Graceful degradation — 404 GitHub user → pipeline continues without crashing |
| 8 | Live pytest run — 51/51 green |

---

## Talking points by stage

**Stage 2 — Extract**
> "Each extractor implements the same Strategy Pattern interface. The CSV extractor, ATS extractor, GitHub API extractor, and LLM extractor all return the same `RawRecord` type. If one fails, it returns an empty list — the pipeline never sees an exception."

**Stage 3 — Normalize**
> "Before anything gets merged, every phone becomes E.164, every date becomes YYYY-MM, every country becomes ISO-3166 alpha-2, and every skill maps to a canonical name. The `all-MiniLM-L6-v2` model catches fuzzy matches like 'postgres' → 'PostgreSQL'."

**Stage 4 — Resolve**
> "Entity resolution uses Union-Find. Tier 1: deterministic anchors — email, LinkedIn URL, GitHub URL. Tier 2: Jaro-Winkler name similarity above 0.88. Union-Find handles transitive chains correctly."

**Stage 7 — Project**
> "The `OutputProjector` supports path expressions: `emails[0]`, `skills[].name`, `location.country`. Change the JSON config, get a completely different output shape. Same engine underneath."
