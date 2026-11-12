# -*- coding: utf-8 -*-
"""Lock identity: the authorization triple, and its revalidation.

An arbiter win only says "this round, you may act".  Whether there is still an
object to act on is a separate question answered by re-reading the lock and
comparing ``(run_id, st_dev, st_ino)``.  The arbiter name is reusable; the
authorization is not.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

LOCK_NAME = "lifecycle.lock"
AUTHORIZED = "AUTHORIZED"
LOCK_LOST = "LOCK_LOST"


class LockUnreadable(RuntimeError):
    pass


@dataclass(frozen=True)
class LockIdentity:
    run_id: str
    dev: int
    ino: int


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def read_lock(root: os.PathLike[str] | str) -> tuple[dict, LockIdentity]:
    path = Path(root) / LOCK_NAME
    stat = path.stat()
    raw = path.read_bytes()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockUnreadable("lock is not valid JSON") from exc
    claimed = record.pop("content_sha256", None)
    if claimed != hashlib.sha256(_canonical(record)).hexdigest():
        raise LockUnreadable("lock digest mismatch")
    record["content_sha256"] = claimed
    return record, LockIdentity(str(record["run_id"]), stat.st_dev, stat.st_ino)


def verify(root: os.PathLike[str] | str, expected: LockIdentity) -> str:
    """Revalidate the original lock identity after winning arbitration.

    Returns ``AUTHORIZED`` or ``LOCK_LOST``.  A *different* lock is still a
    failure: it is not the object the authorization was issued for, so per the
    frozen protocol it is reported as ``LOCK_LOST`` rather than a new code.
    """
    try:
        _, current = read_lock(root)
    except FileNotFoundError:
        return LOCK_LOST
    except LockUnreadable:
        return LOCK_LOST
    if (current.run_id, current.dev, current.ino) != (
            expected.run_id, expected.dev, expected.ino):
        return LOCK_LOST
    return AUTHORIZED
