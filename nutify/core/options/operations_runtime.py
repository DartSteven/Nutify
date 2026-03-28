"""Runtime operation formulas and per-target configuration helpers."""

from __future__ import annotations

import ast
import math
import re
import time
from typing import Any, Dict, Optional, Tuple

from flask import current_app, has_app_context

from core.logger import options_logger as logger
from core.multi_nut.target_scope import resolve_settings_target_id

DEFAULT_OPERATION_SETTINGS: Dict[str, Any] = {
    'measured_power_metric_key': 'ups_realpower',
    'load_metric_key': 'ups_load',
    'nominal_power_metric_key': 'ups_realpower_nominal',
    'realpower_formula': '(load_percent / 100.0) * nominal_power_w',
    'power_calibration_factor': 1.0,
    'energy_formula': 'power_w * delta_hours',
    'cost_formula': '(energy_wh / 1000.0) * price_per_kwh',
    'co2_formula': '(energy_wh / 1000.0) * co2_factor',
}

_CACHE_TTL_SECONDS = 5.0
_SETTINGS_CACHE: Dict[Optional[int], Tuple[float, Dict[str, Any]]] = {}
_METRIC_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_.]+$')


def _is_sqlalchemy_ready() -> bool:
    """Return True when current Flask app has SQLAlchemy extension initialized."""
    if not has_app_context():
        return False

    try:
        return current_app.extensions.get('sqlalchemy') is not None
    except Exception:
        return False


def _safe_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _normalize_metric_key(value: Any, fallback: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return fallback
    normalized = raw.replace(' ', '').lower()
    if not _METRIC_KEY_PATTERN.match(normalized):
        return fallback
    return normalized[:120]


def _normalize_formula(value: Any, fallback: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return fallback
    return raw[:260]


def _normalize_calibration_factor(value: Any, fallback: float = 1.0) -> float:
    parsed = _safe_float(value)
    if parsed is None:
        return float(fallback)
    # Keep multiplier in a practical/safe range.
    if parsed < 0.1:
        return 0.1
    if parsed > 3.0:
        return 3.0
    return float(parsed)


def _resolve_variable_config_model():
    if not _is_sqlalchemy_ready():
        return None, None

    from core.db.ups import VariableConfig, db

    model = None
    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
        model = db.ModelClasses.VariableConfig
    elif hasattr(VariableConfig, 'query'):
        model = VariableConfig
    return model, db


def _query_scoped_row(model, scoped_target_id: Optional[int], include_global_fallback: bool):
    if not model:
        return None

    query = model.query
    if not hasattr(model, 'target_id'):
        return query.order_by(model.id.desc()).first()

    if scoped_target_id is None:
        return query.filter(model.target_id.is_(None)).order_by(model.id.desc()).first()

    scoped_row = query.filter(model.target_id == int(scoped_target_id)).order_by(model.id.desc()).first()
    if scoped_row or not include_global_fallback:
        return scoped_row

    return query.filter(model.target_id.is_(None)).order_by(model.id.desc()).first()


def _build_payload(row, scoped_target_id: Optional[int]) -> Dict[str, Any]:
    payload = {
        **DEFAULT_OPERATION_SETTINGS,
        'target_id': getattr(row, 'target_id', None) if row else None,
        'scope_target_id': scoped_target_id,
    }
    if not row:
        return payload

    for field, fallback in DEFAULT_OPERATION_SETTINGS.items():
        value = getattr(row, field, None)
        if field.endswith('_metric_key'):
            payload[field] = _normalize_metric_key(value, fallback)
        elif field == 'power_calibration_factor':
            payload[field] = _normalize_calibration_factor(value, fallback=fallback)
        else:
            payload[field] = _normalize_formula(value, fallback)
    return payload


def invalidate_operations_cache(target_id: Optional[int] = None) -> None:
    """Invalidate in-memory settings cache for one target or all targets."""
    if target_id is None:
        _SETTINGS_CACHE.clear()
        return

    _SETTINGS_CACHE.pop(int(target_id), None)
    _SETTINGS_CACHE.pop(None, None)


def get_operation_settings(target_id: Optional[int] = None, force_reload: bool = False) -> Dict[str, Any]:
    """Return per-target operation settings with global fallback."""
    scoped_target_id = resolve_settings_target_id(target_id)
    cache_key = int(scoped_target_id) if scoped_target_id else None

    if not force_reload:
        cached = _SETTINGS_CACHE.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return dict(cached[1])

    model, _db = _resolve_variable_config_model()
    row = None
    if model is not None:
        try:
            row = _query_scoped_row(model, scoped_target_id, include_global_fallback=True)
        except Exception as exc:
            logger.debug("Operation settings query unavailable, using defaults: %s", exc)
    payload = _build_payload(row, scoped_target_id)
    _SETTINGS_CACHE[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, dict(payload))
    return payload


def save_operation_settings(payload: Dict[str, Any], target_id: Optional[int] = None) -> Dict[str, Any]:
    """Persist operation settings for current target scope."""
    model, db = _resolve_variable_config_model()
    if not model or db is None:
        raise RuntimeError('VariableConfig model is not available (database not initialized)')

    scoped_target_id = resolve_settings_target_id(target_id)
    row = _query_scoped_row(model, scoped_target_id, include_global_fallback=False)
    if not row:
        row = model()
        if hasattr(row, 'target_id'):
            row.target_id = scoped_target_id
        db.session.add(row)

    for field, fallback in DEFAULT_OPERATION_SETTINGS.items():
        raw = payload.get(field)
        if field.endswith('_metric_key'):
            normalized = _normalize_metric_key(raw, fallback)
        elif field == 'power_calibration_factor':
            normalized = _normalize_calibration_factor(raw, fallback=fallback)
        else:
            normalized = _normalize_formula(raw, fallback)
        if hasattr(row, field):
            setattr(row, field, normalized)

    db.session.commit()
    invalidate_operations_cache(scoped_target_id)
    return get_operation_settings(target_id=scoped_target_id, force_reload=True)


def _extract_metric_value(metrics: Dict[str, Any], metric_key: str) -> Optional[float]:
    if not metrics:
        return None

    normalized_key = _normalize_metric_key(metric_key, metric_key)
    candidates = [
        normalized_key,
        normalized_key.replace('.', '_'),
        normalized_key.replace('_', '.'),
    ]
    for key in candidates:
        if key in metrics:
            value = _safe_float(metrics.get(key))
            if value is not None:
                return value
    return None


def _resolve_attribute_key(node: ast.AST) -> Optional[str]:
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return '.'.join(reversed(parts))
    return None


class _FormulaEvaluator(ast.NodeVisitor):
    _BIN_OPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }
    _UNARY_OPS = {
        ast.UAdd: lambda v: +v,
        ast.USub: lambda v: -v,
    }
    _FUNCS = {
        'max': max,
        'min': min,
        'abs': abs,
        'round': round,
    }

    def __init__(self, context: Dict[str, float]):
        self.context = context

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> float:
        operator = self._BIN_OPS.get(type(node.op))
        if operator is None:
            raise ValueError('Unsupported operator')
        left = self.visit(node.left)
        right = self.visit(node.right)
        return float(operator(left, right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        operator = self._UNARY_OPS.get(type(node.op))
        if operator is None:
            raise ValueError('Unsupported unary operator')
        return float(operator(self.visit(node.operand)))

    def visit_Name(self, node: ast.Name) -> float:
        if node.id in self.context:
            return float(self.context[node.id])
        raise KeyError(f'Unknown variable: {node.id}')

    def visit_Attribute(self, node: ast.Attribute) -> float:
        key = _resolve_attribute_key(node)
        if not key:
            raise KeyError('Unsupported attribute access')
        if key in self.context:
            return float(self.context[key])
        alias = key.replace('.', '_')
        if alias in self.context:
            return float(self.context[alias])
        raise KeyError(f'Unknown variable: {key}')

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name):
            raise ValueError('Unsupported function')
        func = self._FUNCS.get(node.func.id)
        if func is None:
            raise ValueError(f'Unsupported function: {node.func.id}')
        if node.keywords:
            raise ValueError('Keyword arguments are not supported')
        args = [self.visit(arg) for arg in node.args]
        return float(func(*args))

    def visit_Constant(self, node: ast.Constant) -> float:
        value = _safe_float(node.value)
        if value is None:
            raise ValueError('Unsupported constant')
        return value

    def visit_Num(self, node: ast.Num) -> float:  # pragma: no cover
        return float(node.n)

    def generic_visit(self, node: ast.AST) -> float:
        raise ValueError(f'Unsupported expression node: {type(node).__name__}')


def _evaluate_formula(expression: str, context: Dict[str, float], fallback: float) -> float:
    try:
        parsed = ast.parse(expression, mode='eval')
        value = _FormulaEvaluator(context).visit(parsed)
        if math.isnan(value) or math.isinf(value):
            return fallback
        return float(value)
    except Exception as exc:
        logger.debug("Formula evaluation failed for '%s': %s", expression, exc)
        return fallback


def _build_formula_context(metrics: Optional[Dict[str, Any]], extra: Dict[str, Any]) -> Dict[str, float]:
    context: Dict[str, float] = {}

    for key, value in (metrics or {}).items():
        parsed = _safe_float(value)
        if parsed is None:
            continue
        normalized = str(key or '').strip()
        if not normalized:
            continue
        context[normalized] = parsed
        context[normalized.replace('.', '_')] = parsed

    for key, value in extra.items():
        parsed = _safe_float(value)
        if parsed is None:
            continue
        context[str(key)] = parsed

    return context


def compute_realpower_watts(
    metrics: Dict[str, Any],
    *,
    target_id: Optional[int] = None,
    nominal_default: float = 0.0,
) -> float:
    """Compute real power using scoped formula settings."""
    settings = get_operation_settings(target_id=target_id)

    direct_value = _extract_metric_value(metrics, settings['measured_power_metric_key'])
    if direct_value is not None:
        return max(0.0, direct_value)

    load_percent = _extract_metric_value(metrics, settings['load_metric_key']) or 0.0
    nominal_power = _extract_metric_value(metrics, settings['nominal_power_metric_key'])
    if nominal_power is None:
        nominal_power = max(0.0, _safe_float(nominal_default) or 0.0)

    fallback = max(0.0, (nominal_power * load_percent) / 100.0) if nominal_power > 0 else 0.0
    context = _build_formula_context(
        metrics,
        {
            'load_percent': load_percent,
            'nominal_power_w': nominal_power,
            'ups.load': load_percent,
            'ups.realpower.nominal': nominal_power,
        },
    )
    evaluated = _evaluate_formula(settings['realpower_formula'], context, fallback)
    calibration_factor = _normalize_calibration_factor(settings.get('power_calibration_factor', 1.0))
    return max(0.0, evaluated * calibration_factor)


def compute_energy_wh(power_w: float, delta_hours: float, target_id: Optional[int] = None) -> float:
    """Compute energy (Wh) from power and interval using scoped formula."""
    safe_power = max(0.0, _safe_float(power_w) or 0.0)
    safe_delta = max(0.0, _safe_float(delta_hours) or 0.0)
    fallback = safe_power * safe_delta
    context = _build_formula_context(
        {},
        {
            'power_w': safe_power,
            'delta_hours': safe_delta,
            'energy_wh': fallback,
        },
    )
    settings = get_operation_settings(target_id=target_id)
    return max(0.0, _evaluate_formula(settings['energy_formula'], context, fallback))


def compute_cost(energy_wh: float, price_per_kwh: float, target_id: Optional[int] = None) -> float:
    """Compute energy cost using scoped formula."""
    safe_energy = max(0.0, _safe_float(energy_wh) or 0.0)
    safe_price = max(0.0, _safe_float(price_per_kwh) or 0.0)
    fallback = (safe_energy / 1000.0) * safe_price
    context = _build_formula_context(
        {},
        {
            'energy_wh': safe_energy,
            'price_per_kwh': safe_price,
            'cost': fallback,
        },
    )
    settings = get_operation_settings(target_id=target_id)
    return max(0.0, _evaluate_formula(settings['cost_formula'], context, fallback))


def compute_co2_kg(energy_wh: float, co2_factor: float, target_id: Optional[int] = None) -> float:
    """Compute CO2 estimate using scoped formula."""
    safe_energy = max(0.0, _safe_float(energy_wh) or 0.0)
    safe_factor = max(0.0, _safe_float(co2_factor) or 0.0)
    fallback = (safe_energy / 1000.0) * safe_factor
    context = _build_formula_context(
        {},
        {
            'energy_wh': safe_energy,
            'co2_factor': safe_factor,
            'co2_kg': fallback,
        },
    )
    settings = get_operation_settings(target_id=target_id)
    return max(0.0, _evaluate_formula(settings['co2_formula'], context, fallback))
