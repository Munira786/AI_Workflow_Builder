"""Background maintenance: recover runs that will never finish on their own.

A worker can die mid-run (out of memory, container stopped during a deploy, machine reboot).
A dead process can't report its own death, so this "reaper" runs separately, finds runs that
have been stuck too long, and marks them failed so users get an answer instead of a spinner.

Run once:        python -m app.maintenance
Run every 60s:   python -m app.maintenance --loop 60
"""

import argparse
import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Run, RunStatus

logger = logging.getLogger(__name__)

# RQ hard-stops a job after run_job_timeout_seconds, so anything "running" longer than that
# (plus a little slack for clock differences and the final DB write) can no longer finish.
RUNNING_GRACE = timedelta(seconds=60)

# A queued run should be picked up within seconds. If it's still queued after this long, the
# Redis job was lost (e.g. Redis restarted without persistence) and no worker will ever take it.
QUEUED_TIMEOUT = timedelta(minutes=15)

STALE_RUNNING_ERROR = "The run stopped unexpectedly (worker crashed or timed out). Please retry."
STALE_QUEUED_ERROR = "The run was never picked up by a worker. Please retry."


def fail_unfinished_nodes(node_states: dict, reason: str) -> dict:
    """Mark the node that was executing as failed so the editor doesn't show it spinning."""
    failed = {"status": "failed", "error": reason}
    return {
        node_id: failed if state.get("status") == "running" else state
        for node_id, state in node_states.items()
    }


def fail_stale_runs(db: Session, now: datetime | None = None) -> int:
    """Mark stuck runs as failed. Returns how many runs were recovered."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    running_cutoff = now - timedelta(seconds=settings.run_job_timeout_seconds) - RUNNING_GRACE
    queued_cutoff = now - QUEUED_TIMEOUT

    stale = db.scalars(
        select(Run).where(
            or_(
                (Run.status == RunStatus.RUNNING) & (Run.started_at < running_cutoff),
                (Run.status == RunStatus.QUEUED) & (Run.created_at < queued_cutoff),
            )
        )
    ).all()

    recovered = 0
    for run in stale:
        error = STALE_RUNNING_ERROR if run.status == RunStatus.RUNNING else STALE_QUEUED_ERROR
        # Conditional update: only change the row if its status is still what we saw.
        # If a worker finished it a millisecond ago, or another reaper got there first,
        # rowcount is 0 and we leave it alone. This is "optimistic concurrency".
        result = db.execute(
            update(Run)
            .where(Run.id == run.id, Run.status == run.status)
            .values(
                status=RunStatus.FAILED,
                error=error,
                finished_at=now,
                node_states=fail_unfinished_nodes(run.node_states or {}, error),
            )
        )
        if result.rowcount == 1:
            recovered += 1
            logger.warning("Recovered stale run %s (was %s)", run.id, run.status)
    db.commit()
    return recovered


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover stuck pipeline runs.")
    parser.add_argument(
        "--loop", type=int, metavar="SECONDS", help="repeat forever, SECONDS between passes"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    while True:
        try:
            with SessionLocal() as db:
                count = fail_stale_runs(db)
            if count:
                logger.info("Recovered %d stale run(s)", count)
        except Exception:
            # Never let one bad pass (e.g. DB briefly unreachable) kill the reaper itself.
            logger.exception("Maintenance pass failed")
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
