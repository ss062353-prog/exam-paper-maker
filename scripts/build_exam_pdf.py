#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spec-driven printable exam builder, checker and verifier (schema v2).

Commands
--------
    python build_exam_pdf.py --spec paper.json --check-spec
    python build_exam_pdf.py --spec paper.json --verify
    python build_exam_pdf.py --spec paper.json --out out/paper.pdf

Schema v2 adds per-question metadata (id / points / difficulty / topic /
answer / rubric / numeric_check / math / figures), automated answer generation,
diagnosis tables, markup sanitisation and stricter verification.
Schema v1 specs (no metadata) still render; checks degrade to warnings.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import sys
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

try:  # optional: only needed for --verify
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:  # optional: font embedding inspection
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:  # image dimensions (reportlab uses Pillow for raster images anyway)
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover
    PILImage = None

PAGE_SIZES = {"A4": A4, "LETTER": LETTER}
DIFFICULTIES = ("basic", "medium", "challenge")
DIFFICULTY_ZH = {"basic": "基础", "medium": "中等", "challenge": "挑战"}
ALLOWED_TAGS = {"b", "i", "u", "super", "sub", "br"}

DEFAULT_FONTS = [
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
DEFAULT_BOLD_FONTS = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyhbd.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

SAFE_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log,
    "log10": math.log10, "abs": abs, "floor": math.floor, "ceil": math.ceil,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
}


class Fonts:
    def __init__(self) -> None:
        self.body = "Helvetica"
        self.bold = "Helvetica-Bold"
        self.embedded = False


def _try_register(name: str, path: str | None) -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        if path.lower().endswith(".ttc"):
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
        else:
            pdfmetrics.registerFont(TTFont(name, path))
        return True
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("WARN: cannot load font %s (%s)\n" % (path, exc))
        return False


def register_fonts(font_path: str | None = None, bold_path: str | None = None) -> Fonts:
    f = Fonts()
    body_candidates = [font_path, os.environ.get("EXAM_PAPER_FONT")] + DEFAULT_FONTS
    bold_candidates = [bold_path, os.environ.get("EXAM_PAPER_FONT_BOLD")] + DEFAULT_BOLD_FONTS
    body = next((p for p in body_candidates if _try_register("ExamBody", p)), None)
    bold = next((p for p in bold_candidates if _try_register("ExamBold", p)), None)
    if body:
        f.body = "ExamBody"
        f.bold = "ExamBold" if bold else "ExamBody"
        pdfmetrics.registerFontFamily("ExamBody", normal=f.body, bold=f.bold,
                                      italic=f.body, boldItalic=f.bold)
        f.embedded = True
        return f
    cid = os.environ.get("EXAM_PAPER_CID_FONT", "STSong-Light")
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(cid))
        f.body = f.bold = cid
        sys.stderr.write("WARN: no TTF CJK font found; using non-embedded CID font %r\n" % cid)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("WARN: no CJK font available (%s)\n" % exc)
    return f


def sanitize_markup(text: str, allow_raw: bool = False) -> str:
    """Allow only emphasis tags; escape anything else (blocks <img>, <a>, <font>)."""
    if allow_raw or not isinstance(text, str):
        return text

    def repl(match: re.Match) -> str:
        tag = match.group(1).lower()
        if tag in ALLOWED_TAGS:
            return match.group(0)
        return match.group(0).replace("<", "&lt;").replace(">", "&gt;")

    return re.sub(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>", repl, text)


def make_styles(fonts: Fonts) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("t", fontName=fonts.bold, fontSize=16, leading=22,
                                alignment=TA_CENTER),
        "sub": ParagraphStyle("s", fontName=fonts.body, fontSize=9, leading=14,
                              alignment=TA_CENTER, textColor=colors.HexColor("#444444")),
        "h": ParagraphStyle("h", fontName=fonts.bold, fontSize=12, leading=18,
                            spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("b", fontName=fonts.body, fontSize=10.5, leading=17),
        "opt": ParagraphStyle("o", fontName=fonts.body, fontSize=10.5, leading=16, leftIndent=16),
        "note": ParagraphStyle("n", fontName=fonts.body, fontSize=9, leading=14,
                               textColor=colors.HexColor("#333333")),
        "info": ParagraphStyle("i", fontName=fonts.body, fontSize=10.5, leading=20, spaceAfter=4),
        "ans": ParagraphStyle("a", fontName=fonts.body, fontSize=9.5, leading=15, spaceAfter=2),
        "cell": ParagraphStyle("c", fontName=fonts.body, fontSize=9, leading=13),
        "math": ParagraphStyle("m", fontName=fonts.body, fontSize=10.5, leading=15,
                               alignment=TA_CENTER),
    }


def p(text: str, styles: dict, style: str = "body") -> Paragraph:
    return Paragraph(text, styles[style])


def make_table(rows, widths_cm, styles, usable_cm):
    total = sum(widths_cm)
    if total > usable_cm:
        sys.stderr.write("WARN: table widths %.1fcm > usable %.1fcm; scaling down\n"
                         % (total, usable_cm))
        widths_cm = [w * usable_cm / total for w in widths_cm]
    t = Table([[p(str(c), styles, "cell") for c in r] for r in rows],
              colWidths=[w * cm for w in widths_cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def make_fraction(spec: dict, styles: dict) -> Table:
    """Render a fraction with optional limit prefix and suffix (no LaTeX needed)."""
    num = p(sanitize_markup(str(spec.get("num", ""))), styles, "math")
    den = p(sanitize_markup(str(spec.get("den", ""))), styles, "math")
    frac = Table([[num], [den]], colWidths=[3.0 * cm])
    frac.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.7, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    cells, widths = [], []
    if spec.get("apply"):
        cells.append(p(sanitize_markup(spec["apply"]), styles, "math"))
        widths.append(2.2 * cm)
    cells.append(frac)
    widths.append(3.0 * cm)
    if spec.get("suffix"):
        cells.append(p(sanitize_markup(spec["suffix"]), styles, "math"))
        widths.append(3.0 * cm)
    outer = Table([cells], colWidths=widths)
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return outer


def make_figure(fig: dict, asset_root: str, usable_cm: float) -> Image:
    raw = fig["path"]
    path = raw if os.path.isabs(raw) else os.path.join(asset_root, raw)
    path = os.path.realpath(path)
    if not path.startswith(os.path.realpath(asset_root) + os.sep) and path != os.path.realpath(asset_root):
        raise ValueError("figure path escapes asset root: %s" % raw)
    if not os.path.exists(path):
        raise FileNotFoundError("figure not found: %s" % raw)
    width_cm = min(float(fig.get("width_cm", 10)), usable_cm)
    width_pt = width_cm * cm
    height_pt = None
    if PILImage is not None:
        with PILImage.open(path) as im:
            iw, ih = im.size
        height_pt = width_pt * ih / iw
    return Image(path, width=width_pt, height=height_pt)


def eval_expr(expr: str, x: float) -> float:
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id == "x":
                return x
            if node.id in ("pi", "e"):
                return getattr(math, node.id)
            raise ValueError("name not allowed: %s" % node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult,
                                                                ast.Div, ast.Pow, ast.Mod)):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Pow):
                return a ** b
            return a % b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = SAFE_FUNCS.get(node.func.id)
            if not fn or node.keywords:
                raise ValueError("function not allowed: %s" % node.func.id)
            return fn(*[ev(a) for a in node.args])
        raise ValueError("unsupported expression element: %s" % type(node).__name__)

    return ev(tree)


def iter_items(spec: dict) -> Iterable[dict]:
    for sec in spec.get("sections", []):
        for item in sec.get("items", []):
            yield item


def check_spec(spec: dict, asset_root: str) -> tuple[list[str], list[str]]:
    """Structural + arithmetic checks. Returns (errors, warnings)."""
    errors, warnings = [], []
    v2 = int(spec.get("schema_version", 1)) >= 2
    if not v2:
        warnings.append("schema_version < 2: per-question checks skipped")

    items = list(iter_items(spec))
    if not items:
        errors.append("no items found in sections")
        return errors, warnings

    meta = spec.get("meta") or {}

    def check_sources(sources, where):
        for s in sources or []:
            url = str(s.get("url", ""))
            acc = str(s.get("accessed", ""))
            quote = str(s.get("quote", "")).strip()
            if not re.match(r"^https?://", url):
                errors.append("%s: invalid source url %r" % (where, url))
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", acc):
                errors.append("%s: source accessed date must be YYYY-MM-DD (got %r)" % (where, acc))
            if len(quote) < 10:
                errors.append("%s: source quote (>=10 chars) is required" % where)

    check_sources(meta.get("sources"), "meta.sources")
    total = meta.get("total_points")
    if v2 and total is None:
        errors.append("meta.total_points is required for schema v2")
    pts = [it.get("points") for it in items]
    if v2 and any(not isinstance(x, (int, float)) or x <= 0 for x in pts):
        errors.append("every item needs a positive numeric points value")
    elif v2 and total is not None and abs(sum(pts) - total) > 1e-6:
        errors.append("points sum %.2f != meta.total_points %s" % (sum(pts), total))

    ids = [it.get("id") for it in items]
    if v2 and any(not i for i in ids):
        errors.append("every item needs a non-empty id")
    dup = sorted({i for i in ids if ids.count(i) > 1 and i})
    if dup:
        errors.append("duplicate item ids: %s" % ", ".join(dup))

    for it in items:
        if v2:
            if it.get("difficulty") not in DIFFICULTIES:
                errors.append("%s: difficulty must be one of %s" % (it.get("id"), DIFFICULTIES))
            if not it.get("topic"):
                errors.append("%s: topic is required" % it.get("id"))
            if it.get("kind") == "proof":
                if len(it.get("proof_check") or []) < 3:
                    errors.append("%s: proof requires at least 3 proof_check points" % it.get("id"))
                if len(it.get("sources") or []) < 2:
                    errors.append("%s: proof requires at least 2 independent sources" % it.get("id"))
            if it.get("uncertain") and len(it.get("sources") or []) < 2:
                errors.append("%s: uncertain item requires at least 2 verified sources" % it.get("id"))
            ans = str(it.get("answer", "")).strip()
            if ans in {"略", "见解析", "待补", "TODO", "TBD"} or ans.lower() in {"todo", "tbd", "n/a"}:
                errors.append("%s: placeholder answer %r is not allowed" % (it.get("id"), ans))
            opts = it.get("options") or []
            if opts:
                joined = "\n".join(opts)
                matches = list(re.finditer(r"([A-Za-z])[\.、]\s*", joined))
                L = [m.group(1).upper() for m in matches]
                if len(L) < 2:
                    errors.append("%s: options need at least 2 labelled entries (A./B./...)"
                                  % it.get("id"))
                if len(set(L)) != len(L):
                    errors.append("%s: duplicate option letters" % it.get("id"))
                if ans and L and ans[0].upper() not in L:
                    errors.append("%s: answer %r is not among option letters %s"
                                  % (it.get("id"), ans, L))
                texts = []
                for i, m in enumerate(matches):
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(joined)
                    seg = joined[m.end():end].replace("　", " ").strip()
                    texts.append(re.sub(r"\s+", " ", seg))
                if len(texts) >= 2 and len(set(texts)) != len(texts):
                    errors.append("%s: duplicate option text" % it.get("id"))
            if it.get("time_min") is not None:
                try:
                    if float(it["time_min"]) <= 0:
                        errors.append("%s: time_min must be positive" % it.get("id"))
                except (TypeError, ValueError):
                    errors.append("%s: time_min must be a number" % it.get("id"))
        check_sources(it.get("sources"), "%s.sources" % it.get("id"))
        if not str(it.get("answer", "")).strip():
            warnings.append("%s: empty answer" % it.get("id"))
        rubric = it.get("rubric") or []
        if rubric:
            rsum = sum(float(r.get("points", 0)) for r in rubric)
            if abs(rsum - float(it.get("points", 0))) > 1e-6:
                errors.append("%s: rubric sums to %.2f but item points is %s"
                              % (it.get("id"), rsum, it.get("points")))
        elif v2 and float(it.get("points", 0)) >= 5:
            warnings.append("%s: no rubric for a %s-point item" % (it.get("id"), it.get("points")))

        for m in it.get("math", []) or []:
            if m.get("kind", "fraction") not in ("fraction", "text"):
                errors.append("%s: unsupported math kind %r" % (it.get("id"), m.get("kind")))
        for fig in it.get("figures", []) or []:
            raw = fig.get("path", "")
            path = raw if os.path.isabs(raw) else os.path.join(asset_root, raw)
            path = os.path.realpath(path)
            if not (path.startswith(os.path.realpath(asset_root) + os.sep)
                    or path == os.path.realpath(asset_root)):
                errors.append("%s: figure escapes asset root: %s" % (it.get("id"), raw))
            elif not os.path.exists(path):
                errors.append("%s: figure not found: %s" % (it.get("id"), raw))

        nc = it.get("numeric_check")
        if nc:
            try:
                for x in nc.get("at", []):
                    float(eval_expr(nc["expr"], float(x)))
            except Exception as exc:  # noqa: BLE001
                errors.append("%s: numeric_check invalid (%s)" % (it.get("id"), exc))

    if v2:
        coverage = set(meta.get("coverage") or [])
        topics = {it.get("topic") for it in items}
        missing = sorted(coverage - topics)
        if missing:
            errors.append("coverage topics missing from paper: %s" % ", ".join(missing))
        extra = sorted(t for t in topics - coverage if t)
        if coverage and extra:
            warnings.append("topics outside declared coverage: %s" % ", ".join(extra))

        target = meta.get("difficulty_target")
        if target:
            got = {d: sum(float(it.get("points", 0)) for it in items if it.get("difficulty") == d)
                   for d in DIFFICULTIES}
            tol = float(meta.get("difficulty_tolerance", 5))
            for d in DIFFICULTIES:
                want = float(target.get(d, 0))
                if abs(got[d] - want) > tol:
                    errors.append("difficulty %s: %.0f points, target %.0f ± %.0f"
                                  % (d, got[d], want, tol))

        ans = spec.get("answers") or {}
        if not ans.get("auto") and not ans.get("sections"):
            errors.append("answers: set answers.auto=true or provide answers.sections")

        for sec in spec.get("sections", []):
            heading = str(sec.get("heading", ""))
            m = re.search(r"共\s*(\d+(?:\.\d+)?)\s*分", heading)
            if m and "不计入" not in heading:
                declared = float(m.group(1))
                actual = sum(float(it.get("points", 0)) for it in sec.get("items", []))
                if abs(declared - actual) > 1e-6:
                    errors.append("section %r declares %s points but items sum to %.2f"
                                  % (heading, declared, actual))

        times = [float(it["time_min"]) for it in items if it.get("time_min") is not None]
        duration = meta.get("duration_min")
        if times and duration:
            total_t = sum(times)
            if abs(total_t - float(duration)) > max(5.0, 0.2 * float(duration)):
                warnings.append("sum of time_min (%.0f) differs from duration_min (%s)"
                                % (total_t, duration))
    return errors, warnings


def answer_sections(spec: dict) -> list[dict]:
    out = []
    for sec in spec.get("sections", []):
        lines = []
        for it in sec.get("items", []):
            if not str(it.get("answer", "")).strip():
                continue
            line = "<b>%s.</b> %s" % (it.get("id", ""), it["answer"])
            if it.get("why"):
                line += "　" + it["why"]
            if it.get("rubric"):
                line += "　给分点：" + "；".join(
                    "%s（%g 分）" % (r.get("criterion", ""), float(r.get("points", 0)))
                    for r in it["rubric"])
            if it.get("proof_check"):
                line += "　证明自查：" + "；".join(str(x) for x in it["proof_check"])
            lines.append(line)
        if lines:
            out.append({"heading": sec["heading"], "lines": lines})
    return out


def diagnosis_tables(spec: dict, styles: dict, usable_cm: float) -> list[Any]:
    meta = spec.get("meta") or {}
    items = list(iter_items(spec))
    out = []
    rows = [["题号", "考点", "难度", "分值"]]
    for it in items:
        rows.append([it.get("id", ""), it.get("topic", ""),
                     DIFFICULTY_ZH.get(it.get("difficulty"), ""),
                     "%g" % float(it.get("points", 0))])
    rows.append(["合计", "", "", "%g" % sum(float(it.get("points", 0)) for it in items)])
    out.append(KeepTogether([p("双向细目表（含逐题考点定位）", styles, "h"),
                             make_table(rows, [2.6, 7.4, 3.0, 3.4], styles, usable_cm)]))

    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(str(it.get("topic", "")), []).append(it)
    rows = [["小节", "题号", "满分", "我的得分", "得分率"]]
    for topic, its in sorted(groups.items()):
        rows.append([topic, "、".join(str(x.get("id", "")) for x in its),
                     "%g" % sum(float(x.get("points", 0)) for x in its), "", ""])
    rows.append(["合计", "", "%g" % sum(float(x.get("points", 0)) for x in items), "", ""])
    out.append(KeepTogether([p("分小节得分表（自填）", styles, "h"),
                             make_table(rows, [3.0, 6.4, 2.4, 2.8, 2.4], styles, usable_cm)]))

    bands = meta.get("level_bands") or []
    if bands:
        rows = [["分数", "层级", "说明"]]
        for b in bands:
            rows.append([b.get("range", ""), b.get("level", ""), b.get("note", "")])
        block = [p("诊断对照表", styles, "h"), make_table(rows, [3.0, 5.0, 9.0], styles, usable_cm)]
        if meta.get("band_note"):
            block.append(p(sanitize_markup(meta["band_note"]), styles, "note"))
        out.append(KeepTogether(block))

    error_types = meta.get("error_types") or []
    if error_types:
        rows = [["错因", "典型表现"]] + [list(r) for r in error_types]
        out.append(KeepTogether([p("错因分类（用于自诊断）", styles, "h"),
                                 make_table(rows, [4.0, 13.0], styles, usable_cm)]))

    rows = [["题号", "我的答案", "错因（知识/链条/计算/审题/表达）", "用时"]]
    for it in items:
        rows.append([it.get("id", ""), "", "", ""])
    out.append(KeepTogether([p("自诊断记录表", styles, "h"),
                             make_table(rows, [2.2, 3.2, 8.6, 3.0], styles, usable_cm)]))
    return out


def source_table(spec: dict, styles: dict, usable_cm: float):
    meta = spec.get("meta") or {}
    rows = [["用途", "来源", "链接", "访问日期"]]
    for s in meta.get("sources") or []:
        rows.append([s.get("used_for", "教材/范围"), s.get("title", ""), s.get("url", ""),
                     s.get("accessed", "")])
    for it in iter_items(spec):
        for s in it.get("sources") or []:
            rows.append(["%s 命题依据" % it.get("id", ""), s.get("title", ""),
                         s.get("url", ""), s.get("accessed", "")])
    if len(rows) == 1:
        return None
    return KeepTogether([p("命题依据与核验记录", styles, "h"),
                         make_table(rows, [3.6, 5.4, 5.6, 2.4], styles, usable_cm)])


def build_story(spec, styles, usable_cm, asset_root, allow_raw=False):
    st = [p(sanitize_markup(spec["title"], allow_raw), styles, "title")]
    if spec.get("subtitle"):
        st.append(p(sanitize_markup(spec["subtitle"], allow_raw), styles, "sub"))
    st.append(Spacer(1, 8))
    if spec.get("info_line"):
        st.append(p(sanitize_markup(spec["info_line"], allow_raw), styles, "info"))
    if spec.get("note"):
        st.append(p(sanitize_markup(spec["note"], allow_raw), styles, "note"))
    st.append(Spacer(1, 4))

    for sec in spec.get("sections", []):
        if sec.get("page_break_before"):
            st.append(PageBreak())
        st.append(p(sanitize_markup(sec["heading"], allow_raw), styles, "h"))
        if sec.get("note"):
            st.append(p(sanitize_markup(sec["note"], allow_raw), styles, "note"))
        for it in sec.get("items", []):
            st.append(p(sanitize_markup(it["text"], allow_raw), styles, "body"))
            for opt in it.get("options", []):
                st.append(p(sanitize_markup(opt, allow_raw), styles, "opt"))
            for m in it.get("math", []) or []:
                if m.get("kind", "fraction") == "fraction":
                    st.append(make_fraction(m, styles))
                else:
                    st.append(p(sanitize_markup(m.get("text", ""), allow_raw), styles, "math"))
            for fig in it.get("figures", []) or []:
                st.append(Spacer(1, 4))
                st.append(make_figure(fig, asset_root, usable_cm))
                if fig.get("caption"):
                    st.append(p(sanitize_markup(fig["caption"], allow_raw), styles, "note"))
            if it.get("space"):
                st.append(Spacer(1, it["space"]))

    ans = spec.get("answers") or {}
    st.append(PageBreak())
    st.append(p(sanitize_markup(ans.get("title", "答案与评分标准"), allow_raw), styles, "title"))
    if ans.get("subtitle"):
        st.append(p(sanitize_markup(ans["subtitle"], allow_raw), styles, "sub"))
    st.append(Spacer(1, 8))
    sections = answer_sections(spec) if ans.get("auto") else ans.get("sections", [])
    for sec in sections:
        st.append(p(sanitize_markup(sec.get("heading", ""), allow_raw), styles, "h"))
        for line in sec.get("lines", []):
            st.append(p(sanitize_markup(line, allow_raw), styles, "ans"))
    for sec in ans.get("extra_sections", []):
        st.append(p(sanitize_markup(sec.get("heading", ""), allow_raw), styles, "h"))
        for line in sec.get("lines", []):
            st.append(p(sanitize_markup(line, allow_raw), styles, "ans"))
    st.extend(diagnosis_tables(spec, styles, usable_cm))
    src = source_table(spec, styles, usable_cm)
    if src is not None:
        st.append(src)
    return st


def write_markdown(spec, md_path):
    def md(x):
        return (x.replace("<super>", "<sup>").replace("</super>", "</sup>")
                 .replace("&lt;", "<").replace("&gt;", ">"))

    lines = ["---", "tags:", "  - 诊断卷", "created: %s" % spec.get("date", ""),
             "---", "", "# %s" % spec["title"], ""]
    if spec.get("subtitle"):
        lines += ["> %s" % md(spec["subtitle"]), ""]
    if spec.get("note"):
        lines += ["> %s" % md(spec["note"]), ""]
    lines += ["---", ""]
    for sec in spec.get("sections", []):
        lines += ["## %s" % md(sec["heading"]), ""]
        if sec.get("note"):
            lines += ["*%s*" % md(sec["note"]), ""]
        for it in sec.get("items", []):
            lines.append(md(it["text"]))
            for opt in it.get("options", []):
                lines.append("   " + md(opt))
            for m in it.get("math", []) or []:
                if m.get("kind", "fraction") == "fraction":
                    lines.append("   %s (%s)/(%s) %s" % (m.get("apply", ""), m.get("num", ""),
                                                         m.get("den", ""), m.get("suffix", "")))
                else:
                    lines.append("   " + md(m.get("text", "")))
            for fig in it.get("figures", []) or []:
                lines.append("   ![%s](%s)" % (fig.get("caption", "figure"), fig["path"]))
            lines.append("")
    ans = spec.get("answers") or {}
    lines += ["---", "", "# %s" % md(ans.get("title", "答案与评分标准")), ""]
    sections = answer_sections(spec) if ans.get("auto") else ans.get("sections", [])
    for sec in sections:
        lines += ["## %s" % md(sec.get("heading", "")), ""] + [md(x) for x in sec.get("lines", [])] + [""]
    meta = spec.get("meta") or {}
    items = list(iter_items(spec))
    if items:
        lines += ["## 双向细目表（含逐题考点定位）", "", "| 题号 | 考点 | 难度 | 分值 |",
                  "| --- | --- | --- | ---: |"]
        for it in items:
            lines.append("| %s | %s | %s | %g |" % (it.get("id", ""), it.get("topic", ""),
                                                   DIFFICULTY_ZH.get(it.get("difficulty"), ""),
                                                   float(it.get("points", 0))))
        lines.append("")
        groups: dict[str, list[dict]] = {}
        for it in items:
            groups.setdefault(str(it.get("topic", "")), []).append(it)
        lines += ["## 分小节得分表（自填）", "", "| 小节 | 题号 | 满分 | 我的得分 | 得分率 |",
                  "| --- | --- | ---: | --- | --- |"]
        for topic, its in sorted(groups.items()):
            lines.append("| %s | %s | %g |  |  |" % (topic,
                         "、".join(str(x.get("id", "")) for x in its),
                         sum(float(x.get("points", 0)) for x in its)))
        lines.append("")
    bands = meta.get("level_bands") or []
    if bands:
        lines += ["## 诊断对照表", "", "| 分数 | 层级 | 说明 |", "| --- | --- | --- |"]
        for b in bands:
            lines.append("| %s | %s | %s |" % (b.get("range", ""), b.get("level", ""), b.get("note", "")))
        if meta.get("band_note"):
            lines += ["", "> %s" % md(meta["band_note"])]
        lines.append("")

    sources = list(meta.get("sources") or [])
    for it in items:
        for s in it.get("sources") or []:
            sources.append(dict(s, used_for="%s 命题依据" % it.get("id", "")))
    if sources:
        lines += ["## 命题依据与核验记录", "", "| 用途 | 来源 | 链接 | 访问日期 |",
                  "| --- | --- | --- | --- |"]
        for s in sources:
            lines.append("| %s | %s | %s | %s |" % (s.get("used_for", ""), s.get("title", ""),
                                                   s.get("url", ""), s.get("accessed", "")))
        lines.append("")
    os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return md_path


def build(spec, *, fonts, page_size, margins, asset_root, out_override=None,
          allow_raw=False):
    out = out_override or spec["out_pdf"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    left, right, top, bottom = [m * cm for m in margins]
    usable_cm = page_size[0] / cm - (left + right) / cm

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(fonts.body, 8.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        base_y = max(0.7 * cm, bottom - 0.7 * cm)
        canvas.drawCentredString(page_size[0] / 2.0, base_y, "第 %d 页" % doc.page)
        canvas.drawString(left, base_y, spec.get("footer_left", spec.get("title", "")[:20]))
        canvas.drawRightString(page_size[0] - right, base_y, spec.get("footer_right", ""))
        canvas.restoreState()

    doc = SimpleDocTemplate(out, pagesize=page_size,
                            leftMargin=left, rightMargin=right,
                            topMargin=top, bottomMargin=bottom,
                            title=spec.get("title", "exam"),
                            author=spec.get("author", "exam-paper-maker"))
    doc.build(build_story(spec, make_styles(fonts), usable_cm, asset_root, allow_raw),
              onFirstPage=footer, onLaterPages=footer)
    return out


def font_embedding(pdf_path):
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(pdf_path)
    except Exception:  # noqa: BLE001
        return None
    total, embedded = 0, 0
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        fonts = resources.get("/Font") or {}
        for ref in fonts.values():
            font = ref.get_object()
            candidates = [font]
            desc_fonts = font.get("/DescendantFonts")
            if desc_fonts:
                candidates.append(desc_fonts[0].get_object())
            for cand in candidates:
                total += 1
                desc = cand.get("/FontDescriptor")
                if desc:
                    desc = desc.get_object()
                    if any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                        embedded += 1
                        break
    return total, embedded


def verify(pdf_path, spec, *, page_size, margins, tolerance=10.0,
           require_embedded=True):
    if pdfplumber is None:
        raise SystemExit("pdfplumber is required for --verify: pip install pdfplumber")
    v = spec.get("verify") or {}
    left_pt = margins[0] * cm
    right_pt = page_size[0] - margins[1] * cm
    problems = []
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        want = v.get("expected_pages")
        if want and n != want:
            problems.append("page count %d != expected %d" % (n, want))
        pages_text = []
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            pages_text.append(txt)
            words = page.extract_words()
            if words:
                x0 = min(w["x0"] for w in words)
                x1 = max(w["x1"] for w in words)
                if x0 < left_pt - tolerance:
                    problems.append("page %d: text left of margin (x0=%.1f)" % (i, x0))
                if x1 > right_pt + tolerance:
                    problems.append("page %d: text right of margin (x1=%.1f)" % (i, x1))
        for page_no, keys in (v.get("pages") or {}).items():
            idx = int(page_no) - 1
            if idx >= len(pages_text):
                problems.append("page %s missing" % page_no)
                continue
            for k in keys:
                if k not in pages_text[idx]:
                    problems.append("page %s: missing %r" % (page_no, k))
        full = "\n".join(pages_text)
        for k in v.get("must_contain", []):
            if k not in full:
                problems.append("document: missing %r" % k)
        for k in v.get("must_not_contain", []):
            if k in full:
                problems.append("document: unexpected %r (possible glyph drop)" % k)

        # Orphan heading: a section heading stranded as the last content line.
        headings = {s.get("heading", "") for s in spec.get("sections", [])}
        for i, txt in enumerate(pages_text, start=1):
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            lines = [ln for ln in lines if not re.match(r"^第 \d+ 页$", ln)]
            if lines and lines[-1] in headings:
                problems.append("page %d: heading stranded at page bottom: %r" % (i, lines[-1]))

        # Answer coverage: every item id should appear in the answer pages.
        ids = [it.get("id") for it in iter_items(spec) if it.get("id")]
        if ids:
            missing = [i for i in ids if ("%s." % i) not in full]
            if missing:
                problems.append("answers missing for items: %s" % ", ".join(missing))

    emb = font_embedding(pdf_path)
    if emb:
        total, embedded = emb
        if require_embedded and total and embedded == 0:
            problems.append("no embedded fonts (use --font or pass --allow-fallback-fonts)")
    return problems


def parse_margins(raw):
    parts = [float(x) for x in raw.split(",")]
    if len(parts) == 1:
        return (parts[0],) * 4
    if len(parts) == 4:
        return tuple(parts)
    raise argparse.ArgumentTypeError("use --margin 2.0 or --margin L,R,T,B")


def main():
    ap = argparse.ArgumentParser(description="Exam paper builder (schema v2)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out")
    ap.add_argument("--page-size", default="A4", choices=sorted(PAGE_SIZES))
    ap.add_argument("--margin", default="2.0,2.0,1.7,1.8")
    ap.add_argument("--font")
    ap.add_argument("--font-bold", dest="font_bold")
    ap.add_argument("--asset-root", default=None,
                    help="base directory for figure paths (default: spec directory)")
    ap.add_argument("--allow-raw-markup", action="store_true",
                    help="do not sanitise Paragraph markup (trusted specs only)")
    ap.add_argument("--allow-fallback-fonts", action="store_true",
                    help="do not fail verification when fonts are not embedded")
    ap.add_argument("--check-spec", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    asset_root = os.path.abspath(args.asset_root or os.path.dirname(os.path.abspath(args.spec)))
    page_size = PAGE_SIZES[args.page_size]
    margins = parse_margins(args.margin)

    errors, warnings = check_spec(spec, asset_root)
    for w in warnings:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    if errors or (args.strict and warnings):
        print("CHECK-SPEC: FAILED")
        return 1
    if args.check_spec and not args.verify and not args.out and not spec.get("out_pdf"):
        print("CHECK-SPEC: OK")
        return 0
    if args.check_spec:
        print("CHECK-SPEC: OK")
        if not args.verify and not args.out:
            return 0

    fonts = register_fonts(args.font, args.font_bold)
    out = build(spec, fonts=fonts, page_size=page_size, margins=margins,
                asset_root=asset_root, out_override=args.out,
                allow_raw=args.allow_raw_markup)
    print("WROTE %s (fonts embedded: %s)" % (out, fonts.embedded))
    md_path = None
    if spec.get("out_md"):
        md_path = spec["out_md"] if not args.out else os.path.splitext(args.out)[0] + ".md"
        print("WROTE %s" % write_markdown(spec, md_path))

    if args.verify:
        problems = verify(out, spec, page_size=page_size, margins=margins,
                          require_embedded=not args.allow_fallback_fonts)
        for pr in problems:
            print(" -", pr)
        if problems:
            print("VERIFY: FAILED (%d)" % len(problems))
            return 1
        print("VERIFY: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
