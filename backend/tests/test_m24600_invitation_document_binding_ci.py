"""M24600 — publication-bound invitation staging contract (no PostgreSQL)."""
import inspect
from pathlib import Path

from app.account_lifecycle import prepare_invitation_ci

ROOT = Path(__file__).resolve().parents[2]


def test_invite_requires_explicit_document_reference():
    argument = inspect.signature(prepare_invitation_ci).parameters["required_document_id"]
    assert argument.kind == inspect.Parameter.KEYWORD_ONLY
    assert argument.default is inspect.Parameter.empty


def test_document_is_published_and_membership_kind_before_insert():
    text = (ROOT / "backend/app/account_lifecycle.py").read_text()
    segment = text.split("def prepare_invitation_ci(", 1)[1].split(
        "def simulate_invitation_delivery_ci(", 1
    )[0]
    assert "_ci_only(conn)" in segment
    assert "not isinstance(required_document_id, UUID)" in segment
    assert "document_kind='TENANT_MEMBERSHIP'" in segment
    assert "published_at IS NOT NULL" in segment
    assert "FOR SHARE" in segment
    assert "required_document_id)," in segment
    assert segment.index("if not document:") < segment.index("INSERT INTO public.invitations")


def test_ci_fixture_does_not_retroactively_patch_invitation_document():
    fixture = (ROOT / "backend/tests/test_aistudio_account_lifecycle_ci.py").read_text()
    assert "UPDATE public.invitations SET required_document_id=%s" not in fixture
    assert "test_invitation_requires_published_membership_document_at_creation" in fixture


def test_public_invitation_remains_unavailable():
    router = (ROOT / "backend/app/routers/invitations.py").read_text()
    assert "prepare_invitation_ci" not in router
    assert "Convites ainda não implementados" in router
    assert "status.HTTP_503_SERVICE_UNAVAILABLE" in router


def test_legacy_ci_invitation_callers_are_versioned_at_creation():
    """M24601: guard the previously overlooked CI call sites."""
    import ast

    for relative in (
        "backend/tests/test_aistudio_account_lifecycle_ci.py",
        "backend/tests/test_aistudio_live_engines_ci.py",
        "backend/tests/test_aistudio_lifecycle_disabled.py",
    ):
        source = (ROOT / relative).read_text()
        assert "UPDATE public.invitations SET required_document_id=%s" not in source
        tree = ast.parse(source, filename=relative)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "prepare_invitation_ci"
        ]
        assert calls, f"No invitation invocations found in {relative}"
        for call in calls:
            assert any(key.arg == "required_document_id" for key in call.keywords), (
                f"Missing required_document_id in {relative} at line {call.lineno}"
            )
