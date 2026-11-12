#!/usr/bin/env python3
"""Write the untrusted probe request produced by the read-only trigger workflow."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

PROBE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{7,39}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    probe_id = os.environ.get("PROBE_ID", "")
    if not PROBE_ID_RE.match(probe_id):
        raise SystemExit("PROBE_ID_INVALID")
    attempts = int(os.environ.get("ATTEMPTS") or "0")
    window = int(os.environ.get("WINDOW") or "0")
    if not 2 <= attempts <= 6:
        raise SystemExit("PROBE_ATTEMPTS_INVALID")
    if not 30 <= window <= 120:
        raise SystemExit("PROBE_WINDOW_INVALID")
    payload = {
        "schema": "fpf-probe-request/v1",
        "probe_id": probe_id,
        "attempts": attempts,
        "window_seconds": window,
        "requested_by": os.environ.get("GITHUB_ACTOR", ""),
        "requested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
