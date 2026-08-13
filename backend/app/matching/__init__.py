"""AI-powered job matching.

Pipeline:  raw query -> parser.parse_query -> Intent -> engine.rank_jobs -> ranked results
"""

from app.matching.engine import ScoredJob, rank_jobs
from app.matching.parser import Intent, enrich_with_profile, parse_query

__all__ = ["Intent", "ScoredJob", "enrich_with_profile", "parse_query", "rank_jobs"]
