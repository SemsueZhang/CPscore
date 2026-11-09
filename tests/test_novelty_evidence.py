"""Offline checks for candidate recall, bounded reads, cache validity, and usage."""
import copy
from email.message import Message
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

from cpscore import novelty_evidence as e


def fixture():
    rows = [{"rank": i, "title": "Problem " + str(i), "source": "OJ",
             "url": "https://example.test/problem/" + str(i),
             "statement_url": "https://www.cpret.online/p/" + str(i) + "?q=long-query&page=3&lang=en"}
            for i in range(1, 61)]
    rows[24]["group_members"] = [{"title": "Independent group member",
        "url": "https://acm.timus.ru/problem.aspx?space=1&num=1234",
        "statement_url": "https://www.cpret.online/p/1234?q=long-query&page=3&lang=en"}]
    return {"provider": "cpret", "query": "model", "status": "ok", "complete": True,
            "candidates": rows, "retained_count": 60, "fetched_pages": [1, 2, 3],
            "raw_response": "original complete response", "responses": [{"raw_response": "page 1"}]}


def options(**changes):
    args = dict(provider="cpret", page=1, limit=60, dedup=False, timeout=35,
                cpret_url="https://www.cpret.online", arxiv_interface="web")
    return SimpleNamespace(**{**args, **changes})


class Response:
    def __init__(self, body):
        self.body = body.encode()
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.status, self.url = 200, "https://example.test/paper"

    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *args): pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache, self.ledger = self.root / "cache", self.root / "calls.jsonl"

    def tearDown(self): self.temp.cleanup()

    def test_all_ranks_and_group_links_are_recoverable(self):
        record = fixture()
        path = self.root / "search.json"
        e.save(record, path)
        view = e.index_view(record, path)
        self.assertEqual(len(view["candidates"]), 60)
        self.assertEqual([c["rank"] for c in view["candidates"]], list(range(1, 61)))
        late = view["candidates"][24]
        group = late["group_members"][0]
        selected = e.inspect_candidates(path, [late["id"], group["id"]])
        self.assertEqual(selected["candidates"][1]["url"], record["candidates"][24]["group_members"][0]["url"])
        self.assertIn("lang=en", selected["candidates"][1]["statement_url"])
        self.assertNotIn("q=", selected["candidates"][1]["statement_url"])
        self.assertEqual(json.loads(path.read_text()), record)
        self.assertNotIn("raw_response", view)

    def test_abstract_is_only_expanded_on_selection(self):
        record = fixture()
        record["provider"] = "arxiv"
        record["candidates"][0]["summary"] = "critical abstract"
        path = self.root / "papers.json"
        e.save(record, path)
        index = e.index_view(record, path)
        self.assertNotIn("critical abstract", json.dumps(index))
        detail = e.inspect_candidates(path, [index["candidates"][0]["id"]])
        self.assertEqual(detail["candidates"][0]["summary"], "critical abstract")

    def test_unknown_candidate_does_not_succeed(self):
        path = self.root / "search.json"
        e.save(fixture(), path)
        self.assertEqual(e.inspect_candidates(path, ["unknown"])["status"], "error")

    def test_search_cache_reuses_only_identical_parameters(self):
        with patch.object(e.search_module, "search", side_effect=lambda *a: copy.deepcopy(fixture())) as fetch:
            first = e.search_cached(options(), "model", self.root / "a.json", self.cache, self.ledger)
            second = e.search_cached(options(), "model", self.root / "b.json", self.cache, self.ledger)
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(fetch.call_count, 1)
            e.search_cached(options(dedup=True), "model", self.root / "c.json", self.cache)
            self.assertEqual(fetch.call_count, 2)
            e.search_cached(options(), "model", self.root / "d.json", self.cache, refresh=True)
            self.assertEqual(fetch.call_count, 3)
        self.assertEqual(len(self.ledger.read_text().splitlines()), 2)

    def test_cache_expiry_and_partial_failure_retry(self):
        with patch.object(e.search_module, "search", side_effect=lambda *a: copy.deepcopy(fixture())) as fetch:
            e.search_cached(options(), "model", self.root / "a.json", self.cache)
            cache = next((self.cache / "search").glob("*.json"))
            os.utime(cache, (time.time()-100, time.time()-100))
            e.search_cached(options(), "model", self.root / "a.json", self.cache, ttl=1)
            self.assertEqual(fetch.call_count, 2)
        partial = fixture()
        partial.update(status="partial", complete=False, fetched_pages=[1])
        with patch.object(e.search_module, "search", return_value=partial) as fetch:
            for i in range(2):
                view = e.search_cached(options(), "partial", self.root / "partial.json", self.cache)
                self.assertEqual(view["status"], "partial")
                self.assertFalse(view["cache_hit"])
            self.assertEqual(fetch.call_count, 2)

    def test_source_is_cached_and_late_theorem_can_be_read(self):
        html = '<nav>navigation</nav><script>hidden</script><script type="math/tex">x^2</script>'
        html += ''.join('<p>' + str(i) + ' ' + 'words ' * 70 + '</p>' for i in range(100))
        html += '<h2>Theorem 10</h2><p>Important condition</p><a href="/editorial">Editorial</a>'
        with patch.object(e.urllib.request, "urlopen", side_effect=lambda *a, **k: Response(html)) as fetch:
            first = e.read_source(self.root / "source.json", self.cache, url="https://example.test/paper")
            second = e.read_source(self.root / "excerpt.json", self.cache, url="https://example.test/paper",
                                   find="Theorem 10", context=1)
            self.assertTrue(first["truncated"])
            self.assertLessEqual(len(first["text"]), 6000)
            self.assertNotIn("Theorem 10", first["text"])
            self.assertIn("Theorem 10", second["text"])
            self.assertIn("Important condition", second["text"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(fetch.call_count, 1)
        saved = json.loads((self.root / "source.json").read_text())
        self.assertEqual(saved["raw_response"], html)
        self.assertIn("x^2", saved["text"])
        self.assertNotIn("hidden", saved["text"])
        self.assertEqual(saved["links"], ["https://example.test/editorial"])

    def test_source_failure_is_not_cached_as_empty_success(self):
        with patch.object(e.urllib.request, "urlopen", side_effect=[URLError("offline"), Response('<p>real text</p>')]) as fetch:
            a = e.read_source(self.root / "a.json", self.cache, url="https://example.test/retry")
            b = e.read_source(self.root / "b.json", self.cache, url="https://example.test/retry")
            self.assertEqual(a["status"], "error")
            self.assertEqual(b["status"], "ok")
            self.assertEqual(fetch.call_count, 2)

    def test_long_line_pagination_does_not_drop_text(self):
        record = {"status": "ok", "text": "甲" * 20000}
        next_line, pieces = 1, []
        while next_line is not None:
            view = e.excerpt(record, "unused.json", start_line=next_line, max_lines=7, max_chars=1000)
            pieces.extend(line.split(": ", 1)[1] for line in view["text"].splitlines())
            next_line = view["next_line"]
        self.assertEqual("".join(pieces), record["text"])

    def test_find_can_continue_after_first_matches(self):
        record = {"status": "ok", "text": "\n".join('needle '+str(i) for i in range(100))}
        first = e.excerpt(record, "unused.json", find="needle", max_lines=5, context=0)
        second = e.excerpt(record, "unused.json", find="needle", start_line=first["next_line"], max_lines=5, context=0)
        self.assertIn("needle 5", second["text"])
        self.assertNotIn("needle 0", second["text"])

    def test_usage_distinguishes_returned_partial_and_missing(self):
        path = self.root / "events.jsonl"
        rows = [{"type": "turn.started"}, {"type": "turn.completed", "turn_id": "a", "usage": {
            "input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 15}},
            {"type": "turn.started"}, {"type": "turn.completed", "turn_id": "b", "usage": {
            "input_tokens": 50, "cached_input_tokens": 0, "output_tokens": 10}}]
        path.write_text('\n'.join(json.dumps(row) for row in rows))
        data = e.usage_summary([path])
        self.assertEqual(data["usage_status"], "reported")
        self.assertEqual((data["input_tokens"], data["non_cached_input_tokens"], data["output_tokens"]), (150, 90, 25))
        self.assertIsNone(data["reasoning_output_tokens"])
        rows.append({"type": "turn.started"})
        path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n{"partial"')
        self.assertEqual(e.usage_summary([path])["usage_status"], "partial")
        data = e.usage_summary([])
        self.assertEqual(data["usage_status"], "unavailable")
        self.assertIsNone(data["input_tokens"])




if __name__ == '__main__': unittest.main(verbosity=2)
