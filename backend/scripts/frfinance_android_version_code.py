#!/usr/bin/env python3
"""M41590: one versionCode per pinned first-parent FR Finance source commit."""
import re
import subprocess
import sys

ANCHOR = "d54c40693082d711c7ac2955635527f633eb00e6"
BASE_CODE = 4_000_000
LAST_KNOWN_CODE = 3_911_027
MAX_CODE = 2_100_000_000
HEX = re.compile(r"[0-9a-f]{40}")


def version_for_history(history, expected):
    if not HEX.fullmatch(expected) or not history or history[0] != expected:
        raise ValueError("M41590_WRONG_SOURCE_SHA")
    if any(not HEX.fullmatch(v) for v in history) or len(set(history)) != len(history):
        raise ValueError("M41590_INVALID_HISTORY")
    if ANCHOR not in history:
        raise ValueError("M41590_ANCHOR_NOT_ON_FIRST_PARENT")
    code = BASE_CODE + history.index(ANCHOR)
    if not LAST_KNOWN_CODE < code <= MAX_CODE:
        raise ValueError("M41590_VERSION_OUT_OF_RANGE")
    return code


def git(*args):
    return subprocess.check_output(["git", *args], text=True, timeout=30).strip()


def main():
    if len(sys.argv) != 2 or git("rev-parse", "--is-shallow-repository") != "false":
        raise SystemExit("M41590_FULL_HISTORY_AND_EXPECTED_SHA_REQUIRED")
    expected = sys.argv[1]
    if git("rev-parse", "HEAD") != expected:
        raise SystemExit("M41590_WRONG_SOURCE_SHA")
    print(version_for_history(git("rev-list", "--first-parent", "HEAD").splitlines(), expected))


if __name__ == "__main__":
    main()
