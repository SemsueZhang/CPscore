#!/usr/bin/env python3
"""Check review record coverage and source anchors, using only the standard library."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


TASKS = {"content", "reading", "format"}
RESULT_STATES = {"checked", "issue", "uncertain", "not_applicable"}
FINDING_STATES = {"confirmed", "rejected", "uncertain"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def index_rows(rows, label):
    require(isinstance(rows, list), label + " 必须是数组")
    indexed = {}
    for row in rows:
        require(isinstance(row, dict), label + " 条目必须是对象")
        key = row.get("id")
        require(nonempty(key), label + " 缺少 ID")
        require(key not in indexed, label + " 重复 ID: " + key)
        indexed[key] = row
    return indexed


def text_gap(source, ranges):
    """Return the first non-whitespace position outside the supplied ranges."""
    position = 0
    for start, end in sorted(ranges):
        if start > position:
            for offset in range(position, start):
                if not source[offset].isspace():
                    return offset
        position = max(position, end)
    for offset in range(position, len(source)):
        if not source[offset].isspace():
            return offset
    return None


def check_record(record, base, scans):
    require(isinstance(record, dict), "记录必须是 JSON 对象")
    version = record.get("version")
    require(type(version) is int and version in (1, 2), "version 必须为 1 或 2")
    require(type(record.get("format_requested")) is bool, "format_requested 必须显式填写布尔值")
    if version == 2:
        require(type(record.get("reading_requested")) is bool, "reading_requested 必须显式填写布尔值")
    enabled = {"content"}
    if version == 1 or record["reading_requested"]:
        enabled.add("reading")
    if record["format_requested"]:
        enabled.add("format")
    sources = index_rows(record.get("sources"), "sources")
    objects = index_rows(record.get("objects"), "objects")
    findings = index_rows(record.get("findings"), "findings")
    require(bool(sources), "sources 不能为空")
    gaps = []
    if not objects:
        gaps.append("缺少审核对象")
    texts, paths = {}, {}
    for key, source in sources.items():
        require(nonempty(source.get("path")), "来源缺少路径: " + key)
        path = (base / source["path"]).resolve()
        require(path not in paths, "同一源文件重复登记: " + str(path))
        raw = path.read_bytes()
        require(source.get("sha256") == hashlib.sha256(raw).hexdigest(), "源文件摘要不符: " + key)
        texts[key] = raw.decode("utf-8")
        paths[path] = key

    expected = set()
    ranges = {(key, task): [] for key in sources for task in enabled}
    for key, obj in objects.items():
        source_id = obj.get("source")
        require(isinstance(source_id, str) and source_id in sources, "对象引用未知来源: " + key)
        start, end = obj.get("start"), obj.get("end")
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(texts[source_id]),
                "对象范围无效: " + key)
        excerpt = obj.get("excerpt")
        require(nonempty(excerpt) and texts[source_id][start:end].startswith(excerpt), "对象摘录不符: " + key)
        checks = obj.get("checks")
        require(isinstance(checks, list) and bool(checks), "对象缺少检查项: " + key)
        seen = set()
        for check in checks:
            require(nonempty(check) and "." in check, "检查项须有任务前缀: " + key)
            task, detail = check.split(".", 1)
            require(task in TASKS and nonempty(detail), "检查项任务或维度无效: " + check)
            require(task in enabled, "未启用任务却列入检查项: " + check)
            require(check not in seen, "重复检查项: " + key + "/" + check)
            seen.add(check)
            expected.add((key, check))
            ranges[source_id, task].append((start, end))

    for key, finding in findings.items():
        require(finding.get("status") in FINDING_STATES, "候选状态无效: " + key)
        require(nonempty(finding.get("basis")), "候选缺少核实依据: " + key)
        refs = finding.get("objects")
        require(isinstance(refs, list) and bool(refs), "候选缺少原文对象: " + key)
        require(all(isinstance(ref, str) and ref in objects for ref in refs), "候选引用未知对象: " + key)
        if finding["status"] == "uncertain":
            gaps.append("候选尚未核实: " + key)

    results = record.get("results")
    require(isinstance(results, list), "results 必须是数组")
    actual, linked = {}, set()
    for result in results:
        require(isinstance(result, dict), "结果必须是对象")
        object_id, check = result.get("object"), result.get("check")
        require(nonempty(object_id) and nonempty(check), "结果缺少对象或检查项")
        pair = (object_id, check)
        require(pair in expected, "结果引用未知对象或检查项: " + object_id + "/" + check)
        require(pair not in actual, "重复审核结果: " + object_id + "/" + check)
        state = result.get("status")
        require(state in RESULT_STATES, "结果状态无效: " + object_id + "/" + check)
        require(nonempty(result.get("basis")), "结果缺少依据: " + object_id + "/" + check)
        refs = result.get("findings")
        require(isinstance(refs, list), "结果 findings 必须是数组")
        require(all(isinstance(ref, str) and ref in findings for ref in refs), "结果引用未知候选")
        require(all(object_id in findings[ref]["objects"] for ref in refs), "结果与候选的原文对象不符")
        linked.update(refs)
        if state == "issue":
            require(any(findings[ref]["status"] == "confirmed" for ref in refs), "问题结果须关联已确认发现")
        elif any(findings[ref]["status"] == "confirmed" for ref in refs):
            raise ValueError("已确认发现须对应 issue 结果: " + object_id + "/" + check)
        if state == "uncertain":
            gaps.append("检查项未确定: " + object_id + "/" + check)
        actual[pair] = result

    for object_id, check in sorted(expected - actual.keys()):
        gaps.append("缺少结果: " + object_id + "/" + check)
    for key in sorted(findings.keys() - linked):
        gaps.append("候选未并入任务结果: " + key)
    for task in sorted(enabled):
        if not any(check.startswith(task + ".") for _, check in actual):
            gaps.append("任务没有结果: " + task)
        for source_id, source in texts.items():
            offset = text_gap(source, ranges[source_id, task])
            if offset is not None:
                gaps.append("原文未建审核对象: {}/{}/{}".format(source_id, task, offset))

    if scans:
        require(record["format_requested"], "未启用格式任务却传入格式扫描")
    for scan_path in scans:
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
        require(isinstance(scan, dict) and scan.get("schema_version") == 2, "格式扫描 schema_version 须为 2")
        for error in scan.get("errors", []):
            gaps.append("格式扫描未完成: " + str(error.get("message", error)))
        for source in scan.get("files", []):
            path = Path(source["file"]).resolve()
            require(path in paths, "扫描文件不在审核来源中: " + str(path))
            require(source["sha256"] == sources[paths[path]]["sha256"], "格式扫描摘要已过期")
        for candidate in scan.get("review_candidates", []):
            path = Path(candidate["file"]).resolve()
            require(path in paths, "格式候选引用未知来源")
            source_id = paths[path]
            require(candidate["sha256"] == sources[source_id]["sha256"], "格式候选摘要已过期")
            check = "format." + candidate["candidate_id"]
            matches = [obj for (obj, item) in actual if item == check]
            if not matches:
                gaps.append("格式候选未处理: " + candidate["candidate_id"])
            for object_id in matches:
                obj = objects[object_id]
                require(obj["source"] == source_id and obj["start"] < candidate["end_offset"]
                        and obj["end"] > candidate["offset"], "格式候选与审核对象位置不符")
        for finding in scan.get("effective_findings", scan.get("findings", [])):
            if finding.get("type") == "Warning":
                gaps.append("格式扫描仍有未裁定候选: " + str(finding.get("offset")))
            elif finding.get("type") == "Confirmed":
                source_id = paths[Path(finding["file"]).resolve()]
                included = any(
                    check.startswith("format.") and result["status"] == "issue"
                    and objects[obj]["source"] == source_id
                    and objects[obj]["start"] < finding["end_offset"]
                    and objects[obj]["end"] > finding["offset"]
                    for (obj, check), result in actual.items()
                )
                if not included:
                    gaps.append("已确认格式发现未纳入任务结果: " + str(finding.get("offset")))
        for scope in scan.get("effective_skipped", scan.get("skipped", [])):
            if scope.get("unverified", True):
                gaps.append("格式扫描仍有未核验范围: " + str(scope.get("offset")))

    return {"status": "incomplete" if gaps else "records_complete", "enabled_tasks": sorted(enabled),
            "format": "requested" if record["format_requested"] else "not_requested",
            "objects": len(objects), "results": len(actual), "gaps": gaps,
            "scope": "仅验证执行记录与来源绑定，语义正确性及重要对象完整性由审核者核验"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--format-scan", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        result = check_record(record, args.record.resolve().parent, args.format_scan)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as error:
        result = {"status": "invalid", "error": str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"records_complete": 0, "incomplete": 1, "invalid": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
