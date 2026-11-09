#!/usr/bin/env python3
"""Indexed search, cached source excerpts, and observed usage for problem review."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import textwrap
import time
import urllib.parse
import urllib.request

from . import novelty_search as search_module


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            import fcntl
        except ImportError:
            yield
        else:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def cached_record(path, ttl, refresh):
    if refresh or not path.is_file() or time.time() - path.stat().st_mtime > ttl:
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") == "ok" and record.get("complete") is True:
            return record
    except (OSError, ValueError, AttributeError):
        pass
    return None


def save(record, path):
    search_module.write_record(record, Path(path))


def observe(ledger, action, view, started, cache_hit=False, **details):
    if ledger is not None:
        path = Path(ledger)
        event = {"time": now(), "action": action, "status": view.get("status"),
                 "elapsed_seconds": round(time.monotonic() - started, 6),
                 "response_bytes": len(json.dumps(view, ensure_ascii=False).encode()),
                 "cache_hit": cache_hit, **details}
        with file_lock(path.with_suffix(path.suffix + ".lock")):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    return view


def candidates(record):
    """Stable IDs refer to exact original URLs; no unverified alias merging."""
    for candidate in record.get("candidates", []):
        ident = "p" + digest(candidate["url"])[:16]
        yield ident, candidate, None
        for member in candidate.get("group_members", []):
            yield "p" + digest(member["url"])[:16], member, ident


def index_view(record, record_file):
    def item(candidate):
        result = {"id": "p" + digest(candidate["url"])[:16], "title": candidate["title"]}
        if candidate.get("source"):
            result["source"] = candidate["source"]
        return result
    view = {key: record[key] for key in ("provider", "query", "status", "complete", "retained_count",
            "fetched_pages", "error") if key in record}
    view["record_file"] = str(Path(record_file).resolve())
    view["candidates"] = []
    for candidate in record.get("candidates", []):
        row = item(candidate)
        if "rank" in candidate:
            row["rank"] = candidate["rank"]
        if candidate.get("group_members"):
            row["group_members"] = [item(member) for member in candidate["group_members"]]
        view["candidates"].append(row)
    return view


def inspect_candidates(record_file, identifiers, ledger=None):
    started = time.monotonic()
    record = json.loads(Path(record_file).read_text(encoding="utf-8"))
    by_id = {}
    for ident, candidate, parent in candidates(record):
        if ident not in by_id:
            detail = search_module.candidate_view(candidate)
            detail.pop("group_members", None)
            by_id[ident] = {"id": ident, **detail}
        if parent and ident != parent:
            by_id[ident].setdefault("group_parent_ids", []).append(parent)
    requested = list(dict.fromkeys(identifiers))
    missing = [ident for ident in requested if ident not in by_id]
    result = {"status": "error" if missing else "ok", "record_file": str(Path(record_file).resolve()),
              "candidates": [by_id[ident] for ident in requested if ident in by_id]}
    if missing:
        result["unknown_ids"] = missing
    return observe(ledger, "inspect_candidates", result, started, record_file=str(record_file))


def search_cached(options, query, output, cache_dir, ledger=None, ttl=86400, refresh=False):
    started = time.monotonic()
    query = query.strip()
    if not query:
        raise ValueError("query must be nonempty")
    key_data = {"schema": 1, "provider": options.provider, "query": query, "page": options.page,
                "limit": options.limit, "dedup": options.dedup, "cpret_url": options.cpret_url,
                "arxiv_interface": options.arxiv_interface}
    key = digest(key_data)
    cache = Path(cache_dir) / "search" / (key + ".json")
    with file_lock(cache.with_suffix(".lock")):
        record = cached_record(cache, ttl, refresh)
        if record is not None and (record.get("provider") != options.provider or
                record.get("query") != query or not isinstance(record.get("candidates"), list)):
            record = None
        hit = record is not None
        if record is None:
            if options.provider == "arxiv":
                # search.py also waits three seconds before the actual request.
                with file_lock(Path(cache_dir) / ".arxiv.lock"):
                    record = search_module.search(options, query)
            else:
                record = search_module.search(options, query)
            if record.get("status") == "ok" and record.get("complete") is True:
                save(record, cache)
        save(record, output)
    view = index_view(record, output)
    view["cache_hit"] = hit
    return observe(ledger, "search_" + options.provider, view, started, hit,
                   evidence_file=str(Path(output).resolve()), cache_key=key,
                   retained_count=record.get("retained_count"), fetched_pages=record.get("fetched_pages"))


class PageText(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.hidden, self.parts, self.links = url, [], [], []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in {"style", "nav", "header", "footer"} or (tag == "script" and
                not attrs.get("type", "").startswith("math/tex")):
            self.hidden.append(tag)
        if not self.hidden and tag == "a" and attrs.get("href"):
            self.links.append(urllib.parse.urljoin(self.url, attrs["href"]))
        if not self.hidden and tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "pre", "br", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


def source_lines(text):
    # Excerpt line numbers refer to this stable extracted representation, not PDF pages or HTML source.
    return [piece for line in text.splitlines() for piece in
            (textwrap.wrap(line, width=240, replace_whitespace=False) or [""])]


def excerpt(record, record_file, start_line=1, max_lines=40, find=None, context=3,
            max_chars=6000, include_links=False):
    if start_line < 1 or not 1 <= max_lines <= 200 or not 256 <= max_chars <= 30000 or context < 0:
        raise ValueError("Invalid excerpt bounds")
    view = {key: record[key] for key in ("status", "url", "response_url", "retrieved_at",
            "format", "error", "content_quality") if key in record}
    view["record_file"] = str(Path(record_file).resolve())
    if record.get("status") != "ok":
        return view
    lines = source_lines(record.get("text", ""))
    selected = set()
    if find:
        hits = [i for i, line in enumerate(lines) if find.casefold() in line.casefold()]
        for i in hits:
            if i >= start_line-1:
                selected.update(range(max(start_line-1, i-context), min(len(lines), i+context+1)))
        view["matches_total"] = len(hits)
    else:
        selected.update(range(start_line-1, min(len(lines), start_line-1+max_lines)))
    numbered, shown = [], []
    for i in sorted(selected):
        line = str(i+1) + ": " + lines[i]
        if len(numbered) >= max_lines or sum(len(s)+1 for s in numbered) + len(line) > max_chars:
            break
        numbered.append(line)
        shown.append(i)
    view.update(text="\n".join(numbered), total_lines=len(lines), returned_lines=len(shown),
                line_numbering="extracted text wrapped at 240 characters", truncated=(
                    len(shown) < len(selected) or (not find and bool(shown) and shown[-1]+1 < len(lines))))
    view["next_line"] = shown[-1]+2 if shown and shown[-1]+1 < len(lines) else None
    if find and len(shown) < len(selected):
        view["remaining_ranges"] = [i+1 for i in sorted(selected) if i not in shown][:20]
    if include_links:
        view["links"] = record.get("links", [])[:20]
        view["total_links"] = len(record.get("links", []))
        view["links_truncated"] = len(record.get("links", [])) > 20
    return view


def read_source(output, cache_dir, url=None, source_file=None, ledger=None, ttl=86400,
                refresh=False, timeout=25, **bounds):
    started = time.monotonic()
    if bool(url) == bool(source_file):
        raise ValueError("Supply exactly one of url or source_file")
    hit = False
    if source_file:
        path = Path(source_file)
        raw = path.read_text(encoding="utf-8")
        record = json.loads(raw) if path.suffix == ".json" else {
            "status": "ok", "complete": True, "text": raw, "format": "text"}
        if not isinstance(record, dict) or (record.get("status") == "ok" and "text" not in record):
            raise ValueError("Source file must contain extracted text, not a search result")
        hit = True
    else:
        if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
            raise ValueError("Public HTTP(S) source required")
        cache = Path(cache_dir) / "sources" / (digest(url) + ".json")
        with file_lock(cache.with_suffix(".lock")):
            record = cached_record(cache, ttl, refresh)
            if record is not None and (record.get("url") != url or "text" not in record):
                record = None
            hit = record is not None
            if record is None:
                record = {"status": "error", "complete": False, "url": url, "retrieved_at": now()}
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "Auto-Insight-Problem-Review/2.0"})
                    with urllib.request.urlopen(request, timeout=timeout) as response:
                        raw = response.read()
                        record.update(http_status=response.status, response_url=response.url)
                        if raw.startswith(b"%PDF") or "pdf" in response.headers.get("Content-Type", ""):
                            pdf = Path(output).with_suffix(".pdf")
                            pdf.parent.mkdir(parents=True, exist_ok=True)
                            pdf.write_bytes(raw)
                            record.update(format="pdf", pdf_file=str(pdf.resolve()),
                                          error="Use a PDF reader; this source has not been read as text")
                        else:
                            html = raw.decode(response.headers.get_content_charset() or "utf-8")
                            parser = PageText(response.url)
                            parser.feed(html)
                            text = parser.text()
                            record.update(status="ok", complete=True, format="html", raw_response=html,
                                text=text, links=list(dict.fromkeys(parser.links)),
                                content_quality=search_module.statement_quality(text))
                    if record.get("status") == "ok":
                        save(record, cache)
                except (OSError, ValueError) as error:
                    record["error"] = {"type": type(error).__name__, "message": str(error)}
    save(record, output)
    view = excerpt(record, output, **bounds)
    if record.get("pdf_file"):
        view["pdf_file"] = record["pdf_file"]
    view["cache_hit"] = hit
    return observe(ledger, "read_source", view, started, hit, evidence_file=str(Path(output).resolve()))


def usage_summary(event_files=(), ledger=None, wall_seconds=None):
    """Use returned CLI turn usage only. Missing telemetry is never treated as zero."""
    totals = {key: 0 for key in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                               "output_tokens", "reasoning_output_tokens")}
    known = {key: True for key in totals}
    started_turns = completed_turns = missing = 0
    seen_turns = set()
    for path in dict.fromkeys(str(Path(p).resolve()) for p in event_files):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "turn.started":
                started_turns += 1
            if event.get("type") != "turn.completed":
                continue
            turn = event.get("turn")
            ident = event.get("turn_id") or (turn.get("id") if isinstance(turn, dict) else None)
            if ident and (path, ident) in seen_turns:
                continue
            if ident:
                seen_turns.add((path, ident))
            completed_turns += 1
            data = event.get("usage") or {}
            if not isinstance(data, dict):
                data = {}
            if not data:
                missing += 1
            for key in totals:
                value = data.get(key)
                if type(value) is int and value >= 0:
                    totals[key] += value
                else:
                    known[key] = False
    tokens = {key: value if known[key] and completed_turns else None for key, value in totals.items()}
    if tokens["input_tokens"] is not None and tokens["cached_input_tokens"] is not None:
        diff = tokens["input_tokens"] - tokens["cached_input_tokens"]
        tokens["non_cached_input_tokens"] = diff if diff >= 0 else None
    else:
        tokens["non_cached_input_tokens"] = None
    calls = []
    if ledger and Path(ledger).is_file():
        for line in Path(ledger).read_text(encoding="utf-8").splitlines():
            try:
                call = json.loads(line)
                if isinstance(call, dict):
                    calls.append(call)
            except ValueError:
                continue
    status = "unavailable" if not completed_turns or missing == completed_turns else (
        "partial" if missing or started_turns > completed_turns or not known["input_tokens"] or
        not known["output_tokens"] else "reported")
    return {"usage_status": status, "completed_turns": completed_turns, "started_turns": started_turns,
            "turns_without_usage": missing, "unfinished_turns": max(0, started_turns-completed_turns),
            **tokens, "wall_elapsed_seconds": wall_seconds, "tool_calls": len(calls),
            "tool_cache_hits": sum(bool(c.get("cache_hit")) for c in calls),
            "tool_response_bytes": sum(c.get("response_bytes", 0) for c in calls),
            "tool_elapsed_seconds_sum": round(sum(c.get("elapsed_seconds", 0) for c in calls), 6),
            "notes": ["Cached input is part of input; reasoning output is part of output.",
                      "Missing usage remains unknown; partial runs exclude unreported usage.",
                      "Tool intervals may overlap; their sum is not wall time. Bytes are not tokens or money."]}


def build_parser(prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    search = subs.add_parser("search")
    search.add_argument("provider", choices=["cpret", "arxiv"])
    group = search.add_mutually_exclusive_group(required=True)
    group.add_argument("--query")
    group.add_argument("--query-file", type=Path)
    search.add_argument("--page", type=search_module.positive_int, default=1)
    search.add_argument("--limit", type=search_module.positive_int)
    search.add_argument("--dedup", action="store_true")
    search.add_argument("--timeout", type=search_module.positive_timeout, default=45)
    search.add_argument("--cpret-url", default="https://www.cpret.online")
    search.add_argument("--arxiv-interface", choices=["web", "api"], default="web")
    index = subs.add_parser("index")
    index.add_argument("--record", type=Path, required=True)
    index.add_argument("--ledger", type=Path)
    inspect = subs.add_parser("inspect")
    inspect.add_argument("--record", type=Path, required=True)
    inspect.add_argument("--ids", nargs="+", required=True)
    inspect.add_argument("--ledger", type=Path)
    read = subs.add_parser("read")
    group = read.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--source-file", type=Path)
    read.add_argument("--start-line", type=search_module.positive_int, default=1)
    read.add_argument("--max-lines", type=search_module.positive_int, default=40)
    read.add_argument("--max-chars", type=search_module.positive_int, default=6000)
    read.add_argument("--find")
    read.add_argument("--context", type=int, default=3)
    read.add_argument("--include-links", action="store_true")
    read.add_argument("--timeout", type=search_module.positive_timeout, default=25)
    for p in (search, read):
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--cache-dir", type=Path)
        p.add_argument("--ledger", type=Path)
        p.add_argument("--cache-ttl", type=search_module.positive_timeout, default=86400)
        p.add_argument("--refresh", action="store_true")
    usage = subs.add_parser("usage")
    usage.add_argument("--events", type=Path, nargs="*", default=[])
    usage.add_argument("--ledger", type=Path)
    usage.add_argument("--wall-seconds", type=search_module.positive_timeout)
    usage.add_argument("--output", type=Path, required=True)
    return parser


def execute(args):
    started = time.monotonic()
    try:
        if args.action == "search":
            if args.limit is None:
                args.limit = 60 if args.provider == "cpret" else 10
            query = args.query_file.read_text(encoding="utf-8") if args.query_file else args.query
            result = search_cached(args, query, args.output, args.cache_dir or args.output.parent / ".cache",
                args.ledger or args.output.parent / "calls.jsonl", args.cache_ttl, args.refresh)
        elif args.action == "index":
            result = index_view(json.loads(args.record.read_text(encoding="utf-8")), args.record)
            observe(args.ledger or args.record.parent / "calls.jsonl", "index", result, started, True)
        elif args.action == "inspect":
            result = inspect_candidates(args.record, args.ids, args.ledger or args.record.parent / "calls.jsonl")
        elif args.action == "read":
            result = read_source(args.output, args.cache_dir or args.output.parent / ".cache", url=args.url,
                source_file=args.source_file, ledger=args.ledger or args.output.parent / "calls.jsonl",
                ttl=args.cache_ttl, refresh=args.refresh, timeout=args.timeout, start_line=args.start_line,
                max_lines=args.max_lines, max_chars=args.max_chars, find=args.find, context=args.context,
                include_links=args.include_links)
        else:
            result = usage_summary(args.events, args.ledger, args.wall_seconds)
            save(result, args.output)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status", "ok") == "ok" else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = {"status": "error", "error": {"type": type(error).__name__, "message": str(error)}}
        ledger = getattr(args, "ledger", None)
        if ledger:
            observe(ledger, args.action, result, started)
        print(json.dumps(result))
        return 1


def register_cli(subparsers):
    parser = subparsers.add_parser(
        "novelty", parents=[build_parser("cpscore novelty")], add_help=False,
        help="retrieve and inspect novelty evidence (A-E (including C+) judgments are made by the skill)")
    parser.set_defaults(func=execute)


def main(argv=None):
    return execute(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
