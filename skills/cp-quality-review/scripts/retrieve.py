#!/usr/bin/env python3
"""Optional retrieval helper bundled with this skill. Standard library only; run --check first."""

import sys

if sys.version_info < (3, 8):
    sys.exit("Python 3.8 or later is required; use the host's tools instead.")

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


def emit(value):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2))


class Candidates(HTMLParser):
    """Keep every result and every nested identical/similar member."""

    def __init__(self, base):
        super().__init__()
        self.base, self.items = base, []
        self.card, self.depth, self.link = None, 0, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "li":
            if "result-card" in classes:
                self.card = {"title": "", "members": []}
                self.depth = 1
            elif self.card is not None:
                self.depth += 1
        if tag == "a" and self.card is not None:
            href = urljoin(self.base, attrs.get("href", ""))
            if "result-title" in classes:
                self.link = self.card
                self.link.update(url=href, title="")
            elif "t" in classes:
                self.link = {"title": "", "url": href}
                self.card["members"].append(self.link)
            elif "meta-link" in classes and "/p/" in href:
                target = self.card
                if self.depth > 1 and self.card["members"]:
                    target = self.card["members"][-1]
                parsed = urlparse(href)
                language = parse_qs(parsed.query).get("lang", ["en"])[0]
                target["statement"] = parsed._replace(
                    query=urlencode({"lang": language}), fragment="").geturl()

    def handle_data(self, data):
        if self.link is not None:
            self.link["title"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            if self.link is not None:
                self.link["title"] = " ".join(self.link["title"].split())
            self.link = None
        if tag == "li" and self.card is not None:
            self.depth -= 1
            if self.depth == 0:
                self.items.append(self.card)
                self.card = None


class BodyText(HTMLParser):
    skipped = {"script", "style", "noscript", "nav", "footer", "form", "svg"}
    blocks = {"p", "div", "article", "section", "pre", "li", "tr", "br",
              "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.hidden, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.skipped:
            self.hidden += 1
        if not self.hidden and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.skipped:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        value = "\n".join(line.rstrip() for line in "".join(self.parts).splitlines())
        return re.sub(r"\n{3,}", "\n\n", value).strip()


class Cache:
    def __init__(self, directory, refresh=False, timeout=30):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.refresh, self.timeout = refresh, timeout

    def download(self, url):
        if urlparse(url).scheme not in ("http", "https"):
            raise ValueError("Only HTTP(S) URLs are supported.")
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        raw = self.root / (key + ".raw")
        meta_path = self.root / (key + ".json")
        if not self.refresh and raw.exists() and meta_path.exists():
            return raw.read_bytes(), json.loads(meta_path.read_text(encoding="utf-8"))
        request = Request(url, headers={"User-Agent": "CPScore retrieval helper"})
        with urlopen(request, timeout=self.timeout) as response:
            data = response.read()
            meta = {"id": key, "url": url, "final_url": response.geturl(),
                    "content_type": response.headers.get_content_type(),
                    "encoding": response.headers.get_content_charset() or "utf-8",
                    "fetched_at": datetime.now(timezone.utc).isoformat()}
        raw.write_bytes(data)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return data, meta


def parse_candidates(data, base):
    if not isinstance(data, dict) or not isinstance(data.get("html"), str):
        raise ValueError("Unrecognized CPRet response; use the host's browser/search tools.")
    parser = Candidates(base)
    parser.feed(data["html"])
    parser.close()
    if parser.card is not None:
        raise ValueError("Incomplete CPRet markup; inspect the saved response.")
    if not parser.items and data.get("total") != 0:
        raise ValueError("No recognizable candidate cards; this is not a zero-match result.")
    if any(not item.get("title") or not item.get("url") for item in parser.items):
        raise ValueError("Incomplete CPRet candidate cards; inspect the saved response.")
    return parser.items


def search(cache, args):
    query = args.query
    if args.query_file:
        query = Path(args.query_file).read_text(encoding="utf-8").strip()
    result = {"query": query, "complete": True, "pages": [], "candidates": []}
    for page in range(args.start_page, args.start_page + args.pages):
        url = args.base_url.rstrip("/") + "/api/search?" + urlencode(
            {"q": query, "page": page, "lang": args.lang, "mmr": "0", "dedup": "1"})
        try:
            raw, meta = cache.download(url)
            data = json.loads(raw.decode(meta["encoding"]))
            candidates = parse_candidates(data, args.base_url)
            result["pages"].append({"page": page, "source": meta})
            result["candidates"].extend(candidates)
            if not candidates or page >= data.get("max_page", page + 1):
                break
        except (OSError, ValueError) as error:
            result.update(complete=False, failed_page=page, error=str(error))
            break
    key = hashlib.sha256(json.dumps([query, args.base_url, args.start_page, args.pages,
                                    args.lang]).encode("utf-8")).hexdigest()[:20]
    index = cache.root / ("search-" + key + ".json")
    result["index_file"] = str(index.resolve())
    index.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def fetch(cache, url):
    raw, meta = cache.download(url)
    if "pdf" in meta["content_type"] or raw.startswith(b"%PDF-"):
        return dict(meta, status="needs_pdf_tool", raw_file=str(
            (cache.root / (meta["id"] + ".raw")).resolve()))
    text = raw.decode(meta["encoding"], errors="replace")
    if "html" in meta["content_type"]:
        parser = BodyText()
        parser.feed(text)
        text = parser.text()
    if not text.strip():
        return dict(meta, status="needs_browser_tool", reason="No readable text was extracted.")
    target = cache.root / (meta["id"] + ".txt")
    target.write_text(text, encoding="utf-8")
    return dict(meta, status="extracted", characters=len(text),
                text_file=str(target.resolve()), next_action="read --id " + meta["id"])


def excerpt(cache, key, start, length):
    if not re.fullmatch(r"[0-9a-f]{20}", key):
        raise ValueError("Use the document id returned by fetch.")
    text = (cache.root / (key + ".txt")).read_text(encoding="utf-8")
    meta = json.loads((cache.root / (key + ".json")).read_text(encoding="utf-8"))
    end = min(len(text), start + length)
    if start > len(text):
        raise ValueError("Start is beyond the end of the document.")
    return {"id": key, "url": meta["url"], "fetched_at": meta["fetched_at"],
            "start": start, "end": end, "characters": len(text),
            "has_more": end < len(text), "next_start": end, "text": text[start:end]}


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer.")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check Python and standard-library imports; no network or writes.")
    parser.add_argument("--cache-dir", help="Use a task-specific temporary directory.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--timeout", type=positive, default=30)
    commands = parser.add_subparsers(dest="command")
    command = commands.add_parser("search", help="CPRet candidate index, including all grouped members.")
    queries = command.add_mutually_exclusive_group(required=True)
    queries.add_argument("--query")
    queries.add_argument("--query-file")
    command.add_argument("--base-url", default="https://www.cpret.online")
    command.add_argument("--lang", choices=("en", "zh"), default="en")
    command.add_argument("--start-page", type=positive, default=1)
    command.add_argument("--pages", type=positive, default=3)
    commands.add_parser("fetch", help="Cache a source and extract readable text.").add_argument("--url", required=True)
    command = commands.add_parser("read", help="Read a bounded excerpt, with continuation offsets.")
    command.add_argument("--id", required=True)
    command.add_argument("--start", type=int, default=0)
    command.add_argument("--length", type=positive, default=8000)
    args = parser.parse_args(argv)
    if args.check:
        emit({"ok": True, "python": sys.version.split()[0], "dependencies": "standard library only"})
        return 0
    if not args.command or not args.cache_dir:
        parser.error("A command and --cache-dir are required; use --check to probe the environment.")
    if args.command == "read" and args.start < 0:
        parser.error("--start must be nonnegative.")
    try:
        cache = Cache(args.cache_dir, args.refresh, args.timeout)
        if args.command == "search":
            result = search(cache, args)
        elif args.command == "fetch":
            result = fetch(cache, args.url)
        else:
            result = excerpt(cache, args.id, args.start, args.length)
        emit(result)
        return 0 if result.get("complete", True) else 1
    except (OSError, ValueError, LookupError) as error:
        emit({"error": str(error), "fallback": "Use the host's search, browsing or file tools."})
        return 1


if __name__ == "__main__":
    sys.exit(main())
