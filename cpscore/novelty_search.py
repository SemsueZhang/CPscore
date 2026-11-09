#!/usr/bin/env python3
"""Save real CPRet or arXiv candidates and the corresponding search evidence."""

import argparse
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class SearchCardParser(HTMLParser):
    """Read the result cards currently served by the two public websites."""

    def __init__(self, provider, base_url):
        super().__init__(convert_charrefs=True)
        self.provider = provider
        self.base_url = base_url
        self.marker = {"cpret": "result-card", "arxiv": "arxiv-result"}[provider]
        self.fields = {
            "cpret": {"rank": "rank", "result-title": "title",
                      "oj-tag": "source", "score-num": "score"},
            "arxiv": {"title": "title", "authors": "authors",
                      "abstract-full": "summary"},
        }[provider]
        self.current = None
        self.member = None
        self.members = []
        self.stack = []
        self.results = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        classes = set(attrs.get("class", "").split())
        if tag == "li" and self.marker in classes:
            if self.current is not None:
                raise ValueError("Overlapping search result cards")
            self.current = {}
            self.member = None
            self.members = []
            self.stack = []
        elif tag == "li" and self.current is not None and self.provider == "cpret":
            if self.member is not None:
                raise ValueError("Unexpected nesting in a CPRet duplicate group")
            self.member = {}
        if self.current is None:
            return
        target = self.member if self.member is not None else self.current
        field = next((value for key, value in self.fields.items() if key in classes), None)
        href = attrs.get("href", "")
        if "result-title" in classes and href:
            target["url"] = urllib.parse.urljoin(self.base_url, href)
        if self.member is not None and "t" in classes:
            if href:
                target["url"] = urllib.parse.urljoin(self.base_url, href)
            field = "title"
        if self.member is not None and "num" in classes:
            field = "score"
        if "meta-link" in classes and "statement_url" not in target:
            target["statement_url"] = urllib.parse.urljoin(self.base_url, href)
        if self.provider == "arxiv":
            if href.startswith("https://arxiv.org/abs/"):
                self.current["url"] = href
            if href.startswith("https://arxiv.org/pdf/"):
                self.current["pdf_url"] = href
            if "abstract-full" in classes:
                self.current["version_id"] = attrs.get("id", "").removesuffix("-abstract-full")
            if tag == "a":
                field = "ignored"
        if tag not in {"br", "hr", "img", "input", "meta", "link", "wbr"}:
            self.stack.append((tag, field))

    def handle_data(self, data):
        if self.current is None:
            return
        active_fields = {field for _, field in self.stack if field}
        if "ignored" in active_fields:
            active_fields.discard("summary")
        active_fields.discard("ignored")
        target = self.member if self.member is not None else self.current
        for field in active_fields:
            target[field] = target.get(field, "") + data

    def handle_endtag(self, tag):
        if tag in {"br", "hr", "img", "input", "meta", "link", "wbr"}:
            return
        if self.current is None:
            return
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Unexpected nesting in search result card")
        self.stack.pop()
        if tag == "li" and self.member is not None:
            member = {key: " ".join(value.split()) for key, value in self.member.items()}
            if not member.get("title") or not member.get("url"):
                raise ValueError("CPRet group member is missing its title or original link")
            if "score" in member:
                member["score"] = float(member["score"])
                if not math.isfinite(member["score"]):
                    raise ValueError("CPRet group member has a non-finite similarity score")
            self.members.append(member)
            self.member = None
        if self.stack:
            return
        result = {key: " ".join(value.split()) for key, value in self.current.items()}
        if not result.get("title") or not result.get("url"):
            raise ValueError("Search result is missing its title or original link")
        if self.provider == "cpret":
            result["rank"] = int(result.get("rank", "").lstrip("#"))
            result["score"] = float(result.get("score", ""))
            if not math.isfinite(result["score"]):
                raise ValueError("CPRet result has a non-finite similarity score")
            if self.members:
                result["group_members"] = self.members
        else:
            result["authors"] = result.get("authors", "").removeprefix("Authors:").strip()
        self.results.append(result)
        self.current = None


def parse_cpret(raw, base_url):
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("html"), str):
        raise ValueError("CPRet response has no result HTML")
    total = payload.get("total")
    if type(total) is not int or total < 0:
        raise ValueError("CPRet response has no valid total")
    parser = SearchCardParser("cpret", base_url)
    parser.feed(payload["html"])
    parser.close()
    if parser.current is not None or (total > 0 and not parser.results):
        raise ValueError("CPRet returned results but their cards could not be read")
    metadata = {key: payload.get(key) for key in
                ("total", "page", "max_page", "query_token_count", "elapsed", "params")}
    return parser.results, metadata


def parse_arxiv_web(raw):
    parser = SearchCardParser("arxiv", "https://arxiv.org")
    parser.feed(raw)
    parser.close()
    text = " ".join(unescape(re.sub(r"<[^>]*>", " ", raw)).split())
    match = re.search(r"of ([\d,]+) results", text)
    if match:
        total = int(match.group(1).replace(",", ""))
    elif "Sorry, your query" in text and "produced no results" in text:
        total = 0
    else:
        raise ValueError("arXiv page has no recognized search result summary")
    if parser.current is not None or (total > 0 and not parser.results):
        raise ValueError("arXiv returned results but their cards could not be read")
    return parser.results, {"total": total, "page_size": 50}


def parse_arxiv_api(raw):
    root = ET.fromstring(raw)
    atom = "{http://www.w3.org/2005/Atom}"
    opensearch = "{http://a9.com/-/spec/opensearch/1.1/}"
    if root.tag != atom + "feed":
        raise ValueError("arXiv response is not an Atom feed")
    results = []
    for entry in root.findall(atom + "entry"):
        title = " ".join(entry.findtext(atom + "title", "").split())
        identifier = entry.findtext(atom + "id", "")
        summary = " ".join(entry.findtext(atom + "summary", "").split())
        if title == "Error" or "/api/errors" in identifier:
            raise ValueError("arXiv query error: " + summary)
        if not title or "/abs/" not in identifier:
            raise ValueError("arXiv entry is missing its title or article identifier")
        results.append({
            "title": title,
            "url": identifier.replace("http://", "https://", 1),
            "version_id": identifier.split("/abs/", 1)[1],
            "authors": ", ".join(author.findtext(atom + "name", "")
                                 for author in entry.findall(atom + "author")),
            "summary": summary,
            "published": entry.findtext(atom + "published", ""),
            "pdf_url": "https://arxiv.org/pdf/" + identifier.split("/abs/", 1)[1],
        })
    total = int(root.findtext(opensearch + "totalResults", "-1"))
    if total < 0:
        raise ValueError("arXiv feed has no valid totalResults")
    return results, {"total": total, "start": root.findtext(opensearch + "startIndex")}


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_timeout(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def request_url(args, query):
    if args.provider == "cpret":
        base = urllib.parse.urlsplit(args.cpret_url)
        if base.scheme not in {"http", "https"} or not base.netloc or base.query or base.fragment:
            raise ValueError("CPRet base URL must be an absolute HTTP(S) root without query or fragment")
        parameters = {"q": query, "page": args.page, "lang": "en",
                      "dedup": str(int(getattr(args, "dedup", False))), "mmr": "0"}
        return args.cpret_url.rstrip("/") + "/api/search?" + urllib.parse.urlencode(parameters)
    if args.arxiv_interface == "api":
        parameters = {"search_query": query, "start": (args.page - 1) * args.limit,
                      "max_results": args.limit, "sortBy": "relevance"}
        return "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(parameters)
    parameters = {"query": query, "searchtype": "all", "abstracts": "show",
                  "order": "", "size": 50, "start": (args.page - 1) * 50}
    return "https://arxiv.org/search/?" + urllib.parse.urlencode(parameters)


def search(args, query):
    record = {"provider": args.provider, "query": query, "page": args.page,
              "limit": args.limit, "started_at": datetime.now(timezone.utc).isoformat(),
              "status": "error", "complete": False, "candidates": [], "responses": []}
    started = time.monotonic()
    try:
        if args.provider == "arxiv":
            record["interface"] = args.arxiv_interface
            time.sleep(3)
        deadline = time.monotonic() + args.timeout
        page = args.page
        seen = set()
        while True:
            options = argparse.Namespace(**vars(args))
            options.page = page
            url = request_url(options, query)
            record.setdefault("request_url", url)
            response_record = {"page": page, "request_url": url}
            record["responses"].append(response_record)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Search pagination exceeded its total request timeout")
            request = urllib.request.Request(url, headers={"User-Agent": "Auto-Insight-Problem-Review/1.0"})
            with urllib.request.urlopen(request, timeout=remaining) as response:
                raw = response.read().decode(response.headers.get_content_charset() or "utf-8")
                response_record.update(http_status=response.status, response_url=response.url, raw_response=raw)
            if "raw_response" not in record:
                record.update({key: response_record[key] for key in ["http_status", "response_url", "raw_response"]})
            if args.provider == "cpret":
                candidates, metadata = parse_cpret(raw, args.cpret_url)
                if metadata.get("page") is not None and metadata["page"] != page:
                    raise ValueError("CPRet returned a different page than requested")
            elif args.arxiv_interface == "api":
                candidates, metadata = parse_arxiv_api(raw)
            else:
                candidates, metadata = parse_arxiv_web(raw)
            response_record.update(status="ok", retrieved_count=len(candidates), metadata=metadata)
            record.setdefault("metadata", metadata)
            record["retrieved_count"] = record.get("retrieved_count", 0) + len(candidates)
            fresh = [candidate for candidate in candidates if candidate["url"] not in seen]
            if candidates and not fresh:
                raise ValueError("Search pagination repeated an earlier page")
            seen.update(candidate["url"] for candidate in candidates)
            record["candidates"].extend(fresh[:args.limit - len(record["candidates"])])
            if args.provider != "cpret" or len(record["candidates"]) >= args.limit:
                break
            if not candidates or page >= (metadata.get("max_page") or page):
                break
            page += 1
        record.update(status="ok", complete=True)
    except (OSError, ValueError, ET.ParseError) as error:
        record["status"] = "partial" if record["candidates"] else "error"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        if record["responses"]:
            record["responses"][-1].update(status="error", error=record["error"])
        if isinstance(error, urllib.error.HTTPError):
            record["http_status"] = error.code
            error.close()
    record["retained_count"] = len(record["candidates"])
    record["fetched_pages"] = [response["page"] for response in record["responses"]
                               if response.get("status") == "ok"]
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return record


def statement_quality(text):
    """Flag recognizable publishing placeholders separately from HTTP success."""
    normalized = " ".join(text.lower().split())
    markers = [phrase for phrase in ["example problem statement in markdown",
               "remove everything here before publishing your problem"] if phrase in normalized]
    return {"status": "suspect" if markers else "unchecked", "placeholder_markers": markers}


def candidate_view(candidate):
    result = dict(candidate)
    url = result.get("statement_url")
    if url:
        parts = urllib.parse.urlsplit(url)
        if re.search(r"/p/\d+/?$", parts.path):
            parameters = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query)
                          if key not in {"q", "page"}]
            result["statement_url"] = urllib.parse.urlunsplit(
                parts._replace(query=urllib.parse.urlencode(parameters)))
    if "group_members" in result:
        result["group_members"] = [candidate_view(member) for member in result["group_members"]]
    return result


def model_view(record):
    """Keep candidates and status while omitting raw pages and repeated mirror queries."""
    result = {key: value for key, value in record.items() if key not in {"raw_response", "responses"}}
    if record.get("provider") == "cpret":
        result["candidates"] = [candidate_view(candidate) for candidate in record.get("candidates", [])]
    return result


def write_record(record, output):
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + output.name, dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["cpret", "arxiv"])
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query")
    query_group.add_argument("--query-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true",
                        help="Print a compact model view and save full evidence when --output is provided")
    parser.add_argument("--page", type=positive_int, default=1)
    parser.add_argument("--limit", type=positive_int,
                        help="Maximum candidates across CPRet pages, default 60 for CPRet and 10 for arXiv")
    parser.add_argument("--dedup", action="store_true", help="Group CPRet duplicates and preserve member links")
    parser.add_argument("--timeout", type=positive_timeout, default=45)
    parser.add_argument("--cpret-url", default="https://www.cpret.online")
    parser.add_argument("--arxiv-interface", choices=["web", "api"], default="web")
    args = parser.parse_args()
    if args.limit is None:
        args.limit = 60 if args.provider == "cpret" else 10
    try:
        query = args.query_file.read_text(encoding="utf-8") if args.query_file else args.query
    except (OSError, UnicodeError) as error:
        parser.error(str(error))
    query = query.strip()
    if not query:
        parser.error("query must contain non-whitespace text")
    record = search(args, query)
    try:
        if args.compact:
            if args.output is not None:
                write_record(record, args.output)
            write_record(model_view(record), None)
        else:
            write_record(record, args.output)
    except OSError as error:
        print("Could not save search evidence: " + str(error), file=sys.stderr)
        return 1
    return 0 if record["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
