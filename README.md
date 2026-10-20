# Exam Paper Maker

Turn a textbook chapter and past exam papers into a **printable diagnostic exam** — with an answer key, per-question rubrics, independent numeric checks, and diagnostic tables.

An agent skill (`SKILL.md`) plus a deterministic PDF builder. Works with Codex-style and Claude Code-style skills.

## What it guarantees

| Guarantee | How |
| --- | --- |
| 分值不会加错 | `--check-spec` sums item points against `meta.total_points` |
| 不会漏答案 | answers are generated from each item's `answer`/`rubric` |
| 答案有独立复核 | `numeric_check` evaluates a whitelisted expression at sample points |
| 考点覆盖可查 | `meta.coverage` ⊆ topics actually used |
| 难度配比可查 | `meta.difficulty_target` vs actual points per difficulty |
| 引用可核验 | proof items need ≥2 sources with a `quote`; `check_sources.py` fetches each URL and matches the quote |
| 排版可打印 | embedded CJK fonts, page numbers, answer section on new pages |
| 交付前有证据 | `--verify` checks pages, content, margins, fonts, orphan headings, answer coverage |

## Quick start

```bash
pip install reportlab pdfplumber pypdf pillow
python scripts/build_exam_pdf.py --spec examples/spec-example.json --check-spec --verify
python scripts/check_sources.py --spec examples/spec-example.json --allow-blocked
```

`examples/sample-output.pdf` is the generated demo (4 pages: paper + answers + diagnosis).

### Install as a skill

```bash
git clone <your-repo-url> ~/.codex/skills/exam-paper-maker
python ~/.codex/skills/exam-paper-maker/scripts/sync_skill.py --check
```

## Spec (schema v2)

```json
{
  "schema_version": 2,
  "out_pdf": "out/paper.pdf",
  "title": "高等数学 第一章 诊断卷",
  "meta": {
    "total_points": 30,
    "coverage": ["§1.1", "§1.5"],
    "difficulty_target": {"basic": 12, "medium": 12, "challenge": 6},
    "level_bands": [{"range": "27-30", "level": "第 5 层", "note": "稳"}],
    "error_types": [["知识缺口", "定义没记住"]]
  },
  "sections": [{
    "heading": "一、单项选择题（每小题 3 分）",
    "items": [{
      "id": "A1", "points": 3, "difficulty": "basic", "topic": "§1.1",
      "text": "题干",
      "options": ["A. …", "B. …"],
      "answer": "B", "time_min": 3,
      "why": "理由",
      "rubric": [{"criterion": "概念判断", "points": 3}],
      "numeric_check": {"expr": "(x**2 - 4)/(x - 2)", "at": [2.0001], "expected": 4, "rtol": 0.01},
      "math": [{"kind": "fraction", "apply": "lim(x→2)", "num": "x² - 4", "den": "x - 2"}],
      "figures": [{"path": "assets/limit-hole.png", "width_cm": 8, "caption": "图 1"}],
      "sources": [{"title": "…", "url": "https://…", "accessed": "2026-10-20",
                    "quote": "原文摘录（≥10 字）"}]
    }]
  }],
  "answers": {"auto": true},
  "verify": {"must_contain": ["可去间断点"]}
}
```

Full schema: [schemas/paper.schema.json](schemas/paper.schema.json).

## Commands

```bash
python scripts/build_exam_pdf.py --spec paper.json --check-spec   # structure + arithmetic
python scripts/build_exam_pdf.py --spec paper.json --verify       # build + layout/quality checks
python scripts/check_sources.py --spec paper.json --allow-blocked # links + quotes
python scripts/build_exam_pdf.py --spec paper.json --out out.pdf --page-size LETTER --margin 2.5
python scripts/sync_skill.py --check                              # installed copy drift check
```

| Flag | Meaning |
| --- | --- |
| `--font`, `--font-bold` | explicit CJK TTF/TTC (overrides auto-discovery) |
| `--asset-root` | base dir for figure paths (default: spec directory) |
| `--allow-fallback-fonts` | do not fail when fonts are not embedded (emergency only) |
| `--allow-raw-markup` | disable markup sanitising (trusted specs only) |
| `--strict` | treat warnings as errors |

## Security & trust model

- Paragraph markup is sanitised to `b`, `i`, `u`, `super`, `sub`, `br`; `<img>`, `<a>`, `<font>` are escaped. Use the `figures` field instead.
- Figure paths must resolve inside `--asset-root`.
- `numeric_check` expressions are parsed with Python's `ast` and evaluated against a whitelist; no imports, attributes, or arbitrary calls.
- The spec is otherwise treated as trusted input (it controls output paths).

## Research-first for proofs

When a proof's theorem, conditions or counterexample are uncertain, the skill requires a
search → cross-check → local sanity check → record loop:

1. restate the goal and locate the stuck step;
2. search (textbook/publisher pages, university course notes, encyclopedias);
3. cross-check two independent sources;
4. test a small case or a numeric sample;
5. record `title / url / accessed / used_for` in `sources`.

Proof items carry `proof_check` (premise → construction → inequality → conclusion) and are
rendered with a "命题依据与核验记录" appendix. `uncertain: true` without any source is a
hard error. The protocol lives in [references/problem-solving.md](references/problem-solving.md).

## What it does not do

- No LaTeX engine: math is linear text plus a fraction block.
- No automatic correctness proof: numeric checks cover computational items; proof answers need human review.
- `numeric_check` is a *consistency* gate: if both the expression and expected value are wrong in the same way, it passes.
- Difficulty labels and score bands are **heuristic**; `band_note` is rendered on the paper.
- No item-response statistics; collect real student data before treating bands as measurement.

### Calibration loop (optional, but honest)

`assets/calibration-template.csv` is a starting sheet for real data:

```csv
item_id,difficulty,students_attempted,correct_rate,discrimination,notes
B1,medium,32,0.62,0.41,
```

- `correct_rate` = 得分率；用它核对"难度"标签是否与实际一致。
- `discrimination` = 高分组得分率 − 低分组得分率；接近 0 的题对诊断没有分辨率。
- 跑满 30+ 人后再调 `level_bands`；不要用未经标定的分档宣称"测量"。

## Repository layout

```
SKILL.md                       # agent instructions
README.md                      # repo docs
schemas/paper.schema.json      # JSON Schema (v2)
scripts/build_exam_pdf.py      # builder + checker + verifier
scripts/check_sources.py       # URL + quote verification
scripts/sync_skill.py          # install/sync + drift check
references/                    # structure, item quality, font safety
examples/                      # v2 spec, demo figure, generated PDF
tests/                         # unittest suite + e2e smoke test
.github/workflows/ci.yml       # Ubuntu / Windows / macOS CI
```

## Development

```bash
python -m unittest discover -s tests -v
python tests/smoke_test.py
git archive --format=zip -o dist/exam-paper-maker.skill HEAD
```

## License

MIT — see [LICENSE](LICENSE).
