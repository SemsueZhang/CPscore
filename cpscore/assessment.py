"""Evidence-backed problem/contest aggregation and performance report rendering.

Agents supply analysis; tools recompute component scores and enforce the minimum.
These reports deliberately do not change the correctness scoring protocol.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from .schema import loads_json
from .scoring import score_report

TIERS = ("不合格", "合格", "推荐")
SCORE_TIERS = {"unacceptable": TIERS[0], "acceptable": TIERS[1], "excellent": TIERS[2], "undetermined": None}
NOVELTY_TIERS = {"A": TIERS[0], "B": TIERS[0], "C": TIERS[1], "D": TIERS[1], "C+": TIERS[2], "F": TIERS[2]}
DESIGN = {"solution_space": "解法空间", "subtasks": "部分分设计", "full_score": "满分做法与限制", "coherence": "条件自然性与观察价值"}
CONTEST = {"requirements_fit": "比赛要求适配", "difficulty_progression": "难度梯度", "topic_balance": "考点分布", "time_budget": "时间安排", "score_distribution": "分值与部分分", "differentiation": "区分效果", "fairness": "竞赛公平性"}
REQUIREMENTS = ("audience", "format", "duration_minutes", "problem_count", "scoring", "goals", "constraints")


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: 需要非空文字")
    return value


def _obj(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: 需要对象")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{where}: 需要数组")
    return value


def _texts(value: Any, where: str, *, nonempty: bool = False) -> list[str]:
    values = _list(value, where)
    if nonempty and not values:
        raise ValueError(f"{where}: 需要至少一项")
    return [_text(item, where) for item in values]


def _number(value: Any, where: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{where}: 需要{'正' if positive else '非负'}有限数值")
    return value


def _load(base: Path, relative: Any) -> tuple[Path, Any]:
    path = (base / _text(relative, "报告路径")).resolve()
    return path, loads_json(path.read_text(encoding="utf-8"))


def _component(name: str, verdict: str | None, reason: str, *, evidence=(), edits=(), complete: bool = True) -> dict:
    return {"name": name, "verdict": verdict, "completion": "complete" if complete and verdict is not None else "incomplete", "reason": reason, "evidence": list(evidence), "edits": list(edits)}


def _judgment(value: Any, name: str) -> dict:
    value = _obj(value, name)
    verdict = value.get("verdict")
    if verdict is not None and verdict not in TIERS:
        raise ValueError(f"{name}: verdict 只能为推荐、合格、不合格或 null")
    if verdict is None:
        return _component(name, None, value.get("reason") or "尚未完成审查")
    reason = _text(value.get("reason"), f"{name}.reason")
    evidence = _texts(value.get("evidence"), f"{name}.evidence", nonempty=True)
    edits = _texts(value.get("edits"), f"{name}.edits", nonempty=verdict != "推荐")
    return _component(name, verdict, reason, evidence=evidence, edits=edits)


def _finish(kind: str, title: str, components: list[dict], **extra) -> dict:
    known = [item["verdict"] for item in components if item["verdict"] is not None]
    complete = all(item["completion"] == "complete" for item in components)
    verdict = min(known, key=TIERS.index) if complete or "不合格" in known else None
    edits = list(dict.fromkeys(edit for item in components for edit in item["edits"]))
    return {"kind": kind, "title": title, "verdict": verdict, "completion": "complete" if complete else "incomplete", "components": components, "edits": edits, **extra}


def make_assessment(kind: str) -> dict:
    def pending():
        return {"verdict": None, "reason": None, "evidence": [], "edits": []}
    common = {"schema_version": "1.0", "kind": kind, "title": "待填写标题"}
    if kind == "problem":
        return {**common, "reviews": [], "novelty": [], "design_reviews": [{"id": "design-1", "dimensions": {key: pending() for key in DESIGN}, "original_method": {"suitable": None, "reason": None, "simpler_alternative": None}}]}
    if kind == "contest":
        return {**common, "requirements": {key: None for key in REQUIREMENTS}, "problems": [], "assessments": {key: {**pending(), "requirement_refs": []} for key in CONTEST}}
    if kind == "performance":
        return {**common, "context": {"audience": None, "format": None, "duration_minutes": None}, "problems": [], "cohorts": [], "assumptions": []}
    raise ValueError(f"未知评定类型: {kind}")


def _problem(record: dict, base: Path) -> dict:
    components, seen, versions = [], set(), {}
    for relative in _list(record.get("reviews"), "reviews"):
        path, raw = _load(base, relative)
        raw = _obj(raw, str(path))
        # Recompute even when a scored report is supplied. Never trust stored tiers.
        scored = score_report(raw.get("review", raw))
        source = scored["review"]
        for name in source["scope"]:
            version = source["objects"][name]["artifact_version"]
            if name in versions and versions[name] != version:
                raise ValueError(f"{name}: 多份审查指向不同材料版本，需统一后重新核验")
            versions[name] = version
            seen.add(name)
            assessment = scored["objects"][name]
            findings = [item for item in source["objects"][name]["findings"] if item["status"] in ("confirmed", "suspected")]
            reason = f"{assessment['score']}/10；{assessment['completion']}"
            if findings:
                reason += "；" + "；".join(item["title"] for item in findings)
            edits = [item["repair"]["suggestion"] for item in findings if item["repair"]["suggestion"]]
            if assessment["tier"] in ("unacceptable", "acceptable") and not edits:
                edits = [f"修复并复核 {name} 审查列出的缺陷，详见 {path}"]
            components.append(_component(f"{name} · {source['review_id']} · {path.name}", SCORE_TIERS[assessment["tier"]], reason, evidence=[str(path)], edits=edits, complete=assessment["completion"] == "complete"))
    for name in ("statement", "solution", "editorial", "data"):
        if name not in seen:
            components.append(_component(name, None, "缺少当前版本的审查报告"))
    novelty = _list(record.get("novelty"), "novelty")
    for index, item in enumerate(novelty):
        item = _obj(item, "novelty")
        grade = _text(item.get("grade"), "novelty.grade").upper()
        if grade not in NOVELTY_TIERS:
            raise ValueError("新颖度等级只能为 A/B/C/C+/D/F")
        path = (base / _text(item.get("report"), "novelty.report")).resolve()
        _text(path.read_text(encoding="utf-8"), "新颖度报告")
        edits = _texts(item.get("edits", []), "novelty.edits", nonempty=grade in ("A", "B"))
        components.append(_component(f"新颖度 · {index + 1}", NOVELTY_TIERS[grade], f"{grade}：{_text(item.get('reason'), 'novelty.reason')}", evidence=[str(path)], edits=edits))
    if not novelty:
        components.append(_component("新颖度", None, "缺少新颖度审查报告与等级"))
    designs = _list(record.get("design_reviews"), "design_reviews")
    ids = set()
    for design in designs:
        design = _obj(design, "design_reviews")
        name = _text(design.get("id"), "design.id")
        if name in ids:
            raise ValueError("design.id 重复")
        ids.add(name)
        dimensions = _obj(design.get("dimensions"), "design.dimensions")
        for key, label in DESIGN.items():
            components.append(_judgment(dimensions.get(key, {}), f"{name} · {label}"))
        method = _obj(design.get("original_method"), "original_method")
        suitable = method.get("suitable")
        if suitable is None:
            components.append(_component(f"{name} · 原做法适合度", None, "尚未核验竞赛适合度"))
            continue
        if type(suitable) is not bool:
            raise ValueError("original_method.suitable 需要布尔值或 null")
        reason = _text(method.get("reason"), "original_method.reason")
        if suitable:
            components.append(_component(f"{name} · 原做法适合度", "推荐", reason))
            continue
        alternative = method.get("simpler_alternative")
        if alternative is not None:
            alternative = _obj(alternative, "simpler_alternative")
            if type(alternative.get("verified")) is not bool:
                raise ValueError("simpler_alternative.verified 需要布尔值")
        if alternative and alternative["verified"]:
            details = [_text(alternative.get(key), f"simpler_alternative.{key}") for key in ("description", "correctness", "complexity", "suitability")]
            evidence = _texts(alternative.get("evidence"), "simpler_alternative.evidence", nonempty=True)
            components.append(_component(f"{name} · 原做法适合度", "合格", reason + "；已核验更简单且适合竞赛的替代做法：" + "；".join(details), evidence=evidence, edits=["采用已核验的更简单做法，更新题解、参考程序、约束和相关材料后重新审查。此例外不提升其他审查结果。"]))
        else:
            components.append(_component(f"{name} · 原做法适合度", "不合格", reason + "；尚无已核验的更简单且适合竞赛的替代做法", edits=["调整题目设计或给出经核验的更简单竞赛做法。"]))
    if not designs:
        components.append(_component("整体设计", None, "缺少整体设计与解法空间审查"))
    return _finish("problem", record["title"], components, artifact_versions=versions)


def _requirements(value: Any) -> tuple[dict, list[str]]:
    value = _obj(value, "requirements")
    missing = [key for key in REQUIREMENTS if value.get(key) is None]
    for key in REQUIREMENTS:
        if key in missing:
            continue
        if key in ("duration_minutes", "problem_count"):
            _number(value[key], f"requirements.{key}", positive=True)
            if key == "problem_count" and type(value[key]) is not int:
                raise ValueError("requirements.problem_count 需要正整数")
        elif key in ("goals", "constraints"):
            _texts(value[key], f"requirements.{key}", nonempty=key == "goals")
        else:
            _text(value[key], f"requirements.{key}")
    return value, missing


def _contest(record: dict, base: Path) -> dict:
    requirements, missing = _requirements(record.get("requirements"))
    components = []
    if missing:
        components.append(_component("比赛要求", None, "尚未提供：" + "、".join(missing)))
    problems = _list(record.get("problems"), "problems")
    ids = set()
    for problem in problems:
        problem = _obj(problem, "problem")
        name = _text(problem.get("id"), "problem.id")
        if name in ids:
            raise ValueError("比赛中 problem.id 重复")
        ids.add(name)
        points = _number(problem.get("points"), "problem.points", positive=True)
        path, source = _load(base, problem.get("review"))
        if _obj(source, str(path)).get("kind") != "problem":
            raise ValueError("比赛的逐题来源必须为 problem 输入记录")
        result = assess(source, base=path.parent)
        components.append(_component(f"题目 {name}（{points:g} 分）", result["verdict"], f"{result['title']}；{result['completion']}；逐题取最低档", evidence=[str(path)], edits=[f"{name}：{edit}" for edit in result["edits"]], complete=result["completion"] == "complete"))
    if not problems:
        components.append(_component("题目组合", None, "尚未提供题目"))
    if "problem_count" not in missing and problems and len(problems) != requirements["problem_count"]:
        components.append(_component("题目数量", "不合格", f"要求 {requirements['problem_count']} 题，实际 {len(problems)} 题", edits=["按比赛要求调整题目数量。"]))
    judgments = _obj(record.get("assessments"), "assessments")
    for key, label in CONTEST.items():
        raw = judgments.get(key, {})
        item = _judgment(raw, label)
        if item["verdict"] is not None:
            refs = _texts(raw.get("requirement_refs"), f"{key}.requirement_refs", nonempty=True)
            if any(ref not in REQUIREMENTS for ref in refs):
                raise ValueError(f"{key}: 未知的比赛要求引用")
            if missing or any(ref in missing for ref in refs):
                item = _component(label, None, "比赛要求未齐，需结合完整要求重新评定")
        components.append(item)
    return _finish("contest", record["title"], components, requirements=deepcopy(requirements))


def _range(value: Any, name: str, maximum: float) -> list:
    value = _list(value, name)
    if len(value) != 2:
        raise ValueError(f"{name}: 需要 [下界, 上界]")
    lo, hi = (_number(item, name) for item in value)
    if not lo <= hi <= maximum:
        raise ValueError(f"{name}: 需要 0 ≤ 下界 ≤ 上界 ≤ {maximum}")
    return [lo, hi]


def _performance(record: dict) -> dict:
    context = _obj(record.get("context"), "context")
    for key in ("audience", "format"):
        _text(context.get(key), f"context.{key}")
    duration = _number(context.get("duration_minutes"), "context.duration_minutes", positive=True)
    problems = _list(record.get("problems"), "problems")
    maxima = {}
    for problem in problems:
        problem = _obj(problem, "problem")
        name = _text(problem.get("id"), "problem.id")
        if name in maxima:
            raise ValueError("problem.id 重复")
        _text(problem.get("title"), "problem.title")
        maxima[name] = _number(problem.get("max_score"), "problem.max_score", positive=True)
    cohorts = _list(record.get("cohorts"), "cohorts")
    if not problems or not cohorts:
        raise ValueError("预测报告需要题目和至少一类目标选手")
    names = set()
    for cohort in cohorts:
        cohort = _obj(cohort, "cohort")
        name = _text(cohort.get("name"), "cohort.name")
        if name in names:
            raise ValueError("cohort.name 重复")
        names.add(name)
        for key in ("profile", "strategy"):
            _text(cohort.get(key), f"cohort.{key}")
        seen, minimum_time = set(), 0
        for prediction in _list(cohort.get("predictions"), "predictions"):
            prediction = _obj(prediction, "prediction")
            name = _text(prediction.get("problem_id"), "prediction.problem_id")
            if name not in maxima or name in seen:
                raise ValueError("预测中存在未知或重复的题目")
            seen.add(name)
            _range(prediction.get("score_range"), "score_range", maxima[name])
            lo, _ = _range(prediction.get("time_range_minutes"), "time_range_minutes", duration)
            minimum_time += lo
            for key in ("route", "bottlenecks", "basis"):
                _text(prediction.get(key), f"prediction.{key}")
            if prediction.get("confidence") not in ("low", "medium", "high"):
                raise ValueError("confidence 需要 low/medium/high")
        if seen != set(maxima):
            raise ValueError("每类选手需覆盖所有题目，可用零分和零投入表示放弃")
        if minimum_time > duration:
            raise ValueError("各题预计投入时间下界之和超过比赛总时长")
    _texts(record.get("assumptions"), "assumptions", nonempty=True)
    return deepcopy(record)


def assess(record: Any, *, base: Path | str = ".") -> dict:
    record = _obj(record, "assessment")
    if record.get("schema_version") != "1.0":
        raise ValueError("assessment.schema_version 需要 1.0")
    _text(record.get("title"), "title")
    kind = record.get("kind")
    if kind == "performance":
        return _performance(record)
    if kind not in ("problem", "contest"):
        raise ValueError("kind 需要 problem/contest/performance")
    return (_problem if kind == "problem" else _contest)(record, Path(base))


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_assessment(result: dict) -> str:
    if result["kind"] == "performance":
        return _render_performance(result)
    lines = [f"# {result['title']}", "", f"结论：**{result['verdict'] or '评定未完成'}**", "", f"覆盖状态：{result['completion']}。按所有审查结果取最低档，未完成项不产生合格或推荐结论。", ""]
    if result["kind"] == "contest":
        lines += ["## 具体比赛要求", ""]
        for key, value in result["requirements"].items():
            lines.append(f"- {key}：{value if value is not None else '待提供'}")
        lines.append("")
    lines += ["## 分项评定", "", "| 审查项 | 结论 | 覆盖 | 理由 |", "| --- | --- | --- | --- |"]
    for item in result["components"]:
        lines.append(f"| {_cell(item['name'])} | {item['verdict'] or '未完成'} | {item['completion']} | {_cell(item['reason'])} |")
    lines += ["", "## 修改意见", ""]
    lines += [f"- {edit}" for edit in result["edits"]] or ["本轮未发现必须修改的事项。" if result["completion"] == "complete" else "先完成上述未完成项，再形成完整修改意见。"]
    lines += ["", "## 依据", ""]
    for item in result["components"]:
        if item["evidence"]:
            lines.append(f"- {item['name']}：" + "；".join(item["evidence"]))
    return "\n".join(lines) + "\n"


def _render_performance(record: dict) -> str:
    context = record["context"]
    lines = [f"# {record['title']}", "", "本文为基于材料的选手表现预测，未进行盲测，不代表实际比赛成绩。", "", f"目标选手：{context['audience']}。赛制：{context['format']}。比赛时长：{context['duration_minutes']} 分钟。", "", "## 预测假设", "", *[f"- {item}" for item in record["assumptions"]]]
    for cohort in record["cohorts"]:
        lines += ["", f"## {cohort['name']}", "", cohort["profile"], "", f"比赛策略：{cohort['strategy']}", "", "| 题目 | 预计得分 | 投入时间（分钟） | 置信度 |", "| --- | --- | --- | --- |"]
        totals = [0, 0]
        for item in cohort["predictions"]:
            lo, hi = item["score_range"]
            totals[0] += lo
            totals[1] += hi
            time_lo, time_hi = item["time_range_minutes"]
            lines.append(f"| {_cell(item['problem_id'])} | {lo:g}～{hi:g} | {time_lo:g}～{time_hi:g} | {item['confidence']} |")
        lines += ["", f"逐题得分区间合计：{totals[0]:g}～{totals[1]:g}。区间上界未必能同时达到，需结合总时长和上述策略理解。"]
        for item in cohort["predictions"]:
            lines += ["", f"### {item['problem_id']}", "", f"预计路线：{item['route']}", "", f"主要障碍：{item['bottlenecks']}", "", f"预测依据：{item['basis']}"]
    return "\n".join(lines) + "\n"


def _command(args) -> int:
    from .cli import _read, _write
    if args.action == "init":
        result = make_assessment(args.kind)
        _write(json.dumps(result, ensure_ascii=False, indent=2) + "\n", args.output)
    else:
        base = Path(args.base_dir) if args.base_dir else (Path(args.record).resolve().parent if args.record != "-" else Path.cwd())
        result = assess(_read(args.record), base=base)
        _write(json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_assessment(result), args.output)
    return 0


def register_cli(subparsers) -> None:
    parser = subparsers.add_parser("assess", help="problem/contest minimum-tier assessment and performance reports")
    actions = parser.add_subparsers(dest="action", required=True)
    init = actions.add_parser("init", help="create an unreviewed input record")
    init.add_argument("kind", choices=("problem", "contest", "performance"))
    init.add_argument("--output", "-o", default="-")
    init.set_defaults(func=_command)
    report = actions.add_parser("report", help="recompute source reviews and render a Markdown report")
    report.add_argument("record")
    report.add_argument("--base-dir", help="resolve referenced files here; default: record's directory")
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")
    report.add_argument("--output", "-o", default="-")
    report.set_defaults(func=_command)
