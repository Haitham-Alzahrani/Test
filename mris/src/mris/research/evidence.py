"""Evidence extraction and aggregation.

``extract_signals`` reads one text (a review, an audience comment, a search snippet) and
returns every lexicon hit with the sentence it came from.  ``EvidenceSummary`` aggregates the
signals of all sources of a candidate, weighting each by source reliability and counting
*distinct domains* so that one site repeated five times is not treated as consensus.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from mris.research.lexicon import (
    CLAUSE_BREAK,
    COMPILED,
    COMPILED_FLAGS,
    COMPILED_THEMES,
    MINUTE_PATTERNS,
    NEGATORS,
    minutes_value,
)
from mris.text import split_sentences, truncate


@dataclass
class Signal:
    field: str
    polarity: int
    phrase: str
    sentence: str
    flag: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "polarity": self.polarity,
            "phrase": self.phrase,
            "sentence": self.sentence,
            "flag": self.flag,
        }


def _negated(sentence: str, start: int) -> bool:
    prefix = sentence[:start]
    breaks = list(CLAUSE_BREAK.finditer(prefix))
    if breaks:
        prefix = prefix[breaks[-1].end() :]
    words = prefix.lower().split()[-3:]
    if words and words[-1] == "no":
        return True
    return any(NEGATORS.match(w.strip(".!?\"'")) for w in words)


def extract_signals(text: str) -> list[Signal]:
    signals: list[Signal] = []
    for sentence in split_sentences(text):
        if len(sentence) > 900:  # junk block (menus, lists); not a sentence about the film
            continue
        excerpt = truncate(sentence, 300)
        for fld, patterns in COMPILED.items():
            for pattern, polarity in patterns:
                for m in pattern.finditer(sentence):
                    pol = -polarity if _negated(sentence, m.start()) else polarity
                    signals.append(Signal(fld, pol, m.group(0).lower(), excerpt))
        for pattern, flag in COMPILED_FLAGS:
            for m in pattern.finditer(sentence):
                if not _negated(sentence, m.start()):
                    signals.append(Signal("flag", -1, m.group(0).lower(), excerpt, flag=flag))
        for pattern in MINUTE_PATTERNS:
            for m in pattern.finditer(sentence):
                value = minutes_value(m.group(1))
                if value is not None and not _negated(sentence, m.start()):
                    signals.append(Signal("opening_minutes", 0, str(value), excerpt))
    return _dedupe(signals)


def _dedupe(signals: list[Signal]) -> list[Signal]:
    seen: set[tuple[str, int, str, str, str | None]] = set()
    out = []
    for s in signals:
        key = (s.field, s.polarity, s.phrase, s.sentence, s.flag)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def detect_themes(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for theme, pattern in COMPILED_THEMES.items():
        n = len(pattern.findall(text or ""))
        if n:
            counts[theme] = n
    return counts


@dataclass
class FieldEvidence:
    pos: float = 0.0
    neg: float = 0.0
    pos_domains: set[str] = field(default_factory=set)
    neg_domains: set[str] = field(default_factory=set)
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.pos + self.neg

    @property
    def domains(self) -> set[str]:
        return self.pos_domains | self.neg_domains

    def score(self, prior_strength: float = 1.0) -> float | None:
        """Bayesian-smoothed share of positive evidence, ``None`` when there is no evidence."""
        if self.total <= 0:
            return None
        return (self.pos + 0.5 * prior_strength) / (self.total + prior_strength)


@dataclass
class SourceInput:
    """One source's analysed text as fed to the summary."""

    url: str
    domain: str
    source_type: str
    reliability: float
    signals: list[Signal]


@dataclass
class EvidenceSummary:
    fields: dict[str, FieldEvidence] = field(default_factory=lambda: defaultdict(FieldEvidence))
    flags: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # flag -> domains
    flag_weight: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    opening_minutes: list[tuple[float, str]] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)
    professional_domains: set[str] = field(default_factory=set)
    audience_domains: set[str] = field(default_factory=set)

    @classmethod
    def from_sources(cls, sources: list[SourceInput]) -> EvidenceSummary:
        summary = cls()
        for src in sources:
            # Per source, a phrase counts once per field/polarity: repetition on one page is not consensus.
            counted: set[tuple[str, int]] = set()
            for sig in src.signals:
                if sig.field == "opening_minutes":
                    summary.opening_minutes.append((float(sig.phrase), src.domain))
                    summary._mark_domain(src)
                    continue
                if sig.field == "flag":
                    summary.flags[sig.flag].add(src.domain)
                    summary.flag_weight[sig.flag] += src.reliability
                    summary._mark_domain(src)
                    continue
                fe = summary.fields[sig.field]
                key = (sig.field, sig.polarity)
                weight = src.reliability if key not in counted else src.reliability * 0.25
                counted.add(key)
                if sig.polarity > 0:
                    fe.pos += weight
                    fe.pos_domains.add(src.domain)
                else:
                    fe.neg += weight
                    fe.neg_domains.add(src.domain)
                if len(fe.examples) < 6 and not any(
                    e["quote"] == sig.sentence and e["domain"] == src.domain for e in fe.examples
                ):
                    fe.examples.append(
                        {
                            "domain": src.domain,
                            "url": src.url,
                            "polarity": sig.polarity,
                            "quote": sig.sentence,
                        }
                    )
                summary._mark_domain(src)
        return summary

    def _mark_domain(self, src: SourceInput) -> None:
        self.domains.add(src.domain)
        if src.source_type == "professional":
            self.professional_domains.add(src.domain)
        elif src.source_type == "audience":
            self.audience_domains.add(src.domain)

    def get(self, name: str) -> FieldEvidence:
        return self.fields[name] if name in self.fields else FieldEvidence()

    def score(self, name: str) -> float | None:
        return self.get(name).score()

    def flag_domains(self, flag: str) -> set[str]:
        return self.flags.get(flag, set())

    @property
    def median_opening_minutes(self) -> float | None:
        if not self.opening_minutes:
            return None
        return statistics.median(v for v, _ in self.opening_minutes)
