"""
Explainability service for AutiBloom predictions.

Generates parent-friendly explanations from the Feature 3 payload,
combining rule-based domain analysis with real SHAP values when available.
"""

from wellbeing.models import WellbeingQuestion


# ── Static domain mapping (fallback if DB unavailable) ──────────
# Mirrors the standard AutiBloom question→domain assignment.
DEFAULT_DOMAIN_MAP = {
    'a1': 'communication',
    'a2': 'communication',
    'a3': 'emotional_responses',
    'a4': 'routines',
    'a5': 'routines',
    'a6': 'sensory_behaviors',
    'a7': 'communication',
    'a8': 'emotional_responses',
    'a9': 'sensory_behaviors',
    'a10': 'routines',
}

DOMAIN_LABELS = {
    'communication': 'Communication',
    'routines': 'Routines',
    'emotional_responses': 'Emotional Responses',
    'sensory_behaviors': 'Sensory Behaviors',
}


def _get_domain_map():
    """
    Build a1..a10 → domain mapping from the database.
    Falls back to DEFAULT_DOMAIN_MAP if questions aren't loaded yet.
    """
    try:
        qs = WellbeingQuestion.objects.filter(is_active=True)
        if qs.exists():
            return {q.code.lower(): q.domain for q in qs}
    except Exception:
        pass
    return dict(DEFAULT_DOMAIN_MAP)


def build_explanation(payload: dict, shap_values: dict = None) -> dict:
    """
    Build an explanation dict from a validated prediction payload.

    Args:
        payload:     dict with keys age_years, sex, jaundice, family_asd, a1..a10.
        shap_values: optional dict {feature_name: float} from ml.inference.
                     When provided, top_shap_features is populated and the
                     chart in entry_report.html will render real importances.

    Returns:
        JSON-serializable dict with:
        - risk_flags:        list of a# keys where binary_flag == 1
        - risk_count:        len(risk_flags)
        - domain_breakdown:  {domain: [a# list]} for ALL domains
        - top_domains:       domains with the highest risk flag count
        - friendly_summary:  supportive parent-facing narrative
        - shap_values:       raw {feature: float} dict (empty if no real model)
        - top_shap_features: list of {feature, value} sorted by |value| desc
    """
    domain_map = _get_domain_map()

    # ── Identify risk flags ─────────────────────────────────────
    answer_keys = [f'a{i}' for i in range(1, 11)]
    risk_flags = [k for k in answer_keys if payload.get(k) == 1]

    # ── Domain breakdown ────────────────────────────────────────
    domain_breakdown = {
        'communication': [],
        'routines': [],
        'emotional_responses': [],
        'sensory_behaviors': [],
    }

    for key in answer_keys:
        domain = domain_map.get(key, 'communication')
        domain_breakdown.setdefault(domain, []).append(key)

    # Risk flags per domain
    domain_risk_counts = {}
    for domain in domain_breakdown:
        flagged = [k for k in domain_breakdown[domain] if k in risk_flags]
        domain_risk_counts[domain] = len(flagged)

    # ── Top domains ─────────────────────────────────────────────
    max_count = max(domain_risk_counts.values()) if domain_risk_counts else 0
    top_domains = []
    if max_count > 0:
        top_domains = [d for d, c in domain_risk_counts.items() if c == max_count]

    # ── Friendly summary ────────────────────────────────────────
    friendly_summary = _build_friendly_summary(
        risk_flags, top_domains, domain_risk_counts, payload
    )

    # ── SHAP feature importances ─────────────────────────────────
    clean_shap = shap_values or {}
    top_shap_features = []
    if clean_shap:
        top_shap_features = sorted(
            [{'feature': k, 'value': round(v, 4)} for k, v in clean_shap.items()],
            key=lambda x: abs(x['value']),
            reverse=True
        )[:7]  # top 7 for chart

    return {
        'risk_flags':        risk_flags,
        'risk_count':        len(risk_flags),
        'domain_breakdown':  domain_breakdown,
        'top_domains':       top_domains,
        'friendly_summary':  friendly_summary,
        'shap_values':       clean_shap,
        'top_shap_features': top_shap_features,
    }


def _build_friendly_summary(risk_flags, top_domains, domain_risk_counts, payload):
    """Generate a warm, supportive summary for caregivers."""
    risk_count = len(risk_flags)

    if risk_count == 0:
        return (
            "Great news! No areas of concern were flagged this week. "
            "Your child's responses suggest they are doing well across all domains. "
            "Keep up the wonderful care you're providing! 🌟"
        )

    # Build domain mention string
    domain_names = [DOMAIN_LABELS.get(d, d) for d in top_domains]
    if len(domain_names) == 1:
        domain_str = domain_names[0].lower()
    elif len(domain_names) == 2:
        domain_str = f"{domain_names[0].lower()} and {domain_names[1].lower()}"
    else:
        domain_str = ", ".join(d.lower() for d in domain_names[:-1]) + f", and {domain_names[-1].lower()}"

    if risk_count <= 3:
        intensity = "a few"
        tone = (
            f"This week, {domain_str} showed some areas worth keeping an eye on. "
            f"Only {risk_count} item{'s were' if risk_count > 1 else ' was'} flagged — "
            "this is quite common and not a cause for alarm. "
            "Small, consistent support in these areas can make a big difference. 💛"
        )
    elif risk_count <= 6:
        intensity = "several"
        tone = (
            f"This week, {domain_str} showed the most challenges, "
            f"with {risk_count} items flagged overall. "
            "Remember, these patterns help identify where your child may benefit "
            "from extra support. Every child develops at their own pace, "
            "and noticing these patterns is a positive step. 🌱"
        )
    else:
        intensity = "multiple"
        tone = (
            f"This week's check-in flagged {risk_count} items, "
            f"mainly in {domain_str}. "
            "While this may feel concerning, tracking these patterns over time "
            "gives you and your support team valuable insight. "
            "Consider sharing this report with your child's support team "
            "to discuss next steps together. You're doing a great job by staying engaged. 💪"
        )

    return tone
