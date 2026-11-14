#!/usr/bin/env python3
"""FR Finance 192-step plan: default offline, no shell or live service access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.m37500_release_workplan import plan_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M37500 offline release plan")
    parser.add_argument("mode", nargs="?", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    report = plan_summary()
    if args.mode == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("=== FR FINANCE M37500–M37692 — SUPER MEGA MACROPACOTE ===")
    print("M37500_MODE=OFFLINE_NO_PROVIDERS_NO_DATABASE")
    print("M37500_WORKSTREAMS=" + str(report["workstreams_total"]))
    print("M37500_TASKS_PLANNED=" + str(report["tasks_total"]))
    print("M37500_LIVE_GATES_VERIFIED=0/20")
    print("M37500_PROVIDER_GATES_VERIFIED=0/7")
    print("M37500_REAL_ACTIVATION=OFF")
    print("M37500_REAL_PIX=OFF")
    print("M37500_REAL_PAYMENTS=OFF")
    print("M37500_SQL_APPLY=NOT_EXECUTED")
    print("M37500_CLOUD_MUTATIONS=NOT_EXECUTED")
    print("M37500_STATE=IMPLEMENTATION_AND_LIVE_PROOFS_PENDING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
