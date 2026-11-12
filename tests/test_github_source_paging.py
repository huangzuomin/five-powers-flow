"""Pagination hardening for the trusted fact source (FINAL-B01)."""
from __future__ import annotations

import unittest

from packages.fpf_coordinator.dispatch import github_source
from packages.fpf_coordinator.dispatch.github_source import GitHubSourceError, _pages


class PagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = github_source._request
        self.calls: list[str] = []

    def tearDown(self) -> None:
        github_source._request = self._original

    def respond(self, page_map):
        def fake(repo, endpoint, token, **kwargs):
            page = int(endpoint.rsplit("page=", 1)[1])
            self.calls.append(endpoint)
            return page_map[page]

        github_source._request = fake

    def test_check_runs_are_fully_paginated(self) -> None:
        self.respond({
            1: {"total_count": 101, "check_runs": [{"id": index} for index in range(100)]},
            2: {"total_count": 101, "check_runs": [{"id": 100}]},
        })
        items = _pages("o/r", "commits/" + "a" * 40 + "/check-runs", "tok",
                       items_key="check_runs")
        self.assertEqual(len(items), 101)
        self.assertEqual(len(self.calls), 2)

    def test_non_object_records_are_rejected(self) -> None:
        self.respond({1: [{"id": 1}, "oops"]})
        with self.assertRaises(GitHubSourceError) as ctx:
            _pages("o/r", "pulls/1/reviews", "tok")
        self.assertIn("Malformed non-object record", str(ctx.exception))

    def test_malformed_envelope_is_rejected(self) -> None:
        self.respond({1: {"unexpected": []}})
        with self.assertRaises(GitHubSourceError):
            _pages("o/r", "commits/x/check-runs", "tok", items_key="check_runs")

    def test_hundredth_full_page_is_rejected(self) -> None:
        self.respond({page: [{"id": page}] * 100 for page in range(1, 102)})
        with self.assertRaises(GitHubSourceError) as ctx:
            _pages("o/r", "pulls/1/reviews", "tok")
        self.assertIn("Pagination exceeded safe bound", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
