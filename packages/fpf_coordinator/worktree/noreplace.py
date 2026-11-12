# -*- coding: utf-8 -*-
"""Atomic no-replace rename.

The H2 lifecycle protocol decides ownership by racing a single name; a rename
that silently overwrites the destination decides nothing.  ``os.replace`` is
therefore never acceptable here.  Each platform is bound to a primitive that
fails when the destination exists, and a platform that cannot promise that
fails closed instead of degrading.
"""
from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path


class NoReplaceUnsupported(RuntimeError):
    """This platform/filesystem cannot guarantee no-replace semantics."""


class DestinationExists(FileExistsError):
    """The destination name is already taken; nothing was changed."""


def _renameat2_noreplace(src: str, dst: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, "renameat2", None)
    if fn is None:
        raise NoReplaceUnsupported("renameat2 not available")
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                   ctypes.c_uint]
    fn.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace_flag = 1
    rc = fn(at_fdcwd, os.fsencode(src), at_fdcwd, os.fsencode(dst),
            rename_noreplace_flag)
    if rc == 0:
        return
    err = ctypes.get_errno()
    if err in (errno.EEXIST, errno.ENOTEMPTY):
        raise DestinationExists(errno.EEXIST, os.strerror(err), dst)
    if err in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
        raise NoReplaceUnsupported(os.strerror(err))
    raise OSError(err, os.strerror(err), src, None, dst)


def _renamex_np_excl(src: str, dst: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, "renamex_np", None)
    if fn is None:
        raise NoReplaceUnsupported("renamex_np not available")
    fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    rename_excl = 0x00000004
    rc = fn(os.fsencode(src), os.fsencode(dst), rename_excl)
    if rc == 0:
        return
    err = ctypes.get_errno()
    if err in (errno.EEXIST, errno.ENOTEMPTY):
        raise DestinationExists(errno.EEXIST, os.strerror(err), dst)
    if err in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
        raise NoReplaceUnsupported(os.strerror(err))
    raise OSError(err, os.strerror(err), src, None, dst)


def rename_noreplace(src: os.PathLike[str] | str,
                     dst: os.PathLike[str] | str) -> None:
    """Rename ``src`` to ``dst``; raise ``DestinationExists`` when taken."""
    src_s, dst_s = os.fspath(src), os.fspath(dst)
    if not os.path.exists(src_s):
        raise FileNotFoundError(src_s)
    if os.name == "nt":
        # MoveFileEx without MOVEFILE_REPLACE_EXISTING.  Python's os.rename
        # maps to exactly that and raises FileExistsError when dst exists.
        try:
            os.rename(src_s, dst_s)
        except FileExistsError as exc:
            raise DestinationExists(errno.EEXIST, os.strerror(errno.EEXIST),
                                    dst_s) from exc
        return
    if sys.platform == "darwin":
        _renamex_np_excl(src_s, dst_s)
        return
    _renameat2_noreplace(src_s, dst_s)


def archive_unique(root: os.PathLike[str] | str, name: str,
                   suffix: str) -> Path:
    """Archive ``root/name`` under a unique sibling name; never overwrite."""
    base = Path(root)
    target = base / suffix
    rename_noreplace(base / name, target)
    return target
