"""M37500 plan is immutable, deterministic and never live authorization."""
from dataclasses import replace
import json
import pytest

from app.m37500_release_workplan import (
    LIVE_GATES, PROVIDER_GATES, WORKSTREAMS, ReleaseTask,
    workplan, plan_summary,
)
from app.release_evidence_matrix import (
    PRIORITY_ORDER as EXISTING_LIVE_GATES,
    PROVIDER_GATES as EXISTING_PROVIDER_GATES,
)


def test_full_plan_192_tasks_16_streams_and_unique_ids():
    t = workplan()
    assert len(t) == 192
    assert len(WORKSTREAMS) == 16
    assert len({x.task_id for x in t}) == 192
    assert {x.stream for x in t} == {s for s, _ in WORKSTREAMS}
    assert t[0].task_id == "M37501"
    assert t[-1].task_id == "M37692"
    assert all(x.status == "PLANNED_NOT_REAL_VERIFIED" for x in t)


def test_dependencies_in_each_stream_are_ordered_and_acyclic():
    t = workplan()
    known = set()
    for item in t:
        assert all(dep in known for dep in item.depends_on)
        assert len(item.depends_on) == (0 if item.step == 1 else 1)
        assert item.task_id not in known
        known.add(item.task_id)


def test_canonical_release_gates_have_not_drifted():
    assert LIVE_GATES == EXISTING_LIVE_GATES
    assert PROVIDER_GATES == EXISTING_PROVIDER_GATES


@pytest.mark.parametrize("idx", range(192))
def test_every_task_is_a_non_authorizing_review_step(idx):
    x = workplan()[idx]
    assert x.description
    assert 1 <= x.step <= 12
    assert not x.cloud_mutation_authorized
    assert not x.local_sql_apply_authorized
    assert not x.real_user_activation_authorized
    assert not x.real_pix_authorized


@pytest.mark.parametrize("idx", range(16))
def test_each_stream_has_exactly_twelve_unique_steps(idx):
    stream, actions = WORKSTREAMS[idx]
    assert len(actions) == 12
    assert len(set(actions)) == 12
    assert [t.step for t in workplan() if t.stream == stream] == list(range(1, 13))


def test_summary_does_not_accept_external_observation_as_release_evidence():
    for operator_evidence in (None, {}, {"vm_running": True},
                              {"activation_approved": True, "pix": "ON"}):
        x = plan_summary(evidence=operator_evidence)
        assert x["tasks_total"] == 192
        assert x["live_gates_verified_by_this_tool"] == 0
        assert x["provider_gates_verified_by_this_tool"] == 0
        assert x["tasks_real_verified_by_this_tool"] == 0
        assert not x["real_activation_authorized"]
        assert not x["pix_real_authorized"]
        assert not x["payments_real_authorized"]
        assert not x["staging_only_sql_apply_authorized"]
        assert not x["cloud_mutations_authorized"]
        assert len(x["tasks"]) == 192
        assert "activation_approved" not in json.dumps(x)


@pytest.mark.parametrize("bad", ["TRUE", True, [], 1])
def test_invalid_plan_evidence_container_fails_closed(bad):
    with pytest.raises(ValueError):
        plan_summary(evidence=bad)


def test_release_task_cannot_be_mutated_after_generation():
    x = workplan()[0]
    with pytest.raises(Exception):
        x.real_pix_authorized = True


def test_plan_never_contains_secrets_or_personal_information():
    x = json.dumps(plan_summary())
    assert "ocid1." not in x
    assert "refresh_token" not in x
    assert "SMTP_PASSWORD" not in x
    assert "DATABASE_URL" not in x
    assert "AUTH_SECRET" not in x
