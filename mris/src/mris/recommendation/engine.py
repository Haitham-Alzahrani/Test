"""Pick what to show: only PASSED (HIGH-confidence, above-threshold) candidates that are not
blocked and were never recommended before. Every shown recommendation is stored."""

from __future__ import annotations

from dataclasses import dataclass

from mris.models import CandidateMovie, Confidence, RecommendationHistory, ResearchStatus, RuleType, User
from mris.recommendation.blocklist import already_recommended, block_reason
from mris.recommendation.formatter import format_recommendation
from mris.repositories import Repos


@dataclass
class Recommendation:
    candidate: CandidateMovie
    history: RecommendationHistory
    text: str


class RecommendationEngine:
    def __init__(self, repos: Repos, user: User) -> None:
        self.repos = repos
        self.user = user

    def eligible(self) -> list[CandidateMovie]:
        enabled = {
            k for k, v in self.repos.preferences.values(self.user, RuleType.EXCLUSION).items() if v > 0
        }
        out = []
        for cand in self.repos.candidates.by_status(ResearchStatus.PASSED.value):
            if cand.confidence != Confidence.HIGH.value:
                continue
            if already_recommended(self.repos, self.user, cand.movie):
                continue
            reason = block_reason(self.repos, self.user, cand.movie, enabled)
            if reason:
                cand.research_status = ResearchStatus.BLOCKED.value
                cand.decision_reason = f"blocked at display time: {reason}"
                continue
            out.append(cand)
        return sorted(out, key=lambda c: c.total_score or 0, reverse=True)

    def present(self, cand: CandidateMovie, lang: str = "ar", show_score: bool = False) -> Recommendation:
        sources = len(self.repos.candidates.sources(cand))
        text = format_recommendation(cand, lang=lang, show_score=show_score, source_count=sources)
        reason = ", ".join(cand.strengths or []) or (cand.decision_reason or "")
        history = self.repos.recommendations.add(self.user, cand, reason)
        return Recommendation(cand, history, text)

    def recommend(self, count: int = 1, lang: str = "ar", show_score: bool = False) -> list[Recommendation]:
        return [self.present(c, lang, show_score) for c in self.eligible()[:count]]
