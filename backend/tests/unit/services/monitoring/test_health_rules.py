"""Unit tests for the Production Health pure rules (no DB, no I/O).

Covers the P2-01B additions: global platform status, queue-aware thresholds,
trend direction, and error sanitization. These functions are the observable
contract of the health service, so they are pinned directly.
"""

from __future__ import annotations

from app.schemas.health_dashboard import PipelineStage
from app.services.monitoring.health_service import (
    FAILED_CRIT,
    FAILED_WARN,
    PENDING_CRIT,
    PENDING_WARN,
    STALE_PROCESSING_CRIT_S,
    STALE_PROCESSING_WARN_S,
    _state_for_age,
    _worst,
    overall_status,
    queue_state,
    sanitize_error,
    trend_direction,
)


def _stage(state: str) -> PipelineStage:
    return PipelineStage(key="k", name="N", state=state, description="d")  # type: ignore[arg-type]


# --- worst-of ---------------------------------------------------------------


def test_worst_of_states() -> None:
    assert _worst(["healthy", "healthy"]) == "healthy"
    assert _worst(["healthy", "warning"]) == "warning"
    assert _worst(["warning", "critical", "healthy"]) == "critical"
    assert _worst([]) == "healthy"


# --- global platform status -------------------------------------------------


def test_overall_healthy() -> None:
    s = overall_status([_stage("healthy"), _stage("healthy")])
    assert s.state == "healthy"
    assert s.title == "Production Healthy"


def test_overall_warning_when_any_warning_none_critical() -> None:
    s = overall_status([_stage("healthy"), _stage("warning")])
    assert s.state == "warning"
    assert s.title == "Attention Required"


def test_overall_critical_when_any_critical() -> None:
    s = overall_status([_stage("warning"), _stage("critical"), _stage("healthy")])
    assert s.state == "critical"
    assert s.title == "Production Incident"


# --- queue-aware thresholds -------------------------------------------------


def test_queue_healthy_below_thresholds() -> None:
    state, reason = queue_state(pending=10, failed=0, stale_processing_seconds=100)
    assert state == "healthy"
    assert reason is None


def test_pending_warning_and_critical() -> None:
    assert queue_state(PENDING_WARN, 0, None)[0] == "warning"
    assert queue_state(PENDING_CRIT, 0, None)[0] == "critical"


def test_failed_warning_and_critical() -> None:
    assert queue_state(0, FAILED_WARN, None)[0] == "warning"
    assert queue_state(0, FAILED_CRIT, None)[0] == "critical"


def test_stale_processing_warning_and_critical() -> None:
    assert queue_state(0, 0, STALE_PROCESSING_WARN_S)[0] == "warning"
    assert queue_state(0, 0, STALE_PROCESSING_CRIT_S)[0] == "critical"


def test_queue_takes_the_worst_rule() -> None:
    # pending only warning, but failed critical → overall critical.
    state, reason = queue_state(PENDING_WARN, FAILED_CRIT, None)
    assert state == "critical"
    assert reason is not None and "échec" in reason.lower()


# --- activity age -----------------------------------------------------------


def test_state_for_age() -> None:
    assert _state_for_age(None, 10, 20) == "warning"  # never seen → unknown
    assert _state_for_age(5, 10, 20) == "healthy"
    assert _state_for_age(10, 10, 20) == "warning"
    assert _state_for_age(20, 10, 20) == "critical"


# --- trend direction --------------------------------------------------------


def test_trend_direction() -> None:
    assert trend_direction(25) == "up"
    assert trend_direction(-14) == "down"
    assert trend_direction(0) == "stable"


# --- error sanitization -----------------------------------------------------


def test_sanitize_empty() -> None:
    assert sanitize_error(None) == ""
    assert sanitize_error("") == ""


def test_sanitize_redacts_secrets() -> None:
    assert "sk-" not in sanitize_error("auth failed key=sk-ABCDEF1234567890")
    assert "Bearer" not in sanitize_error("401 Bearer abcdef.token.value")
    assert "r8_" not in sanitize_error("replicate r8_ABCDEF1234567890 rejected")
    redacted = sanitize_error("token=deadbeefdeadbeefdeadbeefdeadbeef01")
    assert "***" in redacted


def test_sanitize_single_line_and_truncated() -> None:
    multi = "first line boom\nsecond line\nthird"
    assert sanitize_error(multi) == "first line boom"
    assert len(sanitize_error("x" * 500)) == 200
