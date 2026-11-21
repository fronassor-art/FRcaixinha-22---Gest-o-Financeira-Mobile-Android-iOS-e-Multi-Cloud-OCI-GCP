"""M40810 bearer guard: deterministic header/cookie precedence, no network/DB."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from app.m40810_bearer_input_guard import (
    BearerInputBlocked, strict_bearer_candidate,
)

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / "backend/app/dependencies.py"
DOC = ROOT / "docs/FR_FINANCE_M40810_BEARER_AMBIGUITY_NO_GO.md"
CI = ROOT / ".github/workflows/frfinance-m40810-bearer-ambiguity-ci.yml"
TOKEN = "m40810_test-only_fixture-1__abcDEF012345"


def test_normal_bearer_without_cookie():
    assert strict_bearer_candidate(["Bearer " + TOKEN], None) == TOKEN


def test_normal_cookie_without_header():
    assert strict_bearer_candidate([], TOKEN) == TOKEN


def test_bearer_wins_over_other_cookie():
    assert strict_bearer_candidate(["Bearer " + TOKEN], "old_test_cookie") == TOKEN


@pytest.mark.parametrize("headers,cookie", [
    ([], None),
    ([], ""),
    ([""], TOKEN),
    (["Basic ci"], TOKEN),
    (["bearer " + TOKEN], TOKEN),
    (["Bearer "], TOKEN),
    (["Bearer " + TOKEN, "Bearer " + TOKEN], TOKEN),
    (["Bearer " + TOKEN + " trailing"], TOKEN),
    (["Bearer " + TOKEN + "\n"], TOKEN),
    (["Bearer " + TOKEN + "."], TOKEN),
    (["Bearer " + TOKEN + "="], TOKEN),
    (["Bearer " + TOKEN + "%20"], TOKEN),
    (["Bearer " + TOKEN + "/" ], TOKEN),
    ([], "a" * 257),
    (["Bearer " + "a" * 257], TOKEN),
    ([], "é"),
    ([], b"fixture"),
    ([], object()),
    ("Bearer " + TOKEN, None),
])
def test_invalid_ambiguous_binary_or_unbounded_input_denied(headers, cookie):
    with pytest.raises(BearerInputBlocked):
        strict_bearer_candidate(headers, cookie)


def test_server_bearer_is_valid_for_existing_synthetic_sessions():
    assert strict_bearer_candidate(["Bearer synthetic-ci-token"], None) == "synthetic-ci-token"
    assert strict_bearer_candidate(["Bearer m37462-ci-only-first-bearer-NEVER-REAL-01"], None)


def test_real_auth_dependency_never_uses_cookie_fallback_for_bad_header():
    s = DEPS.read_text(encoding="utf-8")
    ast.parse(s)
    assert "request.headers.getlist('authorization')" in s
    assert "strict_bearer_candidate(headers, cookie)" in s
    assert "except BearerInputBlocked:" in s
    assert "digest = hash_token(raw_token)" in s
    assert s.index("strict_bearer_candidate(headers, cookie)") < s.index("digest = hash_token(raw_token)")


def test_workflow_and_document_preserve_unreleased_state():
    yml = CI.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    assert "test_m40810_bearer_input_no_go_ci.py" in yml
    for marker in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                   "ATIVACAO_REAL: 'OFF'"):
        assert marker in yml
    for marker in ("M40570", "M40730", "GUC", "NO-GO", "PRODUCTION=BLOCKED"):
        assert marker in doc
