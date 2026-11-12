"""FACT_SOURCE_VERIFY unit tests (R11-C01..C08)."""
from __future__ import annotations

import unittest

from packages.fpf_coordinator.dispatch import fact_source
from packages.fpf_coordinator.dispatch.fact_source import (
    FactSourceError,
    EVENT_ID_CONFLICT,
    EVENT_PAGINATION_INCOMPLETE,
    EVENT_SOURCE_UNAVAILABLE,
    EVENT_SOURCE_SNAPSHOT_DRIFT,
    EVENT_COUNT_MISMATCH,
    EVENT_DUPLICATE_MISMATCH,
    EVENT_FIELD_MISMATCH,
    EVENT_ID_MISMATCH,
    EVENT_ORDER_MISMATCH,
    RETRY_ROUNDS,
    PassSnapshot,
    canonical_bytes,
    collect_endpoint,
    compare_event_log,
    compare_event_sequence,
    compare_passes,
    sha256_hex,
    stable_observation,
    _event_id_conflicts,
)


def snapshot(passes: int, digest_tag: str) -> PassSnapshot:
    events = ({"event_id": digest_tag * 8, "payload_digest": digest_tag * 8},)
    page = {
        "pass": passes, "endpoint": "pulls/1/reviews", "page": 1, "count": 1,
        "first_event_id": digest_tag * 8, "last_event_id": digest_tag * 8,
        "page_sha256": digest_tag * 16, "collected_at": "2026-01-01T00:00:00Z",
    }
    pr = {"head_sha": "a" * 40, "base_sha": "b" * 40, "state": "open",
          "merged": False, "updated_at": "x", "digest": "d" * 64}
    return PassSnapshot(pass_no=passes, before=pr, after=pr, pages=(page,), events=events)


class CanonicalizationTests(unittest.TestCase):
    def test_canonical_bytes_is_order_independent(self) -> None:
        self.assertEqual(
            canonical_bytes({"b": 1, "a": 2}), canonical_bytes({"a": 2, "b": 1}),
        )
        self.assertNotEqual(sha256_hex(canonical_bytes({"a": 1})), sha256_hex(canonical_bytes({"a": 2})))


class CompareTests(unittest.TestCase):
    def test_identical_passes_are_stable(self) -> None:
        compare_passes(snapshot(1, "a"), snapshot(2, "a"))

    def test_different_event_sets_drift(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_passes(snapshot(1, "a"), snapshot(2, "b"))
        self.assertEqual(ctx.exception.code, EVENT_SOURCE_SNAPSHOT_DRIFT)

    def test_same_ids_but_different_content_drift(self) -> None:
        left = snapshot(1, "a")
        right = PassSnapshot(
            pass_no=2, before=left.before, after=left.after, pages=left.pages,
            events=({"event_id": "a" * 64, "payload_digest": "b" * 64},),
        )
        with self.assertRaises(FactSourceError):
            compare_passes(left, right)

    def test_event_id_conflict_is_rejected(self) -> None:
        events = [
            {"event_id": "x", "payload_digest": "1"},
            {"event_id": "x", "payload_digest": "2"},
        ]
        self.assertEqual(_event_id_conflicts(events), ["x:1!=2"])

    def test_duplicate_identical_events_do_not_conflict(self) -> None:
        events = [
            {"event_id": "x", "payload_digest": "1"},
            {"event_id": "x", "payload_digest": "1"},
        ]
        self.assertEqual(_event_id_conflicts(events), [])


class EventLogCompareTests(unittest.TestCase):
    def test_count_mismatch(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_log([{"event_id": "a"}], [])
        self.assertEqual(ctx.exception.code, EVENT_COUNT_MISMATCH)

    def test_id_mismatch(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_log([{"event_id": "a"}], [{"event_id": "b"}])
        self.assertEqual(ctx.exception.code, EVENT_ID_MISMATCH)

    def test_field_mismatch(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_log(
                [{"event_id": "a", "type": "X"}], [{"event_id": "a", "type": "Y"}],
            )
        self.assertEqual(ctx.exception.code, EVENT_FIELD_MISMATCH)

    def test_identical_logs_pass(self) -> None:
        events = [{"event_id": "a", "type": "X"}]
        compare_event_log(events, list(events))


class EventSequenceTests(unittest.TestCase):
    """FINAL-B02: order and multiplicity are part of the fact."""

    def test_same_order_passes(self) -> None:
        compare_event_sequence(["a", "b", "c"], ["a", "b", "c"])

    def test_same_set_different_order_is_rejected(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_sequence(["a", "b", "c"], ["a", "c", "b"])
        self.assertEqual(ctx.exception.code, EVENT_ORDER_MISMATCH)

    def test_reversed_order_is_rejected(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_sequence(["a", "b"], ["b", "a"])
        self.assertEqual(ctx.exception.code, EVENT_ORDER_MISMATCH)

    def test_duplicate_multiplicity_is_rejected(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_sequence(["a", "a", "b"], ["a", "b", "b"])
        self.assertEqual(ctx.exception.code, EVENT_ORDER_MISMATCH)

    def test_extra_duplicate_is_rejected(self) -> None:
        with self.assertRaises(FactSourceError) as ctx:
            compare_event_sequence(["a", "b"], ["a", "b", "b"])
        self.assertEqual(ctx.exception.code, EVENT_COUNT_MISMATCH)


class CollectionBindingTests(unittest.TestCase):
    """FINAL-B01: events must come from the pages that produced the forensics."""

    def test_events_are_built_from_the_collected_pages(self) -> None:
        original_snapshot = fact_source._pr_snapshot
        original_collect = fact_source.collect_endpoint
        original_build = fact_source.build_events_from_bundle
        pr = {"number": 1, "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40}}

        fact_source._pr_snapshot = lambda repo, pr_number, token: (
            {"head_sha": "a" * 40, "base_sha": "b" * 40, "state": "open",
             "merged": False, "updated_at": "x", "digest": "d" * 64},
            pr,
        )
        pages = {
            "pulls/1/reviews": [{"id": 11}],
            "commits/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/check-runs": [{"id": 22}],
            "actions/runs?head_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": [{"id": 33}],
        }
        seen: dict[str, object] = {}

        def fake_collect(repo, endpoint, token, *, pass_no, source_object, items_key=None):
            return list(pages[endpoint]), [{
                "pass": pass_no, "endpoint": endpoint, "page": 1,
                "count": len(pages[endpoint]),
                "first_event_id": "", "last_event_id": "",
                "page_sha256": "0" * 64, "collected_at": "2026-01-01T00:00:00Z",
                "_object_ids": [f"{source_object}:{item['id']}" for item in pages[endpoint]],
            }]

        class FakeBatch:
            ordered_events = ()
            complete = True

        def fake_build(repo, bundle, task_id, project_id):
            seen["bundle"] = bundle
            return FakeBatch()

        fact_source.collect_endpoint = fake_collect
        fact_source.build_events_from_bundle = fake_build
        try:
            snapshot = fact_source.collect_pass("o/r", 1, "T", "P", "tok", 1)
        finally:
            fact_source._pr_snapshot = original_snapshot
            fact_source.collect_endpoint = original_collect
            fact_source.build_events_from_bundle = original_build
        bundle = seen["bundle"]
        self.assertEqual(bundle["pr"], pr)
        self.assertEqual(bundle["reviews"], pages["pulls/1/reviews"])
        self.assertEqual(len(snapshot.pages), 3)


class PaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = fact_source._page

    def tearDown(self) -> None:
        fact_source._page = self._original

    def test_stops_at_a_short_page(self) -> None:
        pages = {1: [{"id": i} for i in range(100)], 2: [{"id": 100}]}
        fact_source._page = lambda repo, endpoint, token, page, key: pages[page]
        items, records = collect_endpoint(
            "o/r", "pulls/1/reviews", "t", pass_no=1, source_object="review",
        )
        self.assertEqual(len(items), 101)
        self.assertEqual([record["count"] for record in records], [100, 1])
        self.assertEqual(len(records[0]), 9)  # 8 public fields + private id list

    def test_full_hundredth_page_is_incomplete(self) -> None:
        fact_source._page = lambda repo, endpoint, token, page, key: [{"id": page}] * 100
        with self.assertRaises(FactSourceError) as ctx:
            collect_endpoint("o/r", "pulls/1/reviews", "t", pass_no=1, source_object="review")
        self.assertEqual(ctx.exception.code, EVENT_PAGINATION_INCOMPLETE)

    def test_api_error_never_degrades_to_an_empty_set(self) -> None:
        def boom(repo, endpoint, token, page, key):
            raise FactSourceError(EVENT_SOURCE_UNAVAILABLE, "403")

        fact_source._page = boom
        with self.assertRaises(FactSourceError) as ctx:
            collect_endpoint("o/r", "pulls/1/reviews", "t", pass_no=1, source_object="review")
        self.assertEqual(ctx.exception.code, EVENT_SOURCE_UNAVAILABLE)


class RetryTests(unittest.TestCase):
    def test_three_unstable_rounds_fail_closed(self) -> None:
        original = fact_source.collect_pass
        calls = {"n": 0}

        def flaky(repo, pr, task, project, token, pass_no):
            calls["n"] += 1
            return snapshot(pass_no, "a" if calls["n"] % 2 else "b")

        fact_source.collect_pass = flaky
        try:
            with self.assertRaises(FactSourceError) as ctx:
                stable_observation("o/r", 1, "T", "P", "tok")
        finally:
            fact_source.collect_pass = original
        self.assertEqual(ctx.exception.code, EVENT_SOURCE_SNAPSHOT_DRIFT)
        self.assertEqual(calls["n"], RETRY_ROUNDS * 2)

    def test_first_stable_round_is_accepted(self) -> None:
        original = fact_source.collect_pass
        fact_source.collect_pass = lambda repo, pr, task, project, token, pass_no: snapshot(pass_no, "a")
        try:
            observation, rounds = stable_observation("o/r", 1, "T", "P", "tok")
        finally:
            fact_source.collect_pass = original
        self.assertEqual(len(observation.events), 1)
        self.assertEqual(rounds[0]["status"], "STABLE")


if __name__ == "__main__":
    unittest.main()
