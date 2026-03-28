"""Canonical variable mapping helpers for Multi-NUT targets."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from core.db.ups import db
from core.db.ups.models import DYNAMIC_FIELDS, STATIC_FIELDS
from core.logger import system_logger as logger


CANONICAL_EXTRA_FIELDS = {
    # Internal fallback fields used by existing dashboard logic.
    'ups.realpower.days',
    'ups.realpower.hrs',
}

_token_pattern = re.compile(r'[^a-z0-9]+')


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def dot_to_canonical(dot_key: str) -> str:
    """Convert NUT dot key to canonical underscore key."""
    return str(dot_key or '').strip().replace('.', '_')


def canonical_to_dot(canonical_key: str) -> str:
    """Convert canonical underscore key to NUT dot key."""
    return str(canonical_key or '').strip().replace('_', '.')


def _normalize_name(value: str) -> str:
    lowered = str(value or '').strip().lower()
    lowered = lowered.replace('.', '_')
    lowered = _token_pattern.sub('_', lowered)
    lowered = re.sub(r'_+', '_', lowered)
    return lowered.strip('_')


def _tokenize(value: str) -> List[str]:
    normalized = _normalize_name(value)
    if not normalized:
        return []
    return [token for token in normalized.split('_') if token]


def canonical_dot_fields() -> List[str]:
    """Return sorted canonical NUT fields used by the renamer."""
    combined = set(STATIC_FIELDS) | set(DYNAMIC_FIELDS) | set(CANONICAL_EXTRA_FIELDS)
    return sorted(item for item in combined if item)


def canonical_keys() -> List[str]:
    """Return sorted canonical underscore keys."""
    return [dot_to_canonical(item) for item in canonical_dot_fields()]


def _mapping_model():
    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSMonitorVariableMapping'):
        return db.ModelClasses.UPSMonitorVariableMapping

    from core.db.orm.orm_ups_monitor_variable_mappings import init_model

    return init_model(db.Model, logger)


def list_target_mappings(target_id: int) -> List[Dict[str, object]]:
    """Return mapping rows for a target."""
    MappingModel = _mapping_model()
    rows = (
        MappingModel.query.filter(
            MappingModel.target_id == int(target_id),
            MappingModel.is_enabled == True,
        )
        .order_by(MappingModel.canonical_key.asc())
        .all()
    )
    return [row.to_dict() for row in rows]


def target_mapping_sources(target_id: int) -> Dict[str, str]:
    """Return canonical_key -> source_key map for target."""
    mapping = {}
    for row in list_target_mappings(target_id):
        canonical_key = str(row.get('canonical_key') or '').strip()
        source_key = str(row.get('source_key') or '').strip()
        if canonical_key and source_key:
            mapping[canonical_key] = source_key
    return mapping


def save_target_mappings(target_id: int, mapping_by_canonical: Dict[str, str], replace: bool = True):
    """Persist mapping set for one target."""
    MappingModel = _mapping_model()
    canonical_allowed = set(canonical_keys())

    normalized_payload: Dict[str, str] = {}
    for canonical_key, source_key in (mapping_by_canonical or {}).items():
        canonical_clean = _normalize_name(canonical_key)
        source_clean = str(source_key or '').strip()
        if canonical_clean not in canonical_allowed:
            continue
        if source_clean:
            normalized_payload[canonical_clean] = source_clean

    existing_rows = (
        MappingModel.query.filter(MappingModel.target_id == int(target_id))
        .order_by(MappingModel.canonical_key.asc())
        .all()
    )
    existing_by_key = {str(row.canonical_key): row for row in existing_rows}

    if replace:
        for canonical_key, row in existing_by_key.items():
            if canonical_key not in normalized_payload:
                db.session.delete(row)

    for canonical_key, source_key in normalized_payload.items():
        row = existing_by_key.get(canonical_key)
        if row is None:
            row = MappingModel(
                target_id=int(target_id),
                canonical_key=canonical_key,
                source_key=source_key,
                mapping_mode='manual',
                is_enabled=True,
            )
            db.session.add(row)
            continue

        row.source_key = source_key
        row.mapping_mode = 'manual'
        row.is_enabled = True

    db.session.commit()


def _candidate_score(canonical_key: str, candidate_key: str) -> float:
    canonical_norm = _normalize_name(canonical_key)
    candidate_norm = _normalize_name(candidate_key)

    if not canonical_norm or not candidate_norm:
        return 0.0

    if canonical_norm == candidate_norm:
        return 5.0

    canonical_tokens = _tokenize(canonical_norm)
    candidate_tokens = _tokenize(candidate_norm)
    if not canonical_tokens or not candidate_tokens:
        return 0.0

    shared_tokens = set(canonical_tokens) & set(candidate_tokens)
    if not shared_tokens:
        return 0.0

    if canonical_norm.endswith(candidate_norm) or candidate_norm.endswith(canonical_norm):
        return 4.5

    overlap = len(shared_tokens) / float(max(len(canonical_tokens), len(candidate_tokens)))
    if len(shared_tokens) < 2 and overlap < 0.6:
        return 0.0

    score = overlap * 2.0
    if canonical_tokens[-1] == candidate_tokens[-1]:
        score += 1.0
    if canonical_tokens[0] == candidate_tokens[0]:
        score += 0.5
    if canonical_tokens[0] in candidate_tokens and canonical_tokens[-1] in candidate_tokens:
        score += 0.3

    return score


def suggest_source_for_canonical(
    canonical_key: str,
    available_source_keys: Iterable[str],
) -> Optional[str]:
    """Return best source key suggestion for one canonical key."""
    available = [str(item).strip() for item in available_source_keys if str(item).strip()]
    if not available:
        return None

    # Fast path for direct canonical key or dot variant.
    canonical_dot = canonical_to_dot(canonical_key)
    if canonical_dot in available:
        return canonical_dot
    if canonical_key in available:
        return canonical_key

    best_key = None
    best_score = 0.0
    for candidate in available:
        score = _candidate_score(canonical_key, candidate)
        if score > best_score:
            best_score = score
            best_key = candidate

    if best_score < 1.6:
        return None
    return best_key


def suggest_mapping(
    available_source_keys: Iterable[str],
    existing_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build canonical_key -> suggested source_key map."""
    existing_mapping = existing_mapping or {}
    available = sorted({str(item).strip() for item in available_source_keys if str(item).strip()})

    suggestions: Dict[str, str] = {}
    for canonical_key in canonical_keys():
        if canonical_key in existing_mapping and existing_mapping.get(canonical_key):
            suggestions[canonical_key] = str(existing_mapping[canonical_key]).strip()
            continue

        suggested = suggest_source_for_canonical(canonical_key, available)
        if suggested:
            suggestions[canonical_key] = suggested

    return suggestions


def build_source_list(raw_payload: Dict[str, object]) -> List[str]:
    """Return sorted source list from raw payload keys."""
    return sorted(
        {str(key).strip() for key in (raw_payload or {}).keys() if str(key).strip()}
    )


def _resolve_value_from_source(source_key: str, raw_payload: Dict[str, object]) -> Tuple[bool, object]:
    if not source_key:
        return False, None

    source_clean = str(source_key).strip()
    if source_clean in raw_payload:
        return True, raw_payload[source_clean]

    source_dot = source_clean.replace('_', '.')
    if source_dot in raw_payload:
        return True, raw_payload[source_dot]

    source_underscore = source_clean.replace('.', '_')
    for key, value in raw_payload.items():
        if dot_to_canonical(key) == source_underscore:
            return True, value

    source_normalized = _normalize_name(source_clean)
    for key, value in raw_payload.items():
        if _normalize_name(key) == source_normalized:
            return True, value

    return False, None


def canonicalize_payload(
    raw_payload: Dict[str, object],
    target_id: Optional[int] = None,
    include_auto_suggestion: bool = True,
) -> Dict[str, object]:
    """
    Convert raw upsc payload to canonical underscore keys.

    The resulting dictionary keeps direct canonical conversions and applies
    per-target manual mappings first, then optional automatic suggestions.
    """
    raw_payload = raw_payload or {}

    canonical_payload: Dict[str, object] = {}
    for key, value in raw_payload.items():
        canonical_payload[dot_to_canonical(key)] = _safe_float(value)

    if target_id is None:
        return canonical_payload

    manual_mapping = target_mapping_sources(target_id)
    for canonical_key, source_key in manual_mapping.items():
        resolved, value = _resolve_value_from_source(source_key, raw_payload)
        if resolved:
            canonical_payload[canonical_key] = _safe_float(value)

    if not include_auto_suggestion:
        return canonical_payload

    available_source_keys = build_source_list(raw_payload)
    suggestions = suggest_mapping(
        available_source_keys=available_source_keys,
        existing_mapping=manual_mapping,
    )
    for canonical_key, source_key in suggestions.items():
        if canonical_key in canonical_payload and canonical_payload[canonical_key] is not None:
            continue
        resolved, value = _resolve_value_from_source(source_key, raw_payload)
        if resolved:
            canonical_payload[canonical_key] = _safe_float(value)

    return canonical_payload


def build_catalog_rows(target_id: int, available_source_keys: Iterable[str]) -> List[Dict[str, object]]:
    """Build API-friendly catalog rows for Renamer UI."""
    current = target_mapping_sources(target_id)
    suggestions = suggest_mapping(available_source_keys=available_source_keys, existing_mapping=current)
    sources = sorted({str(item).strip() for item in available_source_keys if str(item).strip()})

    rows = []
    for canonical_key in canonical_keys():
        current_source = current.get(canonical_key)
        suggested_source = suggestions.get(canonical_key)
        selected_source = current_source or suggested_source or ''

        status = 'unmapped'
        if current_source:
            status = 'mapped'
        elif suggested_source:
            status = 'suggested'

        rows.append(
            {
                'canonical_key': canonical_key,
                'canonical_dot_key': canonical_to_dot(canonical_key),
                'current_source': current_source or '',
                'suggested_source': suggested_source or '',
                'selected_source': selected_source,
                'status': status,
                'source_options': sources,
            }
        )

    return rows
