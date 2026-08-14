"""AI-powered job matching.

Two-stage pipeline (retrieve, then re-rank):

    raw query
      -> parser.parse_query          natural language -> structured Intent
      -> engine.rank_jobs            deterministic scoring over every open job
      -> llm.rerank                  OPTIONAL - LLM re-ranks the top N
      -> ranked results

Stage 2 is additive only: without an API key, or on any failure, the stage 1
result is returned unchanged.
"""

from app.matching import llm
from app.matching.engine import ScoredJob, rank_jobs
from app.matching.parser import Intent, enrich_with_profile, parse_query

__all__ = ["Intent", "ScoredJob", "enrich_with_profile", "llm", "parse_query", "rank_jobs"]
