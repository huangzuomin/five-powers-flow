# -*- coding: utf-8 -*-
"""Adapters so the G4 suites run under both unittest and pytest.

``validate`` discovers tests with ``python -m unittest discover`` and does not
install pytest, so these suites must not import pytest.  ``load_tests`` keeps
every module-level ``test_*`` function individually reported by unittest.
"""
from __future__ import annotations

import re
import unittest


class _Raises:
    def __init__(self, exc_type, match=None) -> None:
        self.exc_type = exc_type
        self.match = match
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"{self.exc_type.__name__} was not raised")
        if not issubclass(exc_type, self.exc_type):
            return False
        self.value = exc
        if self.match and not re.search(self.match, str(exc)):
            raise AssertionError(f"{exc!r} does not match {self.match!r}")
        return True


def raises(exc_type, match=None) -> _Raises:
    return _Raises(exc_type, match)


def suite_from_globals(namespace) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for name in sorted(namespace):
        obj = namespace[name]
        if name.startswith("test_") and callable(obj):
            suite.addTest(unittest.FunctionTestCase(obj, description=name))
    return suite
