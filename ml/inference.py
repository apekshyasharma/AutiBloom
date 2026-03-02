"""
ml/inference.py
===============
Lazy-loading inference engine for the AutiBloom ASD screening model.

Usage:
    from ml.inference import run_inference, ModelNotReadyError

    try:
        result = run_inference(payload)
        # result = {label, score, shap_values, model_version}
    except ModelNotReadyError:
        # model artefacts not yet deployed — fall back to stub
        pass
"""

import json
import os
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Artefact paths ────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARTEFACTS_DIR    = os.path.join(_BASE_DIR, 'artefacts')
FEATURE_SCHEMA_DIR = os.path.join(_BASE_DIR, 'feature_schema')

MODEL_PATH      = os.path.join(ARTEFACTS_DIR, 'model.pkl')
EXPLAINER_PATH  = os.path.join(ARTEFACTS_DIR, 'shap_explainer.pkl')
SCHEMA_PATH     = os.path.join(FEATURE_SCHEMA_DIR, 'feature_schema.json')

# ── Module-level singletons (lazy-loaded once) ────────────────────────────────
_pipeline   = None
_explainer  = None
_schema     = None


class ModelNotReadyError(Exception):
    """Raised when model artefacts are not present on disk."""
    pass


# ── Loader helpers ────────────────────────────────────────────────────────────

def _load_artefacts():
    """
    Load pipeline, SHAP explainer, and feature schema into module-level
    singletons. Called once on first inference request.

    Raises ModelNotReadyError if any required artefact is missing.
    """
    global _pipeline, _explainer, _schema

    if _pipeline is not None:
        return  # already loaded

    # Check files exist before importing joblib (avoid import error at startup)
    missing = [p for p in (MODEL_PATH, SCHEMA_PATH) if not os.path.exists(p)]
    if missing:
        raise ModelNotReadyError(
            f"Model artefacts not found: {missing}. "
            "Train the model in Colab and drop artefacts into ml/artefacts/."
        )

    try:
        import joblib  # noqa: PLC0415

        logger.info("Loading ML model from %s", MODEL_PATH)
        _pipeline = joblib.load(MODEL_PATH)

        logger.info("Loading feature schema from %s", SCHEMA_PATH)
        with open(SCHEMA_PATH, 'r') as f:
            _schema = json.load(f)

        # SHAP explainer is optional — gracefully skip if missing
        if os.path.exists(EXPLAINER_PATH):
            logger.info("Loading SHAP explainer from %s", EXPLAINER_PATH)
            _explainer = joblib.load(EXPLAINER_PATH)
        else:
            logger.warning(
                "SHAP explainer not found at %s. "
                "SHAP feature importances will not be available.", EXPLAINER_PATH
            )

    except Exception as exc:
        # Reset singletons so the next call retries
        _pipeline = _explainer = _schema = None
        raise ModelNotReadyError(f"Failed to load ML artefacts: {exc}") from exc


# ── Public API ────────────────────────────────────────────────────────────────

def run_inference(payload: dict) -> dict:
    """
    Run end-to-end prediction + SHAP explanation for a single payload.

    Args:
        payload: dict matching the Feature 3 contract:
                 {age_years, sex, jaundice, family_asd, a1..a10}

    Returns:
        {
            'label':         str   – e.g. "Low Probability"
            'score':         float – probability of class 1 (0.0–1.0)
            'shap_values':   dict  – {feature_name: shap_float} or {}
            'model_version': str   – e.g. "rf-v1.0"
        }

    Raises:
        ModelNotReadyError: if artefacts are not on disk.
    """
    _load_artefacts()

    feature_order = _schema['features']           # order Django sends
    label_map     = _schema.get('label_map', {"0": "Low Probability", "1": "High Probability"})
    model_version = _schema.get('version', 'rf-v1.0')

    # ── Build input DataFrame in the correct feature order ─────────────────
    row = {f: payload[f] for f in feature_order}
    df  = pd.DataFrame([row], columns=feature_order)

    # ── Predict ────────────────────────────────────────────────────────────
    proba       = _pipeline.predict_proba(df)[0]   # [p_class0, p_class1]
    label_idx   = int(np.argmax(proba))
    score       = float(proba[1])                  # probability of ASD = 1
    label       = label_map.get(str(label_idx), str(label_idx))

    # ── SHAP values ────────────────────────────────────────────────────────
    shap_values_dict = {}
    if _explainer is not None:
        try:
            shap_values_dict = _compute_shap(df, feature_order)
        except Exception as exc:
            logger.warning("SHAP computation failed (non-fatal): %s", exc)

    return {
        'label':         label,
        'score':         score,
        'shap_values':   shap_values_dict,
        'model_version': model_version,
    }


# ── Internal SHAP helper ──────────────────────────────────────────────────────

def _compute_shap(df: pd.DataFrame, feature_order: list) -> dict:
    """
    Compute per-feature SHAP values for a single row.

    The SHAP explainer was trained on the *transformed* input (after the
    ColumnTransformer), so we must transform the row first.

    The Colab notebook stores 'transformed_feature_order' in the schema,
    which is the column order AFTER ColumnTransformer (categoricals first,
    then numericals). We use that to map SHAP indices → feature names.

    Returns:
        {feature_name: shap_float} — contribution of each feature to
        the positive-class (ASD=1) prediction. Absolute value indicates
        importance; sign indicates direction.
    """
    # Transform the row through the preprocessor step only
    prep         = _pipeline.named_steps['prep']
    X_transformed = prep.transform(df)             # shape (1, n_features)

    # Get SHAP values — handle both shap return shapes:
    #   Old shap: list of arrays, one per class → raw_shap[1] is class-1 values
    #   New shap: 3D array (n_samples, n_features, n_classes) → [:, :, 1]
    raw_shap = _explainer.shap_values(X_transformed)

    if isinstance(raw_shap, list):
        # Old shap API: list[class0_array, class1_array]
        shap_row = np.array(raw_shap[1])[0]        # class-1 values, first row
    else:
        # New shap API: ndarray of shape (n_samples, n_features, n_classes)
        # or (n_samples, n_features) for binary
        arr = np.array(raw_shap)
        if arr.ndim == 3:
            shap_row = arr[0, :, 1]                # class-1, first sample
        else:
            shap_row = arr[0]                      # binary output

    # Map SHAP indices → feature names using transformed_feature_order
    # Falls back to feature_order if key not present in schema
    transformed_order = _schema.get('transformed_feature_order', feature_order)

    shap_dict = {}
    for i, feat_name in enumerate(transformed_order):
        if i < len(shap_row):
            shap_dict[feat_name] = float(shap_row[i])

    return shap_dict


def get_top_shap_features(shap_values: dict, n: int = 5) -> list:
    """
    Return the top-n features sorted by absolute SHAP value (most impactful first).

    Args:
        shap_values: dict from run_inference() output
        n:           how many top features to return

    Returns:
        list of {'feature': str, 'value': float} dicts, sorted by |value| desc
    """
    if not shap_values:
        return []

    sorted_feats = sorted(
        [{'feature': k, 'value': v} for k, v in shap_values.items()],
        key=lambda x: abs(x['value']),
        reverse=True
    )
    return sorted_feats[:n]
