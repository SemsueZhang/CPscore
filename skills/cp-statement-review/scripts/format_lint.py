#!/usr/bin/env python3
"""CPScore source-format checker and format-only scoring, Python 3.8+ stdlib.

Static rules find deterministic violations. Optional evidence-bound LLM decisions
resolve uncertain ranges; this script owns deduplication and format-only scoring.
It neither calls models nor edits sources or computes the complete material score.
"""


import argparse
import bisect
import hashlib
import html
import json
import re
import string
import sys
import unicodedata
from pathlib import Path


VERSION = 2
LINTER_VERSION = "2.3.1"
RENDER_MODEL = "commonmark-softbreak-whitespace"
CJK = r"\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003ffff"
HAN = "[" + CJK + "]"
LATIN = r"[A-Za-z0-9]"
PUNCT = "，。！？；：、"
OPEN_PUNCT = "“‘（《〈【〔「『"
CLOSE_PUNCT = "”’）》〉】〕」』"
CATEGORIES = {
    "missing_space": "缺少边界空格",
    "extra_space": "多余空格",
    "width": "全半角字符",
    "punctuation": "中文标点",
    "sentence_end": "句末标点",
    "soft_break": "单换行与段落",
    "heading": "标题用法",
    "list": "列表用法",
    "code_fence": "代码定界",
    "container": "扩展容器与折叠块",
    "code_usage": "代码样式用途",
    "long_code": "长代码折叠",
    "link": "链接语法",
    "image_link": "图片附加跳转",
    "image_host": "图片托管",
    "emphasis": "强调样式",
    "missing_math": "缺少数学环境",
    "extra_math": "多余数学环境",
    "math_fragment": "同一公式被拆分",
    "math_delimiter": "数学定界与闭合",
    "math_text": "公式说明文本",
    "math_punctuation": "公式内标点",
    "math_language": "数学语言与运算符",
    "math_function": "函数名正体",
    "math_ellipsis": "数学省略号",
    "complexity_constant": "复杂度固定因子",
    "math_chain": "连等式环境",
    "math_script": "上下标分组",
    "math_number": "大数字表示",
    "math_display": "独立公式环境",
    "math_support": "数学命令支持",
    "math_arguments": "数学命令参数",
    "document_layout": "材料展示约定",
    "coverage": "未完成的格式核验",
}
RULES = {
    "TXT001": ("missing_space", "中文与英文、数字之间留半角空格"),
    "TXT002": ("punctuation", "中文叙述使用全角中文标点"),
    "TXT003": ("extra_space", "中文标点旁不加空格，边界间隔不重复"),
    "TXT004": ("width", "区分意外全角字符与刻意展示"),
    "TXT005": ("sentence_end", "完整正文语句应有句末标点"),
    "TXT006": ("soft_break", "段内单换行不能在中文标点旁生成多余空格"),
    "MD001": ("heading", "使用一至四级非空标题"),
    "MD002": ("code_fence", "代码围栏应闭合"),
    "MD003": ("list", "列表标记后留空格，有序标记使用数字加点"),
    "MD004": ("code_fence", "行内代码定界需要匹配"),
    "MD005": ("heading", "标题应组织章节，不承载连续正文步骤"),
    "MD006": ("list", "列表正文与代码需要正确归属和缩进"),
    "MD007": ("code_usage", "代码样式用于程序片段或字符串"),
    "MD008": ("link", "使用相应 Markdown 链接语法"),
    "MD009": ("image_link", "图片不额外包裹无关跳转链接"),
    "MD010": ("image_host", "配图托管应符合适用发布平台的要求"),
    "MD011": ("long_code", "过长代码应折叠，长度线索不等于已证实违规"),
    "MD012": ("emphasis", "强调样式不能代替可读的正文"),
    "MD013": ("container", "扩展容器的语法与开闭范围需要验证"),
    "MD014": ("emphasis", "候选强调标记应按 Markdown 定界规则显示"),
    "MATH001": ("missing_space", "中文与行内公式之间留半角空格"),
    "MATH002": ("math_delimiter", "数学环境定界应匹配"),
    "MATH003": ("missing_math", "数学运算式应使用数学环境"),
    "MATH004": ("extra_math", "普通叙述或算法名不应误入数学环境"),
    "MATH005": ("math_fragment", "同一运算式应放在同一数学环境中"),
    "TEX001": ("math_delimiter", "begin/end 环境应匹配"),
    "TEX002": ("math_delimiter", "数学分组花括号应匹配"),
    "TEX003": ("math_support", "疑似拼错的数学命令需要核实"),
    "TEX004": ("math_function", "约定函数名使用正体数学命令"),
    "TEX005": ("math_text", "公式内的说明文本使用文本命令"),
    "TEX006": ("math_punctuation", "公式内区分数学标点与中文叙述标点"),
    "TEX007": ("math_language", "数学表达式不直接照搬程序语法"),
    "TEX008": ("math_ellipsis", "数学省略号使用相应数学命令"),
    "TEX009": ("complexity_constant", "大 O 中省去固定乘法因子"),
    "TEX010": ("math_chain", "连等推导使用 aligned 等对齐环境"),
    "TEX011": ("math_script", "上下标的作用范围应明确"),
    "TEX012": ("math_number", "大数字的表示需符合适用协议"),
    "TEX013": ("math_support", "自定义或未支持的命令不能假定可渲染"),
    "TEX014": ("math_display", "独立成行的公式使用行间环境"),
    "TEX015": ("math_arguments", "数学命令及环境应提供必要参数"),
    "DOC001": ("document_layout", "按材料用途核对题名、输入输出、范围与子任务等展示约定；由 LLM 提交有证据的补充发现"),
    "LLM001": ("coverage", "LLM 对静态检查无法确定的格式提供有来源位置的补充核验"),
}
ENVIRONMENTS = set("aligned alignedat align align* alignat alignat* gather gathered cases matrix pmatrix bmatrix Bmatrix vmatrix Vmatrix smallmatrix array equation equation* split".split())
# Names checked against the KaTeX support table, 2026-11-14.
TEX_COMMANDS = set("""
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi varpi rho varrho sigma varsigma
tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega sum prod coprod bigcup
bigcap cup cap setminus in notin ni subset supset subseteq supseteq emptyset varnothing forall exists nexists neg land lor lnot implies iff
to gets leftarrow rightarrow Leftarrow Rightarrow leftrightarrow Leftrightarrow mapsto le leq ge geq ne neq lt gt mid nmid parallel nparallel equiv
approx sim simeq cong propto pm mp times cdot div ast circ bullet oplus otimes odot bmod pmod mod frac dfrac tfrac
binom dbinom tbinom sqrt overline underline vec hat widehat bar tilde widetilde dot ddot mathrm mathit mathbf mathbb mathcal mathsf mathtt mathnormal
boldsymbol bm operatorname mathop mathrel mathord text texttt textrm textsf textnormal phantom vphantom hphantom color textcolor boxed cancel not limits nolimits underbrace
overbrace overset underset stackrel substack displaystyle textstyle scriptstyle scriptscriptstyle begin end left right middle big Big bigg Bigg bigl bigr Bigl Bigr
biggl biggr Biggl Biggr lbrace rbrace lbrack rbrack langle rangle lvert rvert lVert rVert vert Vert lfloor rfloor lceil rceil dots cdots
ldots vdots ddots infty partial nabla ell hbar Re Im prime angle triangle complement top bot perp degree log ln lg max
min gcd det sin cos tan cot sec csc arcsin arccos arctan exp lim limsup liminf sup inf arg deg dim ker
hom Pr choose atop brace brack cr hline arraystretch newcommand renewcommand providecommand def gdef edef let verb quad qquad enspace thinspace medspace
thickspace negthinspace allowbreak space smallint int iint iiint oint backslash
""".split())
TEX_ARGUMENTS = {name: 1 for name in "sqrt overline underline vec hat widehat bar tilde widetilde dot ddot mathrm mathit mathbf mathbb mathcal mathsf mathtt mathnormal boldsymbol bm operatorname mathop mathrel mathord text texttt textrm textsf textnormal phantom vphantom hphantom boxed cancel not underbrace overbrace substack pmod".split()}
TEX_ARGUMENTS.update({name: 2 for name in "frac dfrac tfrac binom dbinom tbinom overset underset stackrel textcolor".split()})
TEX_ARGUMENTS["color"] = 1
DELIMITER_COMMANDS = set("left right middle big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr Biggl Biggr".split())
DELIMITER_SYMBOLS = set("lbrace rbrace lbrack rbrack langle rangle lvert rvert lVert rVert vert Vert lfloor rfloor lceil rceil backslash".split())
TEXT_COMMANDS = {"text", "texttt", "textrm", "textsf", "textnormal"}
FACE_COMMANDS = TEXT_COMMANDS | {"operatorname", "mathrm", "mathop", "mathtt", "verb"}
FUNCTION_NAMES = set("log ln lg max min gcd lcm det sin cos tan cot exp lim ans sum size sgn".split())
MATH_TOKEN, CODE_TOKEN, OTHER_TOKEN = "\ue000", "\ue001", "\ue002"
NON_SPACE = re.compile(r"\S")
NEWLINE = r"(?:\r\n|\r(?!\n)|(?<!\r)\n)"
BLANK_PARAGRAPH = re.compile(NEWLINE + r"[ \t]*" + NEWLINE)
CHAR_REFERENCE = re.compile(r"&(?:\#[^&;\s<>]*|[A-Za-z][A-Za-z0-9]*);")
BARE_MATH_PATTERNS = (
    r"(?<![A-Za-z0-9_])(?:[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9{}]+)",
    r"[\U0001d400-\U0001d7ff∑∏≤≥≠∈∪∩]+",
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_()]+\s*(?:≤|≥|!=|<=|>=|=|×|÷|\^|\+|\*)\s*[A-Za-z0-9_()]+)(?:\s*(?:≤|≥|=|×|÷|\+|\*)\s*[A-Za-z0-9_()]+)*",
)


def merged_ranges(spans):
    result = []
    for start, end in sorted(spans, key=lambda x: (x[0], -x[1])):
        if result and start < result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def bare_math_kind(expression):
    # A multi-letter snake_case name can be prose, an identifier or a formula.
    # Its spelling alone cannot establish missing math mode.
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]+_[A-Za-z0-9{}]+", expression):
        return "Warning"
    return "Confirmed"


def escaped(source, pos):
    start = pos
    while start and source[start - 1] == "\\":
        start -= 1
    return (pos - start) % 2 == 1


def source_lines(text, keepends=False):
    """Markdown lines end at LF/CRLF/CR, not every Unicode line separator."""
    if not text:
        return []
    lines = re.split(r"(?<=\n)|(?<=\r)(?!\n)", text)
    if lines[-1] == "":
        lines.pop()
    return lines if keepends else [line.rstrip("\r\n") for line in lines]


def paragraph_end(text, start):
    match = BLANK_PARAGRAPH.search(text, start)
    return match.start() if match else len(text)


def balanced_end(text, start, opening="(", closing=")"):
    depth, quote = 0, None
    for i in range(start, len(text)):
        char = text[i]
        if char in "\r\n\0":
            return None
        if escaped(text, i):
            continue
        if quote:
            if char == quote:
                quote = None
        elif opening == "(" and char in "\"'" and (i == start or text[i - 1].isspace()):
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def delimiter_flanking(text, pos, size):
    def whitespace(char):
        return not char or char in "\t\n\f\r" or unicodedata.category(char) == "Zs"

    def punctuation(char):
        return bool(char) and (char in string.punctuation or unicodedata.category(char).startswith("P"))

    before = text[pos - 1:pos] if pos else ""
    after = text[pos + size:pos + size + 1]
    left = not whitespace(after) and (not punctuation(after) or whitespace(before) or punctuation(before))
    right = not whitespace(before) and (not punctuation(before) or whitespace(after) or punctuation(after))
    if text[pos:pos + 1] == "_":
        return left and (not right or punctuation(before)), right and (not left or punctuation(after))
    return left, right


def link_destination(body):
    """Validate an inline destination and optional title, without network I/O."""
    body = body.strip(" \t")
    if not body:
        return "", True
    if body.startswith("<"):
        close = next((i for i in range(1, len(body)) if body[i] == ">" and not escaped(body, i)), None)
        if close is None or any(c in "\r\n<" for c in body[1:close]):
            return "", False
        destination, suffix = body[1:close], body[close + 1:]
        if suffix and suffix[0] not in " \t":
            return "", False
    else:
        pos, depth = 0, 0
        while pos < len(body):
            char = body[pos]
            if char == "\\" and body[pos + 1:pos + 2] in string.punctuation and pos + 1 < len(body):
                pos += 2
                continue
            if ord(char) <= 32 or ord(char) == 127:
                break
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    return "", False
            pos += 1
        if depth:
            return "", False
        destination, suffix = body[:pos], body[pos:]
    suffix = suffix.strip(" \t")
    if not suffix:
        return destination, True
    opener = suffix[0]
    closer = {"\"": "\"", "'": "'", "(": ")"}.get(opener)
    if closer is None or len(suffix) < 2 or suffix[-1] != closer or escaped(suffix, len(suffix) - 1):
        return "", False
    if opener == "(":
        return destination, balanced_end(suffix, 0) == len(suffix)
    if any(c == closer and not escaped(suffix, i) for i, c in enumerate(suffix[1:-1], 1)):
        return "", False
    return destination, True


def format_assessment(findings, skipped=(), errors=()):
    """Count real source occurrences, by file and canonical format category."""
    groups = {}
    for finding in findings:
        category = finding.get("category", RULES[finding["rule_id"]][0])
        key = (finding["file"], category)
        group = groups.setdefault(key, {"file": key[0], "category": category,
            "name": CATEGORIES[category], "confirmed": {}, "unconfirmed": {}, "rule_ids": set()})
        group["rule_ids"].add(finding["rule_id"])
        # Detectors for the same physical gap/formula share an occurrence key.
        occurrence = finding.get("occurrence_key", "%s:%s" % (finding["line"], finding["column"]))
        target = "confirmed" if finding["type"] == "Confirmed" else "unconfirmed"
        group[target][occurrence] = {"line": finding["line"], "column": finding["column"],
                                     "excerpt": finding["excerpt"]}
    for scope in skipped:
        if not scope.get("unverified", False):
            continue
        category = scope.get("category", "coverage")
        key = (scope["file"], category)
        group = groups.setdefault(key, {"file": key[0], "category": category,
            "name": CATEGORIES[category], "confirmed": {}, "unconfirmed": {}, "rule_ids": set()})
        occurrence = scope.get("occurrence_key", "%s:%s" % (scope["line"], scope["column"]))
        group["unconfirmed"][occurrence] = {
            "line": scope["line"], "column": scope["column"], "excerpt": scope["reason"]}
    for error in errors:
        key = (error.get("file", "<environment>"), "coverage")
        group = groups.setdefault(key, {"file": key[0], "category": "coverage",
            "name": CATEGORIES["coverage"], "confirmed": {}, "unconfirmed": {}, "rule_ids": set()})
        group["unconfirmed"]["input"] = {"line": 1, "column": 1, "excerpt": error["message"]}
    output = []
    for key in sorted(groups):
        group = groups[key]
        for occurrence in group["confirmed"]:
            group["unconfirmed"].pop(occurrence, None)
        count = len(group["confirmed"])
        # Uncertain candidates never fabricate a third confirmed occurrence.
        severity = "Fatal" if count >= 3 else "Major"
        output.append({"file": key[0], "category": key[1], "name": group["name"],
            "confirmed_count": count, "unconfirmed_count": len(group["unconfirmed"]),
            "severity": severity, "deduction": 10 if severity == "Fatal" else 2,
            "basis": "Confirmed" if count else "Unverified",
            "rule_ids": sorted(group["rule_ids"]),
            "occurrences": list(group["confirmed"].values()),
            "unconfirmed_occurrences": list(group["unconfirmed"].values())})
    return {"verdict": "non_compliant" if output else "pass",
            "complete": not errors and not any(g["unconfirmed_count"] for g in output) and not any(s.get("unverified") for s in skipped),
            "groups": output, "format_deduction": sum(g["deduction"] for g in output),
            "policy": "同类格式错误按独立位置计数：1～2 处 Major，至少 3 处 Fatal，同类只扣一次。未确认项不当作已证实次数。"}


def review_candidates(scanned):
    candidates = []
    for kind, values in (("finding", scanned["findings"]), ("scope", scanned["skipped"])):
        for item in values:
            if not (item.get("type") == "Warning" if kind == "finding" else item.get("unverified")):
                continue
            signature = json.dumps([scanned["sha256"], kind, item], ensure_ascii=False, sort_keys=True)
            candidate_id = kind + ":" + hashlib.sha256(signature.encode("utf-8")).hexdigest()
            candidates.append({"candidate_id": candidate_id, "kind": kind, "file": scanned["file"],
                "sha256": scanned["sha256"], "category": item.get("category", "coverage"),
                "offset": item["offset"], "end_offset": item["end_offset"],
                "line": item["line"], "column": item["column"],
                "rule_id": item.get("rule_id"), "reason": item.get("standard", item.get("reason"))})
    return candidates


def apply_format_decisions(scanned, source, record):
    """Validate evidence anchors, then combine LLM decisions with static facts.

    Evidence truth is checked by the reviewing LLM. The script validates source
    identity, exact quotations, candidate identity and occurrence positions. It
    never accepts caller-provided severity, counts or deductions.
    """
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def keys(value, allowed, label):
        require(isinstance(value, dict) and not set(value).difference(allowed), label + " 字段不受支持")

    def explanation(value, label):
        require(isinstance(value, str) and bool(value.strip()), label + " 不能为空")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError(label + " 包含无效的 Unicode 字符")

    def span(value):
        a, b = value.get("offset"), value.get("end_offset")
        require(type(a) is int and type(b) is int and 0 <= a < b <= len(source), "证据位置不在当前源码范围内")
        require(value.get("excerpt") == source[a:b], "证据摘录与当前源码不一致")
        return a, b

    def evidence(value, target):
        require(isinstance(value, list) and bool(value), "LLM 裁定必须提供源码证据")
        ranges = []
        for anchor in value:
            keys(anchor, {"offset", "end_offset", "excerpt"}, "源码证据")
            ranges.append(span(anchor))
        require(any(a < target[1] and b > target[0] for a, b in ranges), "证据必须覆盖相应候选或新增发现")

    keys(record, {"file", "sha256", "decisions", "additional_findings"}, "LLM 文件记录")
    require(hashlib.sha256(source.encode("utf-8")).hexdigest() == scanned["sha256"], "扫描后源码已改变，必须重新扫描")
    require(record.get("file") == scanned["file"], "LLM 文件记录与扫描文件不匹配")
    require(record.get("sha256") == scanned["sha256"], "LLM 裁定的源码摘要已过期或不匹配")
    candidates = {c["candidate_id"]: c for c in scanned["review_candidates"]}
    decisions = record.get("decisions", [])
    require(isinstance(decisions, list), "decisions 必须为数组")
    resolved = {}
    for decision in decisions:
        keys(decision, {"candidate_id", "verdict", "reason", "evidence"}, "LLM 候选裁定")
        candidate_id = decision.get("candidate_id")
        require(isinstance(candidate_id, str) and candidate_id in candidates, "LLM 候选 ID 不存在；确定性发现不能被外部撤销")
        require(candidate_id not in resolved, "同一候选不能重复裁定")
        candidate = candidates[candidate_id]
        choices = {"confirmed", "dismissed", "unverified"} if candidate["kind"] == "finding" else {"reviewed", "unverified"}
        require(isinstance(decision.get("verdict"), str) and decision["verdict"] in choices, "此候选不支持该裁定类型")
        explanation(decision.get("reason"), "裁定依据")
        evidence(decision.get("evidence"), (candidate["offset"], candidate["end_offset"]))
        resolved[candidate_id] = decision
    candidate_by_source = {(c["kind"], c["offset"], c["end_offset"], c["category"], c["rule_id"], c["reason"]): c
                           for c in candidates.values()}
    effective_findings, effective_skipped = [], []
    for finding in scanned["findings"]:
        item = dict(finding)
        candidate = candidate_by_source.get(("finding", item["offset"], item["end_offset"], item["category"], item["rule_id"], item["standard"]))
        decision = resolved.get(candidate["candidate_id"]) if candidate else None
        if decision and decision["verdict"] == "dismissed":
            continue
        if decision and decision["verdict"] == "confirmed":
            item["type"], item["verified_by"] = "Confirmed", "llm"
            item["adjudication"] = decision
        effective_findings.append(item)
    for scope in scanned["skipped"]:
        item = dict(scope)
        candidate = candidate_by_source.get(("scope", item["offset"], item["end_offset"], item.get("category", "coverage"), None, item["reason"]))
        decision = resolved.get(candidate["candidate_id"]) if candidate else None
        if decision and decision["verdict"] == "reviewed":
            item["unverified"], item["verified_by"] = False, "llm"
            item["adjudication"] = decision
        effective_skipped.append(item)
    additional = record.get("additional_findings", [])
    require(isinstance(additional, list), "additional_findings 必须为数组")
    starts = [0] + [m.end() for m in re.finditer(r"\r\n|[\r\n]", source)]
    for item in additional:
        keys(item, {"category", "offset", "end_offset", "position", "excerpt", "standard", "reason", "evidence"}, "LLM 新增格式发现")
        category = item.get("category")
        require(isinstance(category, str) and category in CATEGORIES and category != "coverage", "新增已确认错误需要有效的格式类别")
        a, b = span(item)
        pos = item.get("position")
        require(type(pos) is int and a <= pos <= b, "新增发现的独立位置必须在其源码范围内")
        explanation(item.get("standard"), "适用规范")
        explanation(item.get("reason"), "发现依据")
        evidence(item.get("evidence"), (a, b))
        row = bisect.bisect_right(starts, a)
        effective_findings.append({"file": scanned["file"], "rule_id": "LLM001", "category": category,
            "offset": a, "end_offset": b, "line": row, "column": a - starts[row - 1] + 1,
            "excerpt": item["excerpt"], "excerpt_truncated": False, "standard": item["standard"],
            "suggestion": item["reason"], "type": "Confirmed", "occurrence_key": str(pos), "position": pos,
            "verified_by": "llm", "evidence": item["evidence"]})
    return {"effective_findings": effective_findings, "effective_skipped": effective_skipped,
            "adjudications": decisions, "additional_findings": additional,
            "format_assessment": format_assessment(effective_findings, effective_skipped)}


def load_format_decisions(path, scans, sources):
    """Validate the entire batch before applying any decision (all or nothing)."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("复核 JSON 包含重复字段：" + key)
            result[key] = value
        return result

    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream, object_pairs_hook=unique_object)
    if not isinstance(payload, dict) or set(payload) != {"files"} or not isinstance(payload["files"], list):
        raise ValueError('复核 JSON 必须为 {"files": [文件记录, ...]}')
    by_file = {scan["file"]: scan for scan in scans}
    merged = {}
    for record in payload["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("file"), str) or record["file"] not in by_file:
            raise ValueError("复核记录必须对应本次已成功扫描的完整文件路径")
        filename = record["file"]
        if filename in merged:
            raise ValueError("同一文件不能重复提交复核记录")
        merged[filename] = apply_format_decisions(by_file[filename], sources[filename], record)
    return merged


class Scanner:
    def __init__(self, source, filename):
        self.source, self.filename = source, str(filename)
        self.view = list(source)
        self._view_cache = None
        self.starts = [0] + [m.end() for m in re.finditer(r"\r\n|[\r\n]", source)]
        self.paragraph_boundaries = [m.start() for m in re.finditer("(?=" + BLANK_PARAGRAPH.pattern + ")", source)]
        self.findings, self.skipped = [], []
        self.tables, self.code_spans, self.math_spans = set(), [], []
        self.inline_tokens = []
        self.link_labels = []
        self.reference_ids = set()
        self.kinds, self.headings, self.lists = {}, [], []
        self.quote_levels = {}
        self.seen = set()
        self.projection_spans = {}
        self.unverified_projection = set()
        self.custom_math_seen = False
        for pos, char in enumerate(source):
            if char in ("\0", MATH_TOKEN, CODE_TOKEN, OTHER_TOKEN):
                self.skip(pos, pos + 1, "源文含保留标记字符，其替换显示未获验证", True, mask=False)
                self.view[pos] = "\ufffd"
            elif 0x20000 <= ord(char) <= 0x3ffff and unicodedata.category(char) == "Cn":
                self.skip(pos, pos + 1, "当前 Unicode 数据库未验证此扩展字符，不作为已确认中文边界", True, mask=False)
                self.view[pos] = "\ufffd"
        lines = source_lines(source)
        for index, line in enumerate(lines):
            cells = line.strip().strip("|").split("|")
            if "|" in line and cells and all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells) and index and "|" in lines[index - 1]:
                self.tables.update((index, index + 1))
                after = index + 1
                while after < len(lines) and lines[after].strip() and "|" in lines[after]:
                    self.tables.add(after + 1)
                    after += 1

    def location(self, pos):
        row = bisect.bisect_right(self.starts, pos)
        return row, pos - self.starts[row - 1] + 1

    def line_bounds(self, pos):
        row, _ = self.location(pos)
        start = self.starts[row - 1]
        stop = self.starts[row] if row < len(self.starts) else len(self.source)
        if stop > start and self.source[stop - 1] == "\n":
            stop -= 1
        if stop > start and self.source[stop - 1] == "\r":
            stop -= 1
        return start, stop

    def paragraph_limit(self, start):
        index = bisect.bisect_left(self.paragraph_boundaries, start)
        return self.paragraph_boundaries[index] if index < len(self.paragraph_boundaries) else len(self.source)

    def masked_text(self):
        if self._view_cache is None:
            self._view_cache = "".join(self.view)
        return self._view_cache

    def mask(self, start, end):
        self._view_cache = None
        for i in range(start, end):
            if self.view[i] not in "\r\n":
                self.view[i] = "\0"

    def add(self, rule, start, end, suggestion, kind="Confirmed", category=None, occurrence=None, evidence=None):
        category = category or RULES[rule][0]
        occurrence = str(start) if occurrence is None else str(occurrence)
        key = (category, occurrence, kind)
        if kind == "Warning" and (category, occurrence, "Confirmed") in self.seen:
            return
        if kind == "Confirmed" and (category, occurrence, "Warning") in self.seen:
            self.seen.remove((category, occurrence, "Warning"))
            self.findings[:] = [f for f in self.findings if not
                (f["category"] == category and f["occurrence_key"] == occurrence and f["type"] == "Warning")]
        if key in self.seen:
            return
        self.seen.add(key)
        row, column = self.location(start)
        self.findings.append({"rule_id": rule, "category": category, "file": self.filename,
            "line": row, "column": column, "end_offset": end, "offset": start,
            "excerpt": self.source[start:end] if end - start <= 180 else self.source[start:start + 177] + "…",
            "excerpt_truncated": end - start > 180, "standard": RULES[rule][1],
            "suggestion": suggestion, "type": kind, "occurrence_key": occurrence})
        if evidence is not None:
            self.findings[-1]["evidence"] = evidence

    def skip(self, start, end, reason, unverified=False, mask=True, category=None):
        row, column = self.location(start)
        last, _ = self.location(max(start, end - 1))
        self.skipped.append({"file": self.filename, "line": row, "column": column,
            "offset": start, "end_offset": end,
            "end_line": last, "reason": reason, "unverified": unverified,
            **({"category": category, "occurrence_key": str(start)} if category else {})})
        if mask:
            self.mask(start, end)

    def blocks(self):
        fence = None
        raw = None
        comment = None
        front = None
        fold = 0
        containers = []
        display = None
        list_indents = []
        offset = 0
        block_lines = source_lines(self.source, keepends=True)
        declared_metadata = False
        if block_lines and block_lines[0].rstrip("\r\n") == "---":
            for candidate in block_lines[1:]:
                candidate = candidate.strip()
                if not candidate or candidate.startswith("#"):
                    continue
                declared_metadata = bool(re.match(r"[A-Za-z_][A-Za-z0-9_.-]*[ \t]*:", candidate))
                break
        for row, line in enumerate(block_lines, 1):
            end = offset + len(line)
            prefix = re.match(r" {0,3}(?:>[ \t]? {0,3})*", line).end()
            self.quote_levels[row] = line[:prefix].count(">")
            indent = len(line) - len(line.lstrip(" "))
            # A list's content indentation is relative to its marker width.
            # Four spaces in an active item need not begin a code block.
            nested = ">" not in line[:prefix] and bool(list_indents) and indent >= list_indents[-1][1]
            parent_indent = list_indents[-1][1] if nested else 0
            if nested:
                prefix = indent
            body = line[prefix:].rstrip("\r\n")
            self.kinds[row] = "prose"
            if row == 1 and body == "---" and declared_metadata:
                front = offset
                self.mask(offset, end)
                self.kinds[row] = "metadata"
                offset = end
                continue
            if front is not None:
                self.mask(offset, end)
                self.kinds[row] = "metadata"
                if body in ("---", "..."):
                    self.skip(front, end, "YAML 前置信息，不适用正文排版规则")
                    front = None
                offset = end
                continue
            if fence:
                self.kinds[row] = "code"
                self.mask(offset, end)
                if re.fullmatch(r"[ >\t]*" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", body):
                    closing_indent = len(line) - len(line.lstrip(" ")) if ">" not in line[:prefix] else len(body) - len(body.lstrip(" "))
                    if closing_indent <= fence[4]:
                        self.code_spans.append((fence[2], end, fence[3], offset, fence[5]))
                        if row - fence[6] - 1 > 80 and not fence[5]:
                            self.add("MD011", fence[2], fence[2] + fence[1],
                                "代码超过 80 行只是长度线索；使用折叠块，本版不把长度本身当作已证实违规", "Warning")
                        fence = None
                offset = end
                continue
            if raw:
                self.kinds[row] = "opaque"
                self.mask(offset, end)
                if re.search(r"</" + raw[0] + r"\s*>", line, re.I):
                    self.skip(raw[1], end, "原始 HTML 块的显示未获验证", True)
                    raw = None
                offset = end
                continue
            if comment is not None:
                closing = line.find("-->")
                if closing < 0:
                    self.mask(offset, end)
                    self.kinds[row] = "comment"
                    offset = end
                    continue
                self.skip(comment, offset + closing + 3, "HTML 注释，不作为可见正文")
                comment = None
                body = "".join(self.view[offset + prefix:end]).rstrip("\r\n")
            if display:
                # Math is parsed by the inline lexer, not by code/list detection.
                self.kinds[row] = "math"
                if display in body:
                    display = None
                offset = end
                continue
            directive = re.fullmatch(r":::\s*([A-Za-z][A-Za-z0-9_-]*)(?:\[.*\]|\s+.*)?", body)
            html_details = re.fullmatch(r"<details(?:\s+[^>]*)?>", body, re.I)
            if directive or html_details:
                known = bool(html_details) or directive[1].lower() in {"details", "fold", "collapse"}
                folding = known
                containers.append(("html" if html_details else "directive", offset, folding))
                fold += int(folding)
                self.skip(offset, end, "折叠容器标记" if known else "此扩展容器的渲染语法未获验证",
                          not known, category="container" if not known else None)
                self.kinds[row] = "container"
                offset = end
                continue
            summary = re.fullmatch(r"<summary>(.*)</summary>", body, re.I)
            if summary:
                known = bool(containers) and containers[-1][0] == "html"
                self.skip(offset, end, "折叠标题标记" if known else "summary 不在已识别的 details 容器中",
                          not known, mask=False, category="container" if not known else None)
                self.mask(offset, offset + prefix + summary.start(1))
                self.mask(offset + prefix + summary.end(1), end)
                self.kinds[row] = "container"
                offset = end
                continue
            if body == ":::" or re.fullmatch(r"</details>", body, re.I):
                expected = "directive" if body == ":::" else "html"
                if containers and containers[-1][0] == expected:
                    _, _, folding = containers.pop()
                    fold -= int(folding)
                    self.skip(offset, end, "扩展容器结束标记")
                else:
                    self.add("MD013", offset + prefix, end, "容器结束标记没有匹配的开头，范围不能确认", "Warning")
                    self.mask(offset, end)
                self.kinds[row] = "container"
                offset = end
                continue
            fence_match = re.match(r"(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$", body)
            if fence_match and not (fence_match[1][0] == "`" and "`" in fence_match[2]):
                start = offset + prefix + fence_match.start(1)
                # Plain fences close with at most 3 spaces; list fences may be nested.
                closing_limit = prefix + fence_match.start(1) + 3
                fence = (fence_match[1][0], len(fence_match[1]), start, end, closing_limit, bool(fold), row)
                self.mask(offset, end)
                self.kinds[row] = "code"
                offset = end
                continue
            if line.startswith("\t") or indent >= (parent_indent + 4 if nested else 4):
                self.skip(offset, end, "缩进代码；复杂列表缩进不能静态确认为正文", True)
                self.kinds[row] = "opaque"
                offset = end
                continue
            # Exclude same-line inline code before recognizing HTML comments.
            comment_view = body
            for code in re.finditer(r"(?<!`)(`+)(?!`)(.*?)\1(?!`)", body):
                comment_view = comment_view[:code.start()] + "\0" * len(code[0]) + comment_view[code.end():]
            cursor = 0
            while True:
                opening = comment_view.find("<!--", cursor)
                if opening < 0:
                    break
                closing = comment_view.find("-->", opening + 4)
                if closing < 0:
                    comment = offset + prefix + opening
                    self.mask(comment, end)
                    break
                self.skip(offset + prefix + opening, offset + prefix + closing + 3, "HTML 注释，不作为可见正文")
                cursor = closing + 3
            body = "".join(self.view[offset + prefix:end]).rstrip("\r\n")
            tag = re.match(r"<(pre|script|style|textarea|table|div)(?:\s|>)", body, re.I)
            if tag:
                raw = (tag[1].lower(), offset)
                self.kinds[row] = "opaque"
                self.mask(offset, end)
                if re.search(r"</" + raw[0] + r"\s*>", line, re.I):
                    self.skip(offset, end, "原始 HTML 块的显示未获验证", True)
                    raw = None
                offset = end
                continue
            if re.match(r"\[[^\]\n]+\]:", body):
                self.reference_ids.add(" ".join(body[1:body.index("]:")].split()).casefold())
                self.skip(offset, end, "引用式链接或脚注定义的目标未验证", True)
                self.kinds[row] = "reference"
                offset = end
                continue
            # Setext headings may span several plain paragraph lines. They are
            # headings, so their titles do not require sentence punctuation.
            if re.fullmatch(r"=+[ \t]*|-+[ \t]*", body) and self.kinds.get(row - 1) == "prose":
                title_rows = []
                previous = row - 1
                while previous > 0 and self.kinds.get(previous) == "prose" and previous not in self.tables and self.quote_levels.get(previous) == self.quote_levels.get(row):
                    if not block_lines[previous - 1].strip():
                        break
                    title_rows.append(previous)
                    previous -= 1
                if title_rows:
                    first = title_rows[-1]
                    content = " ".join("".join(self.view[self.starts[n - 1]:self.starts[n] if n < len(self.starts) else len(self.source)]).replace("\0", "").strip()
                                       for n in reversed(title_rows))
                    self.headings.append((first, self.starts[first - 1], end, content))
                    for n in title_rows:
                        self.kinds[n] = "heading"
                    obsolete = [f for f in self.findings if f["line"] in title_rows and f["rule_id"] == "MD001" and f["type"] == "Warning"]
                    for finding in obsolete:
                        self.seen.discard((finding["category"], finding["occurrence_key"], finding["type"]))
                        self.findings.remove(finding)
                    self.kinds[row] = "heading_marker"
                    self.mask(offset, end)
                    offset = end
                    continue
            stripped = body.strip()
            if stripped in ("$$", r"\["):
                display = "$$" if stripped == "$$" else r"\]"
                self.kinds[row] = "math"
            if re.fullmatch(r"(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,}", body):
                self.kinds[row] = "thematic"
            heading = re.match(r"(#{1,6})(?:[ \t]+|$)(.*)", body)
            if heading:
                self.kinds[row] = "heading"
                content = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2]).strip()
                self.headings.append((row, offset + prefix, end, content))
                if len(heading[1]) > 4 or not content:
                    self.add("MD001", offset + prefix, offset + prefix + len(heading[1]), "使用非空的一至四级标题")
                self.mask(offset + prefix, offset + prefix + heading.start(2))
            elif re.match(r"#{1,6}[^#\s]|#{7,}(?:[ \t]|$)", body):
                suggestion = "井号超过 ATX 标题层级；若为标题，改为一至四级" if body.startswith("#######") else "若为标题，补齐标记后的空格"
                self.add("MD001", offset + prefix, end, suggestion, "Warning")
            marker = re.match(r"([-+*]|\d+[.)])([ \t]*)(.*)", body)
            if marker and (marker[2] or re.match(HAN + r"|\$", marker[3])):
                if ">" not in line[:prefix]:
                    while list_indents and indent <= list_indents[-1][0]:
                        list_indents.pop()
                    list_indents.append((indent, prefix + marker.start(3)))
                self.kinds[row] = "list"
                self.lists.append((row, offset + prefix, marker[1], bool(marker[2]), prefix, end))
                if marker[1].endswith(")") and marker[2]:
                    self.add("MD003", offset + prefix, offset + prefix + len(marker[1]), "将有序列表标记改为数字加点")
                self.mask(offset + prefix, offset + prefix + marker.start(3))
            elif body.strip() and not fence:
                while list_indents and indent < list_indents[-1][1]:
                    list_indents.pop()
            self.mask(offset, offset + prefix)
            offset = end
        if fence:
            self.add("MD002", fence[2], fence[2] + fence[1], "补齐同字符且长度足够的闭合围栏")
            self.code_spans.append((fence[2], len(self.source), fence[3], len(self.source), fence[5]))
        if raw:
            self.skip(raw[1], len(self.source), "未结束或复杂的 HTML 块", True)
        if front is not None:
            self.skip(front, len(self.source), "未闭合的 YAML 前置信息", True)
        if comment is not None:
            self.skip(comment, len(self.source), "未结束的 HTML 注释", True)
        for _, start, _ in containers:
            self.add("MD013", start, min(start + 3, len(self.source)), "扩展容器未闭合，折叠及后续范围不能确认", "Warning")

    def structure(self):
        for index, (row, start, marker, spaced, indent, end) in enumerate(self.lists):
            if not spaced:
                numeric = marker[0].isdigit()
                peers = [x for x in self.lists if x[4] == indent and (x[2][0].isdigit() == numeric) and abs(x[0] - row) <= 40]
                kind = "Confirmed" if len(peers) >= 2 else "Warning"
                self.add("MD003", start, start + len(marker), "在列表标记与内容之间补半角空格", kind)
            # A following same-level paragraph or fence leaves the list item.
            if index + 1 < len(self.lists):
                next_row = self.lists[index + 1][0]
                next_marker = self.lists[index + 1][2]
                if self.lists[index + 1][4] == indent and (marker[0].isdigit() == next_marker[0].isdigit()):
                    for number in range(row + 1, min(next_row, row + 25)):
                        line = self.source[self.starts[number - 1]:self.starts[number] if number < len(self.starts) else len(self.source)]
                        if line.strip() and len(line) - len(line.lstrip(" ")) <= indent and self.kinds.get(number) in ("prose", "code"):
                            # An unindented paragraph line without a blank line is
                            # a valid lazy continuation of the list's paragraph.
                            previous = self.source[self.starts[number - 2]:self.starts[number - 1]] if number > 1 else ""
                            if self.kinds.get(number) == "prose" and previous.strip() and self.kinds.get(number - 1) in ("list", "prose"):
                                continue
                            self.add("MD006", self.starts[number - 1], self.starts[number - 1] + len(line.rstrip()),
                                "该正文或代码未缩进归入前一个列表项；若意在延续列表，修正缩进", "Warning")
                            break
        procedural = []
        for index, (row, start, end, content) in enumerate(self.headings):
            next_row = self.headings[index + 1][0] if index + 1 < len(self.headings) else len(self.starts) + 1
            has_body = any(self.source[self.starts[n - 1]:self.starts[n] if n < len(self.starts) else len(self.source)].strip()
                           for n in range(row + 1, next_row))
            step = re.match(r"[（(]?\d+(?:\.\d+)*[）).、][ \t]*(如果|若|初始化|从|将|对于|更新|删除|计算|结束|返回)", content)
            if step and not has_body and content.endswith(("。", "；")):
                procedural.append((row, start, end))
            else:
                if len(procedural) >= 3:
                    for _row, a, b in procedural:
                        self.add("MD005", a, b, "连续编号动作句没有章节正文，改为列表或伪代码步骤")
                procedural = []
            if re.match(r"(?:[（(]?\d+(?:\.\d+)*[）).、]|如果|将|从)", content) and len(content) > 24:
                body_rows = [n for n in range(row + 1, next_row) if self.kinds.get(n) == "prose" and self.source[self.starts[n - 1]:self.starts[n] if n < len(self.starts) else len(self.source)].strip()]
                if not body_rows:
                    self.add("MD005", start, end, "步骤式标题的章节用途尚不能确认", "Warning")
        if len(procedural) >= 3:
            for _row, a, b in procedural:
                self.add("MD005", a, b, "连续编号动作句没有章节正文，改为列表或伪代码步骤")

    def inline(self):
        # Consuming a token only masks text behind the cursor. Rebuild this
        # snapshot only when a link masks its destination ahead of the cursor.
        view = self.masked_text()
        i = 0
        while i < len(self.view):
            char = self.view[i]
            if char == "\0" or char.isspace():
                i += 1
                continue
            if char == "`" and not escaped(self.source, i):
                run = re.match(r"`+", view[i:])[0]
                limit = self.paragraph_limit(i)
                closing = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", view[i + len(run):limit])
                if closing:
                    stop = i + len(run) + closing.end()
                    content = self.source[i + len(run):stop - len(run)]
                    context = self.source[max(0, i - 16):i]
                    literal_context = bool(re.search(r"字符串|输入|输出|字面|代码|字符|命令|程序", context))
                    concept = bool(re.fullmatch(r"动态规划|线性[ ]?(?:dp|DP)|树形[ ]?(?:dp|DP)|DP|BFS|DFS|LIS|STL|Dynamic Programming", content))
                    tail = self.source[stop:stop + 12]
                    conceptual_use = bool(re.search(r"全称[ \t]*$", context) or re.match(r"(?:的)?(?:分类|通常用来|通常用于|是一种|表示在)", tail))
                    if concept and conceptual_use and not literal_context:
                        self.add("MD007", i, stop, "算法概念名在定义或分类叙述中使用普通文字")
                    elif re.fullmatch(HAN + r"{2,12}", content) and not literal_context:
                        self.add("MD007", i, stop, "代码样式中的纯中文可能是普通叙述，也可能是字符串", "Warning")
                    elif self.math_candidate(content):
                        context = self.source[max(0, i - 16):i]
                        if not re.search(r"输入|输出|字符串|代码|语句|命令|执行|调用|键入", context):
                            kind = "Confirmed" if re.search(r"数学|复杂度|表达式|公式", context) else "Warning"
                            self.add("MATH003", i, stop, "数学表达式使用 LaTeX，真实程序片段保留代码样式", kind)
                            self.complexity(content, i + len(run))
                    elif re.fullmatch(r"(?:BFS|DFS|DP|LIS|STL|Dynamic Programming)", content):
                        self.add("MD007", i, stop, "普通算法名不使用代码样式强调", "Warning")
                else:
                    stop = limit
                    self.add("MD004", i, i + len(run), "确认代码定界是否缺失；未闭合范围不能视为已检查", "Warning")
                    self.skip(i, stop, "未闭合的行内代码范围", True, mask=False, category="code_fence")
                    self.inline_tokens.append((i, stop, "opaque", ""))
                if closing:
                    self.inline_tokens.append((i, stop, "code", content))
                self.mask(i, stop)
                i = max(stop, i + 1)
                continue
            if (char == "$" and not escaped(self.source, i)) or (char == "\\" and not escaped(self.source, i) and view[i:i + 2] in (r"\(", r"\[")):
                if char == "\\" and any(a <= i < b for a, b in self.link_labels):
                    # Luogu problem titles commonly escape their literal [tags].
                    i += 2
                    continue
                i = self.consume_math(i, view)
                continue
            if (char == "!" and view[i:i + 2] == "![" or char == "[") and not escaped(self.source, i):
                image = char == "!"
                label_start = i + (2 if image else 1)
                label_end = balanced_end(view, label_start - 1, "[", "]")
                if label_end is not None and label_end < len(view) and view[label_end] in "([":
                    open_char = view[label_end]
                    stop = balanced_end(view, label_end, open_char, ")" if open_char == "(" else "]")
                    if stop is None:
                        limit = self.paragraph_limit(i)
                        self.add("MD008", i, min(i + 1, limit), "链接语法未闭合，其显示范围不能确认", "Warning")
                        self.skip(i, limit, "复杂或未闭合的链接语法", True, category="link")
                        self.inline_tokens.append((i, limit, "opaque", ""))
                        i = limit
                        continue
                    if open_char == "(":
                        target, valid = link_destination(self.source[label_end + 1:stop - 1])
                    else:
                        reference = self.source[label_end + 1:stop - 1] or self.source[label_start:label_end - 1]
                        target = ""
                        valid = " ".join(reference.split()).casefold() in self.reference_ids
                    if not valid:
                        self.add("MD008", i, stop, "链接目标、标题或引用定义不能按当前语法确认，使用受支持的链接写法", "Warning")
                        self.skip(i, stop, "未验证的链接范围", True, category="link")
                        self.inline_tokens.append((i, stop, "opaque", ""))
                        i = stop
                        continue
                    if image:
                        if target and not re.match(r"(?:https?://(?:cdn|ipic)\.luogu\.com\.cn/|https?://[^/]*luogu\.oss-|data:)", target):
                            self.add("MD010", label_end + 1, stop - 1, "核对适用发布平台的图床要求；外部图床是否受限或属于合法例外需复核", "Warning")
                        self.skip(i, stop, "图片文字排版与可访问性未由源码检查验证", True)
                        self.inline_tokens.append((i, stop, "opaque", ""))
                        i = stop
                        continue
                    label = self.source[label_start:label_end - 1]
                    if label.startswith("!["):
                        self.add("MD009", i, stop, "去掉图片外层跳转链接")
                    self.mask(i, label_start)
                    self.mask(label_end - 1, stop)
                    view = self.masked_text()
                    self.link_labels.append((label_start, label_end - 1))
                    i = label_start
                    continue
            if char == "<":
                auto = re.match(r"<(?:https?://[^\s<>]+|[^\s<>@]+@[^\s<>@]+)>", view[i:], re.I)
                tag = re.match(r"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>", view[i:])
                if auto or tag:
                    stop = i + (auto or tag).end()
                    if auto:
                        self.inline_tokens.append((i, stop, "code", self.source[i + 1:stop - 1]))
                    else:
                        opening_tag = re.match(r"<([A-Za-z][A-Za-z0-9:-]*)\b", tag[0])
                        if opening_tag and opening_tag[1].lower() not in {
                            "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
                            depth, limit = 1, len(view)
                            tag_pattern = r"<!--(?:[\s\S]*?-->|[\s\S]*$)|<(/?)" + re.escape(opening_tag[1]) + r"(?=[\s/>])(?:[^>\"']|\"[^\"]*\"|'[^']*')*>"
                            for nested_tag in re.finditer(tag_pattern, view[stop:], re.I):
                                if nested_tag[0].startswith("<!--"):
                                    continue
                                # In HTML, '/>' does not close a non-void tag.
                                depth += -1 if nested_tag[1] else 1
                                if depth == 0:
                                    limit = stop + nested_tag.end()
                                    break
                            # Unknown HTML can hide or replace its children. Do
                            # not convict invisible child text as rendered prose.
                            stop = limit
                        self.inline_tokens.append((i, stop, "opaque", ""))
                    self.skip(i, stop, "自动链接不作正文检查" if auto else "内联 HTML 显示未获验证", not bool(auto))
                    i = stop
                    continue
            if char in "hH" and view[i:i + 8].lower().startswith(("http://", "https://")):
                match = re.match(r"https?://[^\s<>\[\]\x00]+", view[i:], re.I)
                if match is None:
                    stop = i + len(re.match(r"https?://", view[i:], re.I)[0])
                    self.add("MD008", i, stop, "URL 只有协议前缀，目标与用途不能确认；字面协议名应使用代码样式", "Warning")
                    self.inline_tokens.append((i, stop, "code", self.source[i:stop]))
                    self.mask(i, stop)
                    i = stop
                    continue
                stop = i + len(match[0].rstrip(".,;:!?，。；：！？）)"))
                prefix_end = i + len(re.match(r"https?://", view[i:], re.I)[0])
                self.add("MD008", i, stop, "把裸 URL 写成 Markdown 链接" if stop > prefix_end else "URL 缺少目标地址，不能确认合规",
                         "Confirmed" if stop > prefix_end else "Warning")
                self.inline_tokens.append((i, stop, "code", self.source[i:stop]))
                self.mask(i, stop)
                i = stop
                continue
            i += 1

    @staticmethod
    def math_candidate(text):
        return bool(re.fullmatch(r"(?:[A-Za-z]|O\s*\([^\n]+\)|[A-Za-z0-9_(){}\s]+[+\-*/=≤≥<>×][A-Za-z0-9_(){}\s+\-*/=≤≥<>×]*|\d+[A-Za-z][A-Za-z0-9_()\s+\-*/]*)", text))

    def consume_math(self, start, view):
        opening = ("$$" if view.startswith("$$", start) else "$") if view[start] == "$" else view[start:start + 2]
        closing = {r"\(": r"\)", r"\[": r"\]"}.get(opening, opening)
        content = start + len(opening)
        limit = self.paragraph_limit(content) if opening in ("$", r"\(") else len(view)
        stop = content
        while True:
            stop = view.find(closing, stop, limit)
            if stop < 0:
                break
            if not escaped(self.source, stop) and (closing != "$" or (view[stop - 1:stop] != "$" and view[stop + 1:stop + 2] != "$")):
                break
            stop += len(closing)
        if stop < 0:
            line_start, line_end = self.line_bounds(start)
            alone = self.source[line_start:line_end].strip() == opening
            kind = "Confirmed" if opening in (r"\[", r"\(") or opening == "$$" and alone else "Warning"
            self.add("MATH002", start, content, "补齐数学定界；字面美元应转义", kind)
            self.skip(start, limit, "未闭合数学范围的后续格式未获验证", True, mask=False, category="math_delimiter")
            self.inline_tokens.append((start, limit, "unverified_math", ""))
            self.mask(start, limit)
            return max(limit, content)
        end = stop + len(closing)
        body = self.source[content:stop]
        ambiguous = (opening == "$" and (not body.strip() or body != body.strip() or "\0" in view[content:stop]
                     or bool(re.match(r"\d+(?:\.\d+)?(?:[ \t，。,;:]|$)", body) and re.search(HAN + r"|[A-Za-z]{2,}", body)))) or (opening == "$$" and "$" in body)
        if ambiguous:
            self.add("MATH002", start, end, "美元、跨结构或空白定界用法不能静态确认合规", "Warning")
            self.skip(start, end, "定界用途不明的数学范围未获验证", True, mask=False, category="math_delimiter")
            self.inline_tokens.append((start, end, "unverified_math", body))
        else:
            if opening in ("$", r"\("):
                for pos in (start - 1, end):
                    if 0 <= pos < len(self.source) and re.fullmatch(HAN, self.source[pos]):
                        boundary = start if pos < start else end
                        self.add("MATH001", min(pos, start), max(end, pos + 1), "在相邻边界补半角空格", occurrence=boundary)
                line_start, _ = self.line_bounds(start)
                _, line_end = self.line_bounds(end)
                if self.kinds.get(self.location(start)[0]) != "heading" and NON_SPACE.search(self.source, line_start, start) is None and self.source[end:line_end].strip() in ("", "。", "，", "."):
                    self.add("TEX014", start, end, "独立公式改用行间环境")
            self.tex(content, stop)
        self.math_spans.append((start, end, opening))
        if opening in ("$", r"\(") and not ambiguous:
            self.inline_tokens.append((start, end, "math", body))
        self.mask(start, end)
        return end

    def tex(self, start, end):
        body = self.source[start:end]
        clean = list(body)
        # Verbatim delimiters and their contents are opaque before looking for
        # comments; a literal percent sign must not hide the rest of the math.
        verbatim = list(re.finditer(r"\\verb\*?([^A-Za-z\s])[^\r\n]*?\1", body))
        for match in verbatim:
            if not escaped(body, match.start()):
                clean[match.start():match.end()] = " " * len(match[0])
        clean_text = "".join(clean)
        for match in re.finditer(r"\\verb\b", clean_text):
            if not escaped(clean_text, match.start()):
                self.add("TEX013", start + match.start(), start + match.end(),
                    "verb 的定界未获验证，不能把后续内容假定为可正常显示", "Warning")
                stop = re.search(r"[\r\n]", body[match.end():])
                stop = match.end() + stop.start() if stop else len(body)
                clean[match.start():stop] = " " * (stop - match.start())
        clean_text = "".join(clean)
        comment_end = -1
        for match in re.finditer(r"%", clean_text):
            if not escaped(clean_text, match.start()):
                if match.start() < comment_end:
                    continue
                newline = re.search(r"[\r\n]", body[match.start():])
                stop = match.start() + newline.start() if newline else len(body)
                if re.match(r"[A-Za-z0-9]", body[match.end():]) and match.start() and re.match(r"[A-Za-z0-9]", body[match.start() - 1]):
                    self.add("TEX007", start + match.start(), start + match.end(), "若表示取模，使用 bmod；百分号在 TeX 中开始注释", "Warning")
                clean[match.start():stop] = " " * (stop - match.start())
                comment_end = stop
        clean = "".join(clean)
        commands = [m for m in re.finditer(r"\\([A-Za-z]+)", clean) if not escaped(clean, m.start())]
        unknown = [m for m in commands if m[1] not in TEX_COMMANDS]
        custom = bool(re.search(r"\\(?:def|gdef|edef|newcommand|renewcommand|providecommand|newenvironment|renewenvironment|let|catcode)\b", clean))
        syntax_kind = "Warning" if unknown or custom else "Confirmed"
        for match in unknown:
            self.add("TEX003" if match[1] in {"frca", "fraq", "sqart", "begni"} else "TEX013",
                start + match.start(), start + match.end(),
                "此命令未由脚本验证；提供受支持的命令或扩充经过测试的规则，不能声称命令必然非法", "Warning")
        if custom:
            self.add("TEX013", start, end, "该公式定义自定义宏，静态显示与展开范围未验证", "Warning")
            self.custom_math_seen = True
        elif self.custom_math_seen:
            self.add("TEX013", start, end, "此前宏定义可能覆盖标准命令，需核验本式的展开和显示", "Warning")
        if unknown or self.custom_math_seen:
            self.skip(start, end, "未知命令或宏可改变参数与显示范围，交 LLM 核验整式", True, mask=False,
                      category="math_support")
            return
        stack = []
        environments = [m for m in re.finditer(r"\\(begin|end)\s*\{([^{}]+)\}", clean) if not escaped(clean, m.start())]
        unknown_environment = any(m[2] not in ENVIRONMENTS for m in environments)
        syntax_kind = "Warning" if unknown_environment else syntax_kind
        for match in environments:
            if escaped(clean, match.start()):
                continue
            name = match[2]
            if name not in ENVIRONMENTS:
                self.add("TEX001", start + match.start(), start + match.end(), "该环境未由脚本验证", "Warning")
                self.skip(start + match.start(), end, "未知环境的取参和显示未获验证", True, mask=False,
                          category="math_delimiter")
                continue
            if match[1] == "begin":
                stack.append((name, match.start(), match.end()))
            elif stack and stack[-1][0] == name:
                stack.pop()
            else:
                # One mismatched begin/end pair is one erroneous location.
                opener = stack.pop() if stack else (name, match.start(), match.end())
                self.add("TEX001", start + opener[1], start + match.end(),
                    "修正 begin/end 名称及嵌套顺序", syntax_kind, occurrence=start + opener[1])
        for name, pos, stop in stack:
            self.add("TEX001", start + pos, start + stop, "补齐对应 end 环境", syntax_kind)
        if unknown_environment:
            return
        braces = []
        for i, char in enumerate(clean):
            if escaped(clean, i):
                continue
            if char == "{":
                braces.append(i)
            elif char == "}":
                if braces:
                    braces.pop()
                else:
                    self.add("TEX002", start + i, start + i + 1, "删去多余右花括号或补左花括号", syntax_kind)
        for i in braces:
            self.add("TEX002", start + i, start + i + 1, "补齐右花括号", syntax_kind)
        lefts = []
        for match in re.finditer(r"\\(left|right|middle)\b", clean):
            if match[1] == "left":
                lefts.append(match.start())
            elif match[1] == "middle":
                if not lefts:
                    self.add("TEX001", start + match.start(), start + match.end(), "middle 需要位于 left/right 定界内部", syntax_kind)
            elif lefts:
                lefts.pop()
            else:
                self.add("TEX001", start + match.start(), start + match.end(), "补齐对应 left 定界", syntax_kind)
        for i in lefts:
            self.add("TEX001", start + i, start + i + 5, "补齐对应 right 定界", syntax_kind)
        self.tex_arguments(clean, commands, start, syntax_kind)
        for match in commands:
            if match[1] in {"limits", "nolimits", "color", "textcolor"}:
                self.add("TEX013", start + match.start(), start + match.end(),
                         "上下限修饰的运算符上下文或颜色参数未由静态规则验证", "Warning")
            elif match[1] in {"hline", "cr"} and not re.search(r"\\begin\s*\{(?:array|[bpvBV]?matrix|smallmatrix)\}", clean):
                self.add("TEX013", start + match.start(), start + match.end(),
                         "行／分隔线命令未处于已识别的数组或矩阵中，需要核验环境支持", "Warning")
        text_view, face_view = list(clean), list(clean)
        for match in commands:
            if match[1] not in FACE_COMMANDS:
                continue
            pos = match.end()
            if pos < len(clean) and clean[pos] == "*":
                pos += 1
            while pos < len(clean) and clean[pos].isspace():
                pos += 1
            if pos >= len(clean) or clean[pos] != "{":
                continue
            depth, stop = 1, pos + 1
            while stop < len(clean) and depth:
                if not escaped(clean, stop):
                    depth += (clean[stop] == "{") - (clean[stop] == "}")
                stop += 1
            face_view[match.start():stop] = " " * (stop - match.start())
            if match[1] in TEXT_COMMANDS:
                text_view[match.start():stop] = " " * (stop - match.start())
        text_view, face_view = "".join(text_view), "".join(face_view)
        only_words = re.fullmatch(r"[\s" + CJK + PUNCT + OPEN_PUNCT + CLOSE_PUNCT + r"]+", text_view)
        if only_words and re.search(HAN, text_view):
            self.add("MATH004", start, end, "把普通叙述移出数学环境")
        else:
            for match in re.finditer(HAN + "+", text_view):
                self.add("TEX005", start + match.start(), start + match.end(), "说明文字用 text，字符串用 texttt；普通叙述移出公式")
        for match in re.finditer("[，。；：！？（）]", text_view):
            pos = match.start()
            if not re.search(HAN, text_view[max(0, pos - 1):pos + 2]):
                self.add("TEX006", start + pos, start + pos + 1, "区分公式内部数学标点与公式外中文标点")
        if re.fullmatch(r"\s*(?:BFS|DFS|LIS|STL|Dynamic Programming)\s*", body):
            self.add("MATH004", start, end, "普通算法名移出公式；若有数学变量含义，需可执行规则明确区分", "Warning")
        for match in re.finditer(r"(?<![\\A-Za-z_])(?:log|ln|max|min|gcd|lcm|det|sin|cos|tan|exp|lim)(?![A-Za-z_])|(?<![\\A-Za-z_])[A-Za-z]{2,}(?=\s*\()", face_view):
            if match[0] not in {"O", "dp", "DP"}:
                known = match[0] in FUNCTION_NAMES
                self.add("TEX004", start + match.start(), start + match.end(),
                    "约定函数使用正体；未识别多字母串无法区分函数名和隐式乘积",
                    "Confirmed" if known else "Warning")
        operator_view = text_view
        aligned = bool(re.search(r"\\begin\s*\{(?:align|gather|cases|array|[bpvBV]?matrix)", clean))
        program_patterns = [r"==|!=|:=", r"(?<![A-Za-z])(?:[A-Za-z]+)\.[A-Za-z]+", r"[A-Za-z]+(?:\[[A-Za-z0-9_+\-]+\])+", r"\+=|-=|\*=|/="]
        if not aligned:
            program_patterns.append(r"&&|\|\|")
        for pattern in program_patterns:
            for match in re.finditer(pattern, operator_view):
                self.add("TEX007", start + match.start(), start + match.end(), "赋值、判等、逻辑或分量访问使用相应数学记号")
        for match in re.finditer(r"(?<!\.)\.{3,}(?!\.)|…|⋯|⋮|⋱", text_view):
            self.add("TEX008", start + match.start(), start + match.end(), "使用 dots、cdots、ldots、vdots 或 ddots 命令")
        for match in re.finditer(r"[_^]([A-Za-z0-9]{2,})", text_view):
            if not escaped(text_view, match.start()):
                self.add("TEX011", start + match.start(), start + match.end(), "多个字符是否应属于同一上下标不能静态确定，核对分组", "Warning")
        for match in re.finditer(r"(?<![A-Za-z0-9])\d{6,}(?![A-Za-z0-9])", text_view):
            if text_view[max(0, match.start() - 2):match.start()].endswith(("^", "^{")):
                continue
            self.add("TEX012", start + match.start(), start + match.end(), "大数字是否需要科学计数法未有统一数值阈值，不能仅按位数断言违规", "Warning")
        equals, separators = [], []
        depth = 0
        for index, char in enumerate(text_view):
            if escaped(text_view, index):
                continue
            if char in "{([":
                depth += 1
            elif char in "})]":
                depth = max(0, depth - 1)
            elif char in ",;，；" and depth == 0:
                separators.append(index)
            elif char == "=" and depth == 0 and text_view[max(0, index - 1):index] not in ("<", ">", "=", "!", ":") and text_view[index + 1:index + 2] != "=":
                equals.append(index)
        if len(equals) >= 2 and not aligned and not any(equals[0] < p < equals[-1] for p in separators) and not re.search(r"\\\\", text_view[equals[0] + 1:equals[-1]]):
            self.add("TEX010", start, end, "把连等推导整理到 aligned 等对齐环境")
        self.complexity(text_view, start)
        prefix = self.source[max(0, start - 24):start].rstrip("$ \\(")
        if re.search(r"(?:更新|初始化|置)[ \t]*$", prefix):
            self.assignment(text_view, start)

    def tex_arguments(self, clean, commands, start, syntax_kind):
        """Check simple required arguments, deferring macro/compound expansion.

        This is a bounded token/group check, not a complete TeX interpreter.
        Balanced groups and atomic arguments are accepted. Unbraced commands
        taking arguments are deferred because expansion can change consumption.
        """
        groups, stack = {}, []
        for pos, char in enumerate(clean):
            if escaped(clean, pos):
                continue
            if char == "{":
                stack.append(pos)
            elif char == "}" and stack:
                groups[stack.pop()] = pos + 1
        command_at = {match.start(): match for match in commands}
        argument_positions = [match.start() for match in commands if match[1] in TEX_ARGUMENTS]

        def next_pos(pos):
            match = NON_SPACE.search(clean, pos)
            return match.start() if match else len(clean)

        def token(pos):
            pos = next_pos(pos)
            if pos == len(clean) or clean[pos] in "}&^_#" or clean.startswith(r"\\", pos):
                return pos, "missing"
            if clean[pos] == "{":
                return groups.get(pos, len(clean)), "ok" if pos in groups else "unclosed"
            if clean[pos] == "\\":
                match = command_at.get(pos)
                if match:
                    name = match[1]
                    if name in {"end", "right", "cr", "hline"}:
                        return pos, "missing"
                    if name in TEX_ARGUMENTS or name in DELIMITER_COMMANDS or name == "begin":
                        return match.end(), "uncertain"
                    return match.end(), "ok" if name in TEX_COMMANDS else "uncertain"
                return min(pos + 2, len(clean)), "ok" if pos + 1 < len(clean) else "missing"
            return pos + 1, "ok"

        def report(match, message, kind=syntax_kind, category=None):
            self.add("TEX015", start + match.start(), start + match.end(), message, kind, category=category)

        for match in commands:
            name, pos = match[1], match.end()
            if name in DELIMITER_COMMANDS:
                pos = next_pos(pos)
                delimiter = command_at.get(pos)
                if pos == len(clean) or clean[pos] not in ".()[]|/<>" and not (
                    clean[pos:pos + 2] in (r"\{", r"\}", r"\|") or
                    delimiter and delimiter[1] in DELIMITER_SYMBOLS):
                    report(match, "定界命令后需要合法定界符；复杂宏提供的定界保留核验",
                           "Warning" if delimiter or syntax_kind == "Warning" else "Confirmed", "math_delimiter")
                continue
            if name in {"begin", "end"}:
                env = re.match(r"\s*\{([^{}]+)\}", clean[pos:])
                if not env:
                    if next_pos(pos) == len(clean):
                        report(match, "begin/end 缺少环境名称参数")
                    else:
                        report(match, "环境名称参数的语法未获验证", "Warning")
                    continue
                if name == "end" or env[1] not in {"array", "alignedat", "alignat", "alignat*"}:
                    continue
                pos = next_pos(pos + env.end())
                if pos < len(clean) and clean[pos] == "[":
                    # Optional alignment parameters vary across renderers.
                    report(match, "环境可选参数及其后的必要参数需要结合渲染支持核验", "Warning")
                    continue
                if pos >= len(clean) or clean[pos] != "{":
                    report(match, "此环境缺少必要的列格式或对齐组数参数")
                elif pos in groups:
                    parameter = clean[pos + 1:groups[pos] - 1].strip()
                    valid = (bool(re.fullmatch(r"[lcr|: ]+", parameter)) and bool(re.search(r"[lcr]", parameter))) if env[1] == "array" else bool(re.fullmatch(r"[1-9][0-9]*", parameter))
                    if not valid:
                        report(match, "环境参数为空或超出简单列格式／正整数组数的已验证范围", "Warning")
                continue
            if name not in TEX_ARGUMENTS:
                continue
            if name == "operatorname" and clean[pos:pos + 1] == "*":
                pos += 1
            if name == "sqrt":
                pos = next_pos(pos)
                if pos < len(clean) and clean[pos] == "[":
                    index, status = pos + 1, "missing"
                    while index < len(clean):
                        if clean[index] == "{" and not escaped(clean, index):
                            if index not in groups:
                                status = "unclosed"
                                break
                            index = groups[index]
                            continue
                        if clean[index] == "]" and not escaped(clean, index):
                            pos, status = index + 1, "ok"
                            if bisect.bisect_left(argument_positions, index) > bisect.bisect_right(argument_positions, match.end()):
                                report(match, "根号指标含复合命令，取参边界需要结合上下文核验", "Warning")
                            break
                        if clean[index] == "[" and not escaped(clean, index):
                            status = "uncertain"
                            break
                        index += 1
                    if status != "ok":
                        if status != "unclosed":
                            report(match, "根号可选指标未闭合或使用未验证的嵌套语法",
                                   "Warning" if status == "uncertain" else syntax_kind)
                        continue
            for _ in range(TEX_ARGUMENTS[name]):
                pos, status = token(pos)
                if status != "ok":
                    if status == "missing":
                        report(match, "命令缺少必要参数；可用分组或合法单 token 参数")
                    elif status == "uncertain":
                        report(match, "无分组的复合命令参数需要核验展开和取参范围", "Warning")
                    # An unclosed group is already a TEX002 occurrence.
                    break

    def assignment(self, text, start):
        match = re.match(r"[ \t]*[A-Za-z][A-Za-z0-9_{}]*(?:\[[^\]\n]+\])*[ \t]*(?<![<>=!:])=(?!=)", text)
        if match:
            pos = start + match.end() - 1
            self.add("TEX007", pos, pos + 1, "明确的更新或初始化赋值使用 gets 或 to，定义和条件等式不套用此规则")

    def fragmented_math(self):
        run = []
        operators = re.compile(r"\s*(?:[+*/=<>≤≥≠×÷-]|\\(?:leq?|geq?|neq?|times|cdot|div|bmod|equiv))\s*")

        def finish(tokens):
            if len(tokens) >= 3 and any(operators.fullmatch(t[3]) for t in tokens):
                if not operators.fullmatch(tokens[0][3]) and not operators.fullmatch(tokens[-1][3]):
                    self.add("MATH005", tokens[0][0], tokens[-1][1],
                        "相邻环境通过独立运算符连接，把整条运算式合并到一个数学环境")

        for token in sorted(self.inline_tokens):
            if token[2] != "math":
                finish(run)
                run = []
                continue
            if run and not re.fullmatch(r"[ \t]*", self.source[run[-1][1]:token[0]]):
                finish(run)
                run = []
            run.append(token)
        finish(run)

    def complexity(self, text, start, mapping=None):
        for match in re.finditer(r"(?<![A-Za-z])O\s*\(", text):
            pos = match.end()
            front = re.match(r"\s*\d+(?:\.\d+)?\s*(?:(?:\\(?:cdot|times)|\*)\s*)?(?=[A-Za-z\\(])", text[pos:])
            if front:
                a, b = start + match.start(), start + pos + front.end()
                if mapping is not None:
                    a, b = mapping[0][a], mapping[1][b - 1]
                self.add("TEX009", a, b, "复杂度中删去固定乘法因子；操作次数推导可保留常数")

    def prose(self):
        view = self.masked_text()
        for match in re.finditer("(?=(" + HAN + LATIN + "|" + LATIN + HAN + "))", view):
            start, end = match.span(1)
            self.add("TXT001", start, end, "在中英文或中文数字边界补半角空格", occurrence=start + 1)
        self.inline_boundaries(view)
        for pattern in (HAN + r"[,;:!?](?![/:;!?])", HAN + r"\.(?![.A-Za-z0-9])"):
            for match in re.finditer(pattern, view):
                self.add("TXT002", match.start() + 1, match.end(), "替换为相应全角中文标点")
        for match in re.finditer(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]+", view):
            self.add("TXT004", match.start(), match.end(), "全角英数字的用途不能静态确认", "Warning")
        for match in re.finditer(HAN + "\u3000+" + HAN, view):
            self.add("TXT004", match.start() + 1, match.end() - 1, "删除中文词内全角空格", category="extra_space")
        # Masks preserve offsets. A protected inline token can still border punctuation.
        for match in re.finditer(r"[ \t]+", view):
            start, end = match.span()
            row, _ = self.location(start)
            line_start = self.starts[row - 1]
            if not view[line_start:start].strip() or end == len(view) or view[end] in "\r\n":
                continue
            before, after = view[start - 1], view[end]
            if row in self.tables and ((before == "|" and not escaped(self.source, start - 1)) or (after == "|" and not escaped(self.source, end))):
                continue
            reason = None
            if after in PUNCT + CLOSE_PUNCT + OPEN_PUNCT:
                reason = "删除中文标点旁的多余空格"
            elif before in PUNCT + OPEN_PUNCT + CLOSE_PUNCT and (re.fullmatch(HAN + "|" + LATIN, after) or after == "\0"):
                reason = "删除中文标点旁的多余空格"
            elif end - start > 1 and ((re.fullmatch(HAN, before) and (re.fullmatch(LATIN, after) or after == "\0")) or (re.fullmatch(HAN, after) and (re.fullmatch(LATIN, before) or before == "\0"))):
                reason = "边界只保留一个半角空格"
            if reason:
                self.add("TXT003", start, end, reason, occurrence=start)
            elif re.fullmatch(HAN, before) and re.fullmatch(HAN, after):
                self.add("TXT003", start, end, "中文词内空格是否有必要无法静态确认", "Warning", occurrence=start)
        # Match concrete mathematical syntax, not all ordinary English/digits.
        spans = []
        for match in re.finditer(r"(?<![A-Za-z])O\s*\(", view):
            stop = balanced_end(view, match.end() - 1)
            if stop:
                spans.append((match.start(), stop))
                self.complexity(view[match.start():stop], match.start())
        for pattern in BARE_MATH_PATTERNS:
            spans.extend(m.span() for m in re.finditer(pattern, view))
        # Contained matches are not extra occurrences of the same mathematical phrase.
        for start, end in merged_ranges(spans):
            kind = bare_math_kind(view[start:end])
            self.add("MATH003", start, end, "把该数学表达式放入同一 LaTeX 环境" if kind == "Confirmed" else
                     "带下划线的多字母名字可能是标识符或普通名称，需要核验用途", kind)
        for match in re.finditer(r"\\(?:sum|prod|frac|sqrt|log|max|min|geq|leq|Rightarrow)\b", view):
            self.add("MATH003", match.start(), match.end(), "区分作为文本讲解的命令和缺少定界的数学表达式", "Warning")
        for match in re.finditer(r"(?:更新|初始化|置)[ \t]+(?=[A-Za-z])", view):
            context = self.source[max(0, match.start() - 12):match.start()]
            if not re.search(r"代码|语句|字符串|输入|输出|命令", context):
                self.assignment(view[match.end():], match.end())
        for match in re.finditer(r"(?m)^[ \t]*×[ \t]*\n[ \t]*×", view):
            self.add("TEX007", match.start(), match.end(), "两个相邻的乘号之间缺少操作数，修正重复的运算符")
        # Dense alternating emphasis is a lead, not a word-count style conviction.
        for row, line in enumerate(source_lines(view), 1):
            if self.kinds.get(row) not in ("prose", "list"):
                continue
            if len(re.findall(r"\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)", line)) >= 5:
                start = self.starts[row - 1]
                self.add("MD012", start, start + len(line), "密集强调的作用未验证，不能仅按次数证实滥用", "Warning")

    def projected_view(self, view=None):
        # Remove *paired* presentation delimiters only for checking text edges.
        # Code/formula interiors stay opaque; a token represents their boundary.
        view = self.masked_text() if view is None else view
        projected = list(view)
        for match in re.finditer(r"(\*\*|__|\*|_|~~)(?=\S)([^\r\n]+?)(?<=\S)\1", view):
            size = len(match[1])
            closing = match.end() - size
            if escaped(self.source, match.start()) or escaped(self.source, closing):
                continue
            if not delimiter_flanking(self.source, match.start(), size)[0] or not delimiter_flanking(self.source, closing, size)[1]:
                self.add("MD014", match.start(), match.end(),
                         "此成对标记按当前模型未形成强调，字面符号或强调用途不能确认", "Warning")
                continue
            projected[match.start():match.start() + size] = "\0" * size
            projected[match.end() - size:match.end()] = "\0" * size
        for start, end, kind, content in self.inline_tokens:
            projected[start] = MATH_TOKEN if kind == "math" else (CODE_TOKEN if kind == "code" and re.match(LATIN, content) else OTHER_TOKEN)
        self.projection_spans = {}
        reference_view = "".join(projected)
        for match in CHAR_REFERENCE.finditer(reference_view):
            spelling = match[0]
            literal = escaped(self.source, match.start())
            if literal:
                decoded = OTHER_TOKEN
            elif re.fullmatch(r"&#(?:[0-9]{1,7}|[xX][0-9A-Fa-f]{1,6});", spelling):
                decoded = html.unescape(spelling)
            elif not spelling.startswith("&#"):
                decoded = html.entities.html5.get(spelling[1:])
            else:
                decoded = None
            if decoded is None:
                self.unverified_projection_scope(match.start(), match.end(), "未识别的字符引用，其字面显示和用途未获验证")
                decoded = OTHER_TOKEN
            # Character references do not create Markdown source line breaks.
            decoded = decoded.replace("\r", " ").replace("\n", " ")
            if not literal and any(c in ("\0", MATH_TOKEN, CODE_TOKEN, OTHER_TOKEN, "\ufffd") or unicodedata.category(c) in {"Cc", "Cf", "Cs", "Cn"} and c != "\t" for c in decoded):
                self.unverified_projection_scope(match.start(), match.end(), "字符引用包含替换、控制或未验证字符")
                decoded = OTHER_TOKEN
            projected[match.start():match.end()] = list(decoded) + ["\0"] * (len(spelling) - len(decoded))
            for pos in range(match.start(), match.start() + len(decoded)):
                self.projection_spans[pos] = (match.start(), match.end())
        for pos, char in enumerate(projected):
            if char == "\0" or char in (MATH_TOKEN, CODE_TOKEN, OTHER_TOKEN, "\t", "\r", "\n"):
                continue
            if (ord(char) < 32 or ord(char) > 127) and unicodedata.category(char) in {"Cc", "Cf", "Cs", "Cn"}:
                a, b = self.projection_spans.get(pos, (pos, pos + 1))
                self.unverified_projection_scope(a, b, "正文含不可见控制或未验证字符，实际显示未获验证")
                projected[pos] = OTHER_TOKEN
        return "".join(projected)

    def unverified_projection_scope(self, start, end, reason):
        if start not in self.unverified_projection:
            self.unverified_projection.add(start)
            self.skip(start, end, reason, True, mask=False)

    def inline_boundaries(self, view):
        projected = self.projected_view(view)
        chars, positions, ends = [], [], []
        for pos, char in enumerate(projected):
            if char != "\0":
                chars.append(char)
                a, b = self.projection_spans.get(pos, (pos, pos + 1))
                positions.append(a)
                ends.append(b)
        text = "".join(chars)
        for index in range(len(text) - 1):
            left, right = text[index:index + 2]
            left_han, right_han = bool(re.fullmatch(HAN, left)), bool(re.fullmatch(HAN, right))
            left_foreign = bool(re.fullmatch(LATIN, left)) or left in (MATH_TOKEN, CODE_TOKEN)
            right_foreign = bool(re.fullmatch(LATIN, right)) or right in (MATH_TOKEN, CODE_TOKEN)
            if not (left_han and right_foreign or left_foreign and right_han):
                continue
            a, b = positions[index:index + 2]
            boundary = ends[index] if left_han else b
            rule = "MATH001" if MATH_TOKEN in (left, right) else "TXT001"
            self.add(rule, a, ends[index + 1], "在可见中文与英文、代码或公式边界补半角空格", occurrence=boundary)
        for match in re.finditer(r"[,;:!?]|\.(?![.A-Za-z0-9])", text):
            index = match.start()
            left = text[index - 1:index]
            right = text[index + 1:].lstrip(" \t")[:1]
            row, _ = self.location(positions[index])
            line = projected[self.starts[row - 1]:self.starts[row] if row < len(self.starts) else len(projected)]
            if re.fullmatch(HAN, left) or re.fullmatch(HAN, right) or (left in (MATH_TOKEN, CODE_TOKEN) and re.search(HAN, line)):
                pos = positions[index]
                self.add("TXT002", pos, ends[index], "中文叙述中，可见文字、公式或代码后的标点同样使用相应全角标点")
        for match in re.finditer(r"[^\S\r\n]+", text):
            a, b = match.span()
            left, right = text[a - 1:a], text[b:b + 1]
            start, stop = positions[a], ends[b - 1]
            row, _ = self.location(start)
            padding = row in self.tables and ((left == "|" and not escaped(self.source, positions[a - 1])) or (right == "|" and not escaped(self.source, positions[b])))
            if padding:
                continue
            in_line = bool(left and right and left not in "\r\n" and right not in "\r\n")
            punctuation_gap = in_line and (right in PUNCT + OPEN_PUNCT + CLOSE_PUNCT or left in PUNCT + OPEN_PUNCT + CLOSE_PUNCT)
            repeated_gap = in_line and b - a > 1 and ((re.fullmatch(HAN, left) and (re.fullmatch(LATIN, right) or right in (MATH_TOKEN, CODE_TOKEN))) or (re.fullmatch(HAN, right) and (re.fullmatch(LATIN, left) or left in (MATH_TOKEN, CODE_TOKEN))))
            fullwidth_word_gap = in_line and "\u3000" in match[0] and re.fullmatch(HAN, left) and re.fullmatch(HAN, right)
            if punctuation_gap or repeated_gap or fullwidth_word_gap:
                self.add("TXT004" if fullwidth_word_gap else "TXT003", start, stop,
                         "删除可见标点旁或中文词内多余空格，边界只保留一个半角空格", category="extra_space")
            elif in_line and re.fullmatch(HAN, left) and re.fullmatch(HAN, right):
                left_links = {label_start for label_start, label_end in self.link_labels if label_start <= positions[a - 1] < label_end}
                right_links = {label_start for label_start, label_end in self.link_labels if label_start <= positions[b] < label_end}
                if left_links == right_links:
                    self.add("TXT003", start, stop, "中文词内空格是否有必要无法静态确认", "Warning")
            elif any(c != " " for c in match[0]):
                self.add("TXT004", start, stop, "正文中的特殊空白用途未验证；必要缩进和代码空白不套用此规则", "Warning")
        for match in re.finditer(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]+", text):
            a, b = match.span()
            if any(positions[n] != ends[n] - 1 for n in range(a, b)):
                self.add("TXT004", positions[a], ends[b - 1], "字符引用显示为全角英数字，其用途不能静态确认", "Warning")
        if self.projection_spans:
            spans = [m.span() for pattern in BARE_MATH_PATTERNS for m in re.finditer(pattern, text)]
            for match in re.finditer(r"(?<![A-Za-z])O\s*\(", text):
                end = balanced_end(text, match.end() - 1)
                if end is not None:
                    spans.append((match.start(), end))
            for a, b in merged_ranges(spans):
                if any(ends[n] - positions[n] > 1 for n in range(a, b)):
                    kind = bare_math_kind(text[a:b])
                    self.add("MATH003", positions[a], ends[b - 1], "字符引用显示为数学表达式，使用同一 LaTeX 环境" if kind == "Confirmed" else
                             "字符引用显示为带下划线的多字母名字，需要核验用途", kind)
            self.complexity(text, 0, mapping=(positions, ends))

    @staticmethod
    def sentence_shape(text):
        text = text.replace("\0", "").strip()
        text = re.sub(r"\s+", " ", text)
        # Earlier complete sentences do not complete the final fragment.
        text = re.split(r"[。！？；：]", text)[-1].strip()
        if len(re.findall(HAN, text)) < 5:
            return False
        if text.endswith(("可以", "需要", "能够", "将", "为", "表示", "得到", "等于", "即", "则", "如果", "因为", "比如", "例如", "的", "以及", "或者", "并且")):
            return False
        if text.endswith("通过") and not re.match(r"希望|请", text):
            return False
        # A conditional fragment is not a complete sentence merely because it
        # contains a keyword; e.g. a broken formula after '如果'.
        if re.match(r"因为|如果|若|当", text) and not re.search(r"所以|则|直接|返回|否则|那么|可以|需要", text):
            return False
        return bool(re.search(
            r"(?:我们|本文|本题|本节|这里|算法|答案|结果|复杂度).*(?:是|为|需要|可以|可不|得到|等于|表示|使用|采用|输出|计算)"
            r"|(?:所以|因此|从而).+"
            r"|(?:若|如果).*(?:则|直接|返回|否则|那么).+"
            r"|(?:定义|记|设).*(?:为|表示).+"
            r"|^(?:BFS|DFS|DP|LIS|ST).*(?:是|为|需要|可以|得到|表示|使用).+"
            r"|^给定.+(?:要求|计算|输出|求出).+"
            r"|^(?:希望|请|建议).{3,}(?:通过|注意|使用|采用|计算|输出|返回|检查|阅读|理解)", text))

    def paragraphs(self):
        lines = source_lines(self.source, keepends=True)
        view_lines = source_lines(self.projected_view(), keepends=True)
        opaque_rows = {row for scope in self.skipped if scope.get("unverified")
                       for row in range(scope["line"], scope["end_line"] + 1)}
        current = []
        paragraphs = []
        for row, (raw, visible) in enumerate(zip(lines, view_lines), 1):
            kind = self.kinds.get(row)
            if not raw.strip() or kind not in ("prose", "list") or row in self.tables or row in opaque_rows or not visible.replace("\0", "").strip():
                if current:
                    paragraphs.append(current)
                    current = []
                continue
            if kind == "list" and current:
                paragraphs.append(current)
                current = []
            if current and self.quote_levels.get(row) != self.quote_levels.get(current[-1]):
                paragraphs.append(current)
                current = []
            if current:
                prev_row = current[-1]
                previous = lines[prev_row - 1].rstrip("\r\n")
                backslashes = len(previous) - len(previous.rstrip("\\"))
                if not previous.endswith("  ") and backslashes % 2 == 0:
                    left = view_lines[prev_row - 1].replace("\0", "").rstrip()[-1:]
                    right = visible.replace("\0", "").lstrip()[:1]
                    bad_gap = (left in PUNCT + OPEN_PUNCT + CLOSE_PUNCT and bool(right)) or bool(right and right in PUNCT + OPEN_PUNCT + CLOSE_PUNCT)
                    self.add("TXT006", self.starts[row - 1] - 1, self.starts[row - 1],
                        "按 CommonMark 空白模型，单换行在中文标点旁产生多余空格；改为分段或硬换行" if bad_gap else
                        "此单换行在 CommonMark 模型中成为段内空白；断行意图不能静态确认",
                        "Confirmed" if bad_gap else "Warning",
                        evidence={"render_model": RENDER_MODEL, "rendered_gap": " ",
                                  "left": {MATH_TOKEN: "<inline_math>", CODE_TOKEN: "<inline_code>", OTHER_TOKEN: "<inline_literal>"}.get(left, left),
                                  "right": {MATH_TOKEN: "<inline_math>", CODE_TOKEN: "<inline_code>", OTHER_TOKEN: "<inline_literal>"}.get(right, right)})
            current.append(row)
        if current:
            paragraphs.append(current)
        terminal = "。！？；：.!?;:…"
        for rows in paragraphs:
            first, last = rows[0], rows[-1]
            visible = "".join(view_lines[n - 1] for n in rows)
            if not re.search(HAN, visible):
                continue
            plain = visible.replace("\0", "").rstrip()
            plain = re.sub(r"[”’）》〉】〕」』]+$", "", plain).rstrip()
            if not plain or plain[-1] in terminal:
                continue
            label = r"(?:算法思路|正确性(?:证明)?|(?:时间|空间)?复杂度|前置知识|代码讲解|参考实现|基本框架|实现方式)"
            if re.fullmatch(label + r"(?:[与和]" + label + r")*", plain.strip()):
                continue
            # Short labels and noun-only list entries are not assumed to be sentences.
            chinese = "".join(re.findall(HAN, visible))
            sentence = self.sentence_shape(visible)
            if len(chinese) < 7 and not sentence:
                continue
            pos = self.starts[last - 1] + len(lines[last - 1].rstrip())
            self.add("TXT005", max(self.starts[last - 1], pos - 1), pos,
                "完整语句补句末标点；短语或说明标签的意图不明确时不声称已证实", "Confirmed" if sentence else "Warning")
        for start, end, _, _content_end, _folded in self.code_spans:
            row, _ = self.location(start)
            # An orphaned language label is not itself treated as a format rule.
            self.kinds[row] = "code"

    def run(self):
        self.blocks()
        self.structure()
        self.inline()
        self.fragmented_math()
        self.prose()
        self.paragraphs()
        self.findings.sort(key=lambda f: (f["line"], f["column"], f["rule_id"]))
        assessment = format_assessment(self.findings, self.skipped)
        result = {"file": self.filename, "findings": self.findings, "skipped": self.skipped,
            "linter_version": LINTER_VERSION, "render_model": RENDER_MODEL,
            "sha256": hashlib.sha256(self.source.encode("utf-8")).hexdigest(),
            "format_assessment": assessment}
        result["review_candidates"] = review_candidates(result)
        return result


def lint_text(source, filename="<memory>"):
    return Scanner(source, filename).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="仅检查已有 Python 3.8+ 环境")
    parser.add_argument("--rules", action="store_true", help="输出规则及规范类别，不扫描稿件")
    parser.add_argument("--decisions", type=Path, help="合并当前源码上的 LLM 复核 JSON；不调用模型")
    parser.add_argument("files", nargs="*", type=Path, help="UTF-8 Markdown 源文件")
    args = parser.parse_args(argv)
    supported = sys.version_info >= (3, 8)
    result = {"schema_version": VERSION, "status": "ok" if supported else "error",
        "linter_version": LINTER_VERSION, "render_model": RENDER_MODEL,
        "python": sys.version.split()[0], "supported": supported, "findings": [],
        "skipped": [], "errors": [], "files_checked": [], "files": [], "review_candidates": [],
        "effective_findings": [], "effective_skipped": [], "decisions_applied": False,
        "format_assessment": {"verdict": "not_assessed", "groups": [], "format_deduction": None}}
    if not supported:
        result["errors"].append({"message": "需要已有 Python 3.8+；不安装运行时"})
    elif args.decisions and (args.rules or args.check):
        result["errors"].append({"message": "--decisions 只能与源码扫描合用"})
    elif args.rules:
        result["rules"] = [{"rule_id": r, "category": c, "standard": s} for r, (c, s) in RULES.items()]
    elif args.check:
        pass
    elif not args.files:
        result["errors"].append({"message": "未提供 Markdown 源文件"})
    else:
        # Repeating a file argument does not create new physical error occurrences.
        seen_paths, scans, sources = set(), [], {}
        for path in args.files:
            try:
                canonical = str(path.resolve())
                if canonical in seen_paths:
                    continue
                seen_paths.add(canonical)
                if path.suffix.lower() not in (".md", ".markdown", ".mdown", ".mkd"):
                    raise ValueError("只接受 Markdown 源文件；PDF、截图不能假装完成源码格式审核")
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    source = stream.read()
                scanned = lint_text(source, canonical)
            except (OSError, UnicodeError, ValueError, RuntimeError) as error:
                result["errors"].append({"file": str(path), "message": str(error)})
                continue
            result["files_checked"].append(canonical)
            scans.append(scanned)
            sources[canonical] = source
            result["findings"].extend(scanned["findings"])
            result["skipped"].extend(scanned["skipped"])
            result["review_candidates"].extend(scanned["review_candidates"])
        merged = {}
        if args.decisions:
            try:
                merged = load_format_decisions(args.decisions, scans, sources)
                result["decisions_applied"] = True
            except (OSError, UnicodeError, ValueError, RecursionError) as error:
                result["errors"].append({"file": str(args.decisions), "message": "复核记录未应用：" + str(error)})
        for scanned in scans:
            scanned["static_format_assessment"] = scanned["format_assessment"]
            if scanned["file"] in merged:
                scanned.update(merged[scanned["file"]])
            else:
                scanned["effective_findings"] = scanned["findings"]
                scanned["effective_skipped"] = scanned["skipped"]
            summary = {key: scanned[key] for key in ("file", "sha256", "static_format_assessment", "format_assessment")}
            if scanned["file"] in merged:
                summary.update({key: scanned[key] for key in ("adjudications", "additional_findings")})
            result["files"].append(summary)
            result["effective_findings"].extend(scanned["effective_findings"])
            result["effective_skipped"].extend(scanned["effective_skipped"])
        result["format_assessment"] = format_assessment(result["effective_findings"], result["effective_skipped"], result["errors"])
    if result["errors"]:
        result["status"] = "partial" if result["files_checked"] else "error"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
