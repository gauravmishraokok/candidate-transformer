import logging
from pathlib import Path
from schemas.raw_record import RawRecord
from pipeline.extractors.csv_extractor import CsvExtractor
from pipeline.extractors.ats_json_extractor import AtsJsonExtractor
from pipeline.extractors.github_extractor import GithubApiExtractor
from pipeline.extractors.llm_extractor import LlmTextExtractor
from pipeline.normalizers.phone import normalize_phone
from pipeline.normalizers.date_normalizer import normalize_date
from pipeline.normalizers.country import normalize_country
from pipeline.normalizers.skills import SkillNormalizer
from pipeline.resolver import EntityResolver
from pipeline.merger import CandidateMerger
from pipeline.projector import OutputProjector
from pipeline.validator import OutputValidator

logger = logging.getLogger(__name__)

EXTRACTOR_MAP = {
    "csv": CsvExtractor,
    "ats_json": AtsJsonExtractor,
    "github": GithubApiExtractor,
    "llm_text": LlmTextExtractor,
}


class PipelineOrchestrator:
    def __init__(self, config_path: str = "configs/default_config.json"):
        config_file = Path(config_path)
        import json

        self.config: dict = {}
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    self.config = json.load(f)
                logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config {config_path}: {e}. Using defaults.")
        else:
            logger.warning(f"Config file not found: {config_path}. Using defaults.")

        logger.info("Initializing SkillNormalizer (this may take a moment)...")
        self.skill_normalizer = SkillNormalizer()

        self.resolver = EntityResolver()
        self.merger = CandidateMerger()
        self.projector = OutputProjector(self.config)
        self.validator = OutputValidator()

    def run(self, sources: list[dict]) -> dict:
        extraction_stats: list[dict] = []

        # Stage 1-2: Ingest + Extract
        all_raw_records: list[RawRecord] = []
        for source in sources:
            source_type = source.get("type", "")
            source_path = source.get("path", "")
            ExtractorClass = EXTRACTOR_MAP.get(source_type)

            if not ExtractorClass:
                logger.warning(f"Unknown source type: '{source_type}' — skipping")
                extraction_stats.append({
                    "source": source_path,
                    "type": source_type,
                    "records": 0,
                    "status": "SKIPPED (unknown type)",
                })
                continue

            extractor = ExtractorClass()
            logger.info(f"Extracting from {source_type}: {source_path}")
            records = extractor.extract(source_path)
            all_raw_records.extend(records)
            extraction_stats.append({
                "source": source_path,
                "type": source_type,
                "records": len(records),
                "status": "OK" if records else "EMPTY",
            })
            logger.info(f"Extracted {len(records)} record(s) from {source_path}")

        if not all_raw_records:
            return {
                "error": "No records could be extracted from any source",
                "extraction_stats": extraction_stats,
            }

        # Stage 3: Normalize all raw records in place
        logger.info("Stage 3: Normalizing raw records...")
        for record in all_raw_records:
            # Normalize phones
            normalized_phones = []
            for phone in record.phones:
                norm = normalize_phone(phone)
                if norm:
                    normalized_phones.append(norm)
                else:
                    logger.warning(f"Phone normalization failed: '{phone}' in {record.source_id}")
            record.phones = normalized_phones

            # Normalize skills using SkillNormalizer
            if record.skills_raw:
                canonical_skills = self.skill_normalizer.normalize_batch(record.skills_raw)
                record.skills_raw = canonical_skills

        # Stage 4: Resolve — group by entity
        logger.info("Stage 4: Resolving entities...")
        groups = self.resolver.resolve(all_raw_records)
        logger.info(f"Resolved {len(all_raw_records)} records into {len(groups)} candidate group(s)")

        # Stage 5-6: Merge each group into CanonicalProfile
        logger.info("Stage 5-6: Merging and scoring...")
        profiles = []
        for group in groups:
            profile = self.merger.merge(group)
            profiles.append(profile)
            logger.info(
                f"Merged group of {len(group)} records → "
                f"{profile.candidate_id} (confidence={profile.overall_confidence:.3f})"
            )

        # Stage 7-8: Project + Validate each profile
        logger.info("Stage 7-8: Projecting and validating...")
        results = []
        for profile in profiles:
            try:
                projected = self.projector.project(profile)
                is_valid, errors = self.validator.validate(projected, self.config)
                if not is_valid:
                    projected["_validation_warnings"] = errors
                    logger.warning(
                        f"Profile {profile.candidate_id} has validation warnings: {errors}"
                    )
                results.append(projected)
            except ValueError as e:
                logger.error(f"Projection error for {profile.candidate_id}: {e}")
                results.append({
                    "error": str(e),
                    "candidate_id": profile.candidate_id,
                })

        return {
            "profiles": results,
            "meta": {
                "total_sources": len(sources),
                "total_raw_records": len(all_raw_records),
                "total_profiles": len(profiles),
                "pipeline_version": "1.0.0",
                "extraction_stats": extraction_stats,
            },
        }
