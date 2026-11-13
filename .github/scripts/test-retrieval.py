"""Offline behavioral checks for the optional retrieval helper."""

import argparse
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-quality-review/retrieve.py"
SPEC = importlib.util.spec_from_file_location("retrieval", SCRIPT)
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)

CARD = '''<li class="result-card"><a class="result-title" href="https://example.test/original">Main <b>problem</b></a>
<a class="meta-link" href="/p/10?lang=zh&amp;q=long-query&amp;page=1">Statement</a>
<details><ul><li><a class="t" href="https://example.test/alias">Alias</a>
<a class="meta-link" href="/p/11?lang=zh&amp;q=long-query">Statement</a></li></ul></details></li>'''


class Response(io.BytesIO):
    def __init__(self, body, content_type="text/html; charset=utf-8"):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def geturl(self):
        return "https://example.test/final"


class RetrievalChecks(unittest.TestCase):
    def test_probe_without_cache_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=directory,
                                    capture_output=True, encoding="utf-8", check=True)
            self.assertTrue(json.loads(result.stdout)["ok"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_grouped_candidates_and_short_mirror_urls(self):
        result = HELPER.parse_candidates({"html": CARD, "total": 1}, "https://www.cpret.online")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Main problem")
        self.assertEqual(result[0]["statement"], "https://www.cpret.online/p/10?lang=zh")
        self.assertEqual(result[0]["members"], [{"title": "Alias", "url": "https://example.test/alias",
                                              "statement": "https://www.cpret.online/p/11?lang=zh"}])

    def test_invalid_markup_is_not_zero_matches(self):
        for data in [{"html": "<p>maintenance</p>", "total": 10},
                     {"html": CARD[:-5], "total": 1}, {"error": "changed API"}]:
            with self.assertRaises(ValueError):
                HELPER.parse_candidates(data, "https://www.cpret.online")
        self.assertEqual(HELPER.parse_candidates({"html": "", "total": 0}, "https://www.cpret.online"), [])

    def test_cache_reuses_successful_response(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = HELPER.Cache(directory)
            with patch.object(HELPER, "urlopen", return_value=Response(b"original")) as request:
                first = cache.download("https://example.test/source")
                second = cache.download("https://example.test/source")
                self.assertEqual(request.call_count, 1)
                self.assertEqual(first, second)
            with patch.object(HELPER, "urlopen", return_value=Response(b"updated")):
                fresh, _ = HELPER.Cache(directory, refresh=True).download("https://example.test/source")
                self.assertEqual(fresh, b"updated")

    def test_full_source_and_continuable_excerpt(self):
        body = '<nav>navigation</nav><article><h1>题目</h1><p>Formula: $a_i &lt; b_i$.</p><pre>  indented code</pre></article><script>noise</script>'
        with tempfile.TemporaryDirectory() as directory:
            cache = HELPER.Cache(directory)
            with patch.object(HELPER, "urlopen", return_value=Response(body.encode("utf-8"))):
                document = HELPER.fetch(cache, "https://example.test/source")
            self.assertEqual(document["status"], "extracted")
            full = Path(document["text_file"]).read_text(encoding="utf-8")
            self.assertIn("$a_i < b_i$", full)
            self.assertIn("  indented code", full)
            self.assertNotIn("navigation", full)
            self.assertNotIn("noise", full)
            first = HELPER.excerpt(cache, document["id"], 0, 10)
            rest = HELPER.excerpt(cache, document["id"], first["next_start"], len(full))
            self.assertTrue(first["has_more"])
            self.assertFalse(rest["has_more"])
            self.assertEqual(first["text"] + rest["text"], full)
            with self.assertRaises(ValueError):
                HELPER.excerpt(cache, "../outside", 0, 10)

    def test_failed_page_retains_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = HELPER.Cache(directory)
            args = argparse.Namespace(query="test", query_file=None, base_url="https://www.cpret.online",
                                      start_page=1, pages=3, lang="en")
            response = Response(json.dumps({"html": CARD, "total": 60, "max_page": 3}).encode(),
                                "application/json")
            with patch.object(HELPER, "urlopen", side_effect=[response, URLError("offline")]):
                result = HELPER.search(cache, args)
            self.assertFalse(result["complete"])
            self.assertEqual(result["failed_page"], 2)
            self.assertEqual(len(result["candidates"]), 1)
            self.assertEqual(json.loads(Path(result["index_file"]).read_text(encoding="utf-8")), result)

    def test_pdf_and_empty_page_route_to_host_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = HELPER.Cache(directory)
            with patch.object(HELPER, "urlopen", return_value=Response(b"%PDF-1.7", "application/pdf")):
                result = HELPER.fetch(cache, "https://example.test/paper")
                self.assertEqual(result["status"], "needs_pdf_tool")
                self.assertTrue(Path(result["raw_file"]).exists())
            with patch.object(HELPER, "urlopen", return_value=Response(b"<script>app()</script>")):
                result = HELPER.fetch(cache, "https://example.test/empty")
                self.assertEqual(result["status"], "needs_browser_tool")


if __name__ == "__main__":
    unittest.main()
