from datetime import UTC, datetime, timedelta

import pytest
from rq.timeouts import JobTimeoutException

from app import jobs
from app.db import SessionLocal
from app.engine.executor import ExecutionResult
from app.maintenance import STALE_QUEUED_ERROR, STALE_RUNNING_ERROR, fail_stale_runs
from app.models import Run, RunStatus, User

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    with SessionLocal() as session:
        session.add(User(id="u1", email="u1@example.com", hashed_password="x"))
        session.commit()
        yield session


def make_run(db, run_id, status, *, started_ago=None, created_ago=timedelta(0), node_states=None):
    run = Run(
        id=run_id,
        owner_id="u1",
        status=status,
        graph={"nodes": [], "edges": []},
        node_states=node_states or {},
        created_at=NOW - created_ago,
        started_at=NOW - started_ago if started_ago is not None else None,
    )
    db.add(run)
    db.commit()
    return run


def status_of(run_id):
    with SessionLocal() as session:
        return session.get(Run, run_id)


def test_stuck_running_run_is_failed(db):
    # Cutoff = job timeout (600s) + grace (60s) = 11 minutes; 12 minutes is clearly past it.
    node_states = {
        "a": {"status": "succeeded"},
        "b": {"status": "running"},
        "c": {"status": "pending"},
    }
    make_run(
        db, "stuck", RunStatus.RUNNING, started_ago=timedelta(minutes=12), node_states=node_states
    )
    assert fail_stale_runs(db, now=NOW) == 1

    run = status_of("stuck")
    assert run.status == RunStatus.FAILED
    assert run.error == STALE_RUNNING_ERROR
    assert run.node_states["a"]["status"] == "succeeded"  # finished work is kept
    assert run.node_states["b"]["status"] == "failed"  # the node that was executing
    assert run.node_states["c"]["status"] == "pending"


def test_recent_running_run_is_left_alone(db):
    make_run(db, "busy", RunStatus.RUNNING, started_ago=timedelta(minutes=5))
    assert fail_stale_runs(db, now=NOW) == 0
    assert status_of("busy").status == RunStatus.RUNNING


def test_cutoff_boundary(db):
    # Exactly at the cutoff the worker could still be writing its result: leave it.
    make_run(db, "at", RunStatus.RUNNING, started_ago=timedelta(minutes=11))
    make_run(db, "past", RunStatus.RUNNING, started_ago=timedelta(minutes=11, seconds=1))
    assert fail_stale_runs(db, now=NOW) == 1
    assert status_of("at").status == RunStatus.RUNNING
    assert status_of("past").status == RunStatus.FAILED


def test_lost_queued_run_is_failed(db):
    make_run(db, "lost", RunStatus.QUEUED, created_ago=timedelta(minutes=20))
    make_run(db, "fresh", RunStatus.QUEUED, created_ago=timedelta(minutes=1))
    assert fail_stale_runs(db, now=NOW) == 1
    assert status_of("lost").error == STALE_QUEUED_ERROR
    assert status_of("fresh").status == RunStatus.QUEUED


def test_finished_runs_are_never_touched(db):
    make_run(db, "old-ok", RunStatus.SUCCEEDED, started_ago=timedelta(days=3))
    assert fail_stale_runs(db, now=NOW) == 0
    assert status_of("old-ok").status == RunStatus.SUCCEEDED


def test_reaper_is_safe_to_run_twice(db):
    make_run(db, "stuck", RunStatus.RUNNING, started_ago=timedelta(hours=1))
    assert fail_stale_runs(db, now=NOW) == 1
    assert fail_stale_runs(db, now=NOW) == 0  # idempotent: nothing left to do


def test_late_worker_result_does_not_overwrite_reaper(db, monkeypatch):
    make_run(db, "slow", RunStatus.QUEUED)

    def execute_then_get_reaped(graph, inputs, on_state):
        # While the worker is busy, the reaper decides the run is dead...
        with SessionLocal() as other:
            other.get(Run, "slow").status = RunStatus.FAILED
            other.commit()
        # ...then the worker finishes anyway.
        return ExecutionResult(outputs={"answer": "too late"})

    monkeypatch.setattr(jobs, "execute_pipeline", execute_then_get_reaped)
    jobs.process_run("slow")

    run = status_of("slow")
    assert run.status == RunStatus.FAILED
    assert run.outputs == {}


def test_rq_timeout_gives_a_clear_message(db, monkeypatch):
    make_run(db, "long", RunStatus.QUEUED)

    def too_slow(graph, inputs, on_state):
        on_state("llm-1", {"status": "running"})
        raise JobTimeoutException("Task exceeded maximum timeout value")

    monkeypatch.setattr(jobs, "execute_pipeline", too_slow)
    jobs.process_run("long")

    run = status_of("long")
    assert run.status == RunStatus.FAILED
    assert "timed out" in run.error
    assert run.node_states["llm-1"]["status"] == "failed"
