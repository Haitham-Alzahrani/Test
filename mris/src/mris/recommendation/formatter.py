"""Concise user-facing output (section 25). Arabic by default, English available.

Only evidence-backed strengths are listed; at most one caveat; no scores unless asked for;
rejected / weak candidates are never mentioned.
"""

from __future__ import annotations

from mris.models import CandidateMovie

STRENGTHS = {
    "ar": {
        "strong_opening": "بداية قوية — الأحداث تبدأ مبكرًا",
        "clear_story": "قصة واضحة ومتماسكة",
        "event_progression": "تسلسل أحداث مستمر ومنطقي",
        "strong_acting": "تمثيل قوي",
        "continuous_events": "إيقاع سريع وأحداث متواصلة",
        "strong_production": "إنتاج قوي وتصوير واضح",
        "strong_tension": "توتر مستمر",
        "standalone": "قصة مستقلة لا تحتاج مشاهدة أفلام سابقة",
    },
    "en": {
        "strong_opening": "Strong opening — events start early",
        "clear_story": "Clear, coherent story",
        "event_progression": "Continuous, logical event progression",
        "strong_acting": "Strong acting",
        "continuous_events": "Fast pacing, continuous events",
        "strong_production": "Strong production, clear camerawork",
        "strong_tension": "Continuous tension",
        "standalone": "Standalone story — no prior films needed",
    },
}

RISKS = {
    "ar": {
        "slow_opening": "بعض المراجعات تشير إلى أن البداية أهدأ قليلًا",
        "slow_burn": "بعض المراجعات تصف إيقاعه بالتصاعد البطيء",
        "excessive_dialogue": "فيه حوار أكثر من المعتاد في بعض المشاهد",
        "chaotic_camera": "بعض المراجعات انتقدت التصوير/المونتاج في مشاهد الأكشن",
        "weak_cast": "طاقم التمثيل أقل شهرة من المعتاد",
        "potential_cast_mismatch": "احتمال ألا يناسبك طاقم التمثيل",
        "generic_high_concept": "بعض المراجعات وصفت القصة بالمتوقَّعة",
        "irrational_plotting": "بعض المراجعات أشارت إلى ثغرات في منطق الأحداث",
        "low_production": "الإنتاج أصغر من أفلامك المرجعية",
        "franchise_dependency": "جزء من سلسلة لكنه يعمل كقصة مستقلة حسب المراجعات",
        "non_english": "اللغة الأساسية ليست الإنجليزية",
        "weak_ratings": "تقييمات الجمهور متوسطة",
        "confusing_story": "بعض المراجعات وجدت القصة معقدة قليلًا",
        "negative_reference_similarity": "فيه تشابه مع فيلم لم يعجبك سابقًا",
    },
    "en": {
        "slow_opening": "Some reviews say the opening is a little calmer",
        "slow_burn": "Some reviews describe a slow build",
        "excessive_dialogue": "More dialogue than usual in places",
        "chaotic_camera": "Some reviews criticise the action camerawork/editing",
        "weak_cast": "Less-known cast",
        "potential_cast_mismatch": "Potential cast mismatch",
        "generic_high_concept": "Some reviews call it predictable",
        "irrational_plotting": "Some reviews mention plot-logic holes",
        "low_production": "Smaller production than your references",
        "franchise_dependency": "Part of a franchise, but reviews say it works standalone",
        "non_english": "Primary language is not English",
        "weak_ratings": "Average audience ratings",
        "confusing_story": "Some reviews found the story a bit complicated",
        "negative_reference_similarity": "Shares traits with a movie you disliked",
    },
}

LABELS = {
    "ar": {
        "why": "لماذا يناسبك:",
        "similar": "قريب من",
        "caveat": "تنبيه",
        "confidence": "الثقة",
        "score": "درجة التوافق",
        "sources": "المصادر",
    },
    "en": {
        "why": "Why it fits:",
        "similar": "Close to",
        "caveat": "Caveat",
        "confidence": "Confidence",
        "score": "Compatibility",
        "sources": "Sources",
    },
}


def format_recommendation(
    cand: CandidateMovie, lang: str = "ar", show_score: bool = False, source_count: int | None = None
) -> str:
    lang = lang if lang in STRENGTHS else "ar"
    movie = cand.movie
    lines = [f"🎬 {movie.label}", "", LABELS[lang]["why"]]
    bullets = [STRENGTHS[lang][s] for s in cand.strengths or [] if s in STRENGTHS[lang]][:5]
    refs = [r["title"] for r in (cand.similar_references or [])][:2]
    if refs:
        bullets.append(f"{LABELS[lang]['similar']}: {'، '.join(refs) if lang == 'ar' else ', '.join(refs)}")
    lines += [f"- {b}" for b in bullets]
    caveat = _top_caveat(cand, lang)
    if caveat:
        lines += ["", f"{LABELS[lang]['caveat']}: {caveat}"]
    if show_score:
        lines += [
            "",
            f"{LABELS[lang]['score']}: {cand.total_score:.0f}/100 · {LABELS[lang]['confidence']}: {cand.confidence}"
            + (f" · {LABELS[lang]['sources']}: {source_count}" if source_count is not None else ""),
        ]
    return "\n".join(lines)


def _top_caveat(cand: CandidateMovie, lang: str) -> str | None:
    penalties = (cand.score_breakdown or {}).get("penalties", {})
    risks = sorted(
        cand.risks or [],
        key=lambda r: (r.get("severity") == "strong", penalties.get(r.get("flag"), 0)),
        reverse=True,
    )
    for risk in risks:
        text = RISKS[lang].get(risk.get("flag"))
        if text:
            return text
    return None


def format_explanation(cand: CandidateMovie, lang: str = "ar") -> str:
    """Detailed internal view - only shown when the user explicitly asks for it."""
    b = cand.score_breakdown or {}
    lines = [
        f"{cand.movie.label} — {cand.research_status} — {cand.total_score} / 100 — {cand.confidence}",
        f"decision: {cand.decision_reason}",
        f"opening: score={cand.opening_score} confidence={cand.opening_confidence} "
        f"event_start≈{cand.opening_event_start_minutes} min",
    ]
    for key, value in (b.get("dimensions") or {}).items():
        lines.append(
            f"  {key:22s} {value if value is not None else '—'}  (+{b.get('contributions', {}).get(key)})"
        )
    for key, value in (b.get("penalties") or {}).items():
        lines.append(f"  penalty {key:14s} -{value}")
    for r in cand.risks or []:
        lines.append(f"  risk {r['flag']} [{r['severity']}]: {r['reason']}")
    for e in (cand.opening_evidence or [])[:4]:
        lines.append(f"  opening evidence ({e.get('domain')}): {e.get('quote')}")
    if b.get("confidence_reasons"):
        lines.append("  confidence notes: " + "; ".join(b["confidence_reasons"]))
    return "\n".join(lines)
