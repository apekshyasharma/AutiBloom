"""
Prediction service helpers.

Provides reusable functions to build and validate the ML payload
from a submitted WeeklyWellbeingEntry, matching the Feature 3 contract.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone


# Exact key set required by the Feature 3 ML contract
EXPECTED_KEYS = frozenset(
    ['age_years', 'sex', 'jaundice', 'family_asd']
    + [f'a{i}' for i in range(1, 11)]
)

VALID_SEX = {'m', 'f'}
VALID_YES_NO = {'yes', 'no'}


def build_payload_from_entry(entry):
    """
    Build the strict Feature 3 payload dict from a submitted entry.

    Returns dict with keys: age_years, sex, jaundice, family_asd, a1..a10

    Raises ValidationError if:
      - entry is not SUBMITTED
      - child profile is missing required demographic fields
      - any of the 10 answer binary flags is missing
    """
    if entry.status != 'SUBMITTED':
        raise ValidationError(
            "Entry must be in SUBMITTED status to build prediction payload.",
            code='not_submitted',
        )

    child = entry.child
    missing_fields = []

    if not child.date_of_birth:
        missing_fields.append('date_of_birth')
    if not child.sex:
        missing_fields.append('sex')
    if not child.jaundice:
        missing_fields.append('jaundice')
    if not child.family_asd:
        missing_fields.append('family_asd')

    if missing_fields:
        raise ValidationError(
            f"Child profile is missing required fields: {', '.join(missing_fields)}",
            code='missing_profile_fields',
            params={'missing_fields': missing_fields},
        )

    # Compute age
    today = timezone.localdate()
    age_years = today.year - child.date_of_birth.year - (
        (today.month, today.day) < (child.date_of_birth.month, child.date_of_birth.day)
    )

    payload = {
        'age_years': age_years,
        'sex': child.sex,
        'jaundice': child.jaundice,
        'family_asd': child.family_asd,
    }

    # Map answers by question code
    answers = entry.answers.select_related('question').all()
    answer_map = {ans.question.code.lower(): ans for ans in answers}
    expected_codes = [f'a{i}' for i in range(1, 11)]
    missing_flags = []

    for code in expected_codes:
        if code not in answer_map:
            missing_flags.append(code)
        else:
            ans = answer_map[code]
            if ans.binary_flag is None:
                missing_flags.append(code)
            else:
                payload[code] = ans.binary_flag

    if missing_flags:
        raise ValidationError(
            f"Missing answer binary flags: {', '.join(missing_flags)}",
            code='missing_binary_flags',
            params={'missing_fields': missing_flags},
        )

    return payload


def validate_payload(payload):
    """
    Validate a prediction payload against the Feature 3 contract.

    Checks:
      - Key set exactly matches contract
      - a1..a10 each in {0, 1}
      - sex in {"m", "f"}
      - jaundice, family_asd in {"yes", "no"}
      - age_years is int in [1, 18]

    Raises ValidationError on failure.
    """
    errors = []

    # Key set check
    payload_keys = set(payload.keys())
    if payload_keys != EXPECTED_KEYS:
        extra = payload_keys - EXPECTED_KEYS
        missing = EXPECTED_KEYS - payload_keys
        parts = []
        if extra:
            parts.append(f"unexpected keys: {extra}")
        if missing:
            parts.append(f"missing keys: {missing}")
        errors.append(f"Payload key mismatch — {'; '.join(parts)}")

    # Validate a1..a10
    for i in range(1, 11):
        key = f'a{i}'
        val = payload.get(key)
        if val is not None and val not in (0, 1):
            errors.append(f"{key} must be 0 or 1, got {val}")

    # Validate sex
    sex = payload.get('sex')
    if sex is not None and sex not in VALID_SEX:
        errors.append(f"sex must be one of {VALID_SEX}, got '{sex}'")

    # Validate jaundice / family_asd
    for field in ('jaundice', 'family_asd'):
        val = payload.get(field)
        if val is not None and val not in VALID_YES_NO:
            errors.append(f"{field} must be one of {VALID_YES_NO}, got '{val}'")

    # Validate age_years
    age = payload.get('age_years')
    if age is not None:
        if not isinstance(age, int) or age < 1 or age > 18:
            errors.append(f"age_years must be int in [1, 18], got {age}")

    if errors:
        raise ValidationError(errors, code='payload_invalid')
