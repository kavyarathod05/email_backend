"""Preference matching package."""

from intel.modules.matching.ranker import RankResult, load_profile, rank_jobs, score_job

__all__ = ["RankResult", "load_profile", "rank_jobs", "score_job"]
