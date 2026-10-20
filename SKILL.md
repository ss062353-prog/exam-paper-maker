---
name: exam-paper-maker
description: 生成可打印的诊断试卷（原创仿真题 + 答案与评分标准 + 分层诊断表），题源优先取自知识库里的历年真题并限定到指定章节。Generate printable diagnostic exam papers (original simulation questions + answer key + scoring rubric + diagnostic tables) from past papers and a textbook chapter. Use when the user asks to 出试卷/组卷/命题/模拟卷/诊断卷/单元卷, or to create/build an exam paper, quiz, mock test, or unit test. Not for grading submitted papers.
metadata:
  short-description: 按章节与真题命制可打印诊断卷
---

# Exam Paper Maker

**Iron Law: 先建题目元数据与双向细目表，再排版；真题只参照题型与考点，绝不整卷复制。**

题目和答案写在**同一条目**里（`answer` / `rubric`），由工具自动生成答案区——这样不会出现"答案漏了一题"。

## 产出物

1. 可打印 PDF（A4/Letter，字体内嵌，答案独立成页）；
2. Markdown 源；
3. 答案与给分点（由 `rubric` 自动生成）；
4. 双向细目表、诊断对照表、错因分类、自诊断记录表。

## 开工前确认（能推断就不要问）

- 章节范围与教材版本；真题来源；满分、时长、题型；
- 是否允许超纲题（默认不允许；要用就标注"挑战题（需第 X 章）"）；
- 输出目录（默认 `03-知识库\练习\`）。

## 工作流

### 1. 读题源（⚠️ 必做）

真题取**题型结构与考点分布**；教材用官方目录核对小节；输出考点清单（来源：真题/教材）。

### 2. 先写题目元数据（⚠️ 必做）

每道题必须带：

| 字段 | 作用 |
| --- | --- |
| `id` | 唯一题号，用于答案覆盖与定位 |
| `points` | 分值 |
| `difficulty` | `basic` / `medium` / `challenge` |
| `topic` | 小节，如 `§1.5` |
| `answer` | 答案（必填） |
| `rubric` | 给分点列表，合计必须等于 `points`（≥5 分的题必填） |
| `numeric_check` | 可选；数值复核表达式（见下） |
| `time_min` | 建议用时（分钟）；各题之和应与 `meta.duration_min` 接近 |

**数值复核**：给计算题写 `{"expr": "...", "at": [1000, 10000], "expected": 7.389, "rtol": 0.01}`。表达式只允许 `x`、数字、`+ - * / ** %` 和白名单数学函数（`sin/cos/exp/log/sqrt/...`），由安全 AST 求值，不执行任意代码。它是**答案正确性的独立检查**；证明题没有数值复核，仍需人工复核（这是诚实的边界）。

### 3. 结构校验（⚠️ 必做）

```bash
python scripts/build_exam_pdf.py --spec paper.json --check-spec
```

会检查：分值总和、题号唯一、覆盖小节、难度配比、rubric 合计、答案非空/非占位、选项唯一且答案在选项内、章节标题"共 X 分"与题目合计一致、时间预算、数值表达式、插图路径越界，以及**证明题 ≥2 个带 quote 的来源**。**有 ERROR 就不要生成。**

### 4. 生成与版式校验（⚠️ 必做）

```bash
python scripts/build_exam_pdf.py --spec paper.json --verify
```

校验：页数、每页关键内容、边距、**字体是否内嵌**、标题是否孤立在页底、**答案是否覆盖所有题号**。

常用参数：`--out`、`--page-size A4|LETTER`、`--margin L,R,T,B`、`--font`、`--font-bold`、`--asset-root`、`--allow-fallback-fonts`（应急）、`--allow-raw-markup`（仅可信 spec）。

### 5. 归档

写入 Markdown 源与 PDF，更新 `练习\索引.md`；对话里给出打印页码指引。

### 6. 卡住时：先检索，再落笔（⚠️ 证明题必做）

遇到**定理条件记不准、构造想不到、答案与数值冲突、反例拿不准**时：

1. 重述目标，指出卡在定义/条件/构造/结论哪一步；
2. 联网检索（优先教材官方页、大学课程页、百科），**交叉核对两个独立来源**；
3. 用小例子/极端值/`numeric_check` 做本地自检；
4. 在题目 `sources` 里记录 `title / url / accessed / used_for`；
5. 仍不确定就标 `uncertain: true` 并向用户提问——**不许编造定理**。
6. 运行 `python scripts/check_sources.py --spec paper.json --allow-blocked`，确认链接可达且页面确实包含 quote。

证明题要写 `proof_check`（≥3 条：前提、构造、不等式/取整、结论句）与 **≥2 个独立来源（每个都带 `quote` 原文摘录）**。完整协议见
[references/problem-solving.md](references/problem-solving.md)。

## 硬规则

1. 真题只参照题型与考点，不整卷复制，不声称官方。
2. 先题后答案；答案由 `answers.auto: true` 从题目生成。
3. 每个题型给分值；卷末必须有诊断对照表。
4. 逐题考点定位表由 `topic` 自动生成，不要手写两份。
5. 超纲工具不默认使用；要用就标注。
6. `--check-spec` 与 `--verify` 都必须通过；失败先修再交付。
7. 字体必须内嵌；`--allow-fallback-fonts` 只用于临时排查。
8. 插图必须走 `figures` + `--asset-root`，不要在文本里写 `<img>`（默认会被清洗）。
9. 证明题卡壳时先检索并留痕；`uncertain: true` 而没有 `sources` 会被 `--check-spec` 判为 ERROR。
10. 证明题少于 2 个来源、或来源缺 `quote`，直接判 ERROR；CI 会运行 `check_sources.py`。

## 反模式

- ❌ 只有题干没有 `points/topic/rubric` → 诊断与配分无法校验
- ❌ 手写答案区 → 容易漏题，且无法自动核对
- ❌ 难度标签随手写 → 4:4:2 校验会失败
- ❌ 用 `<img>` 嵌图 → 被清洗；请用 `figures`
- ❌ 只跑构建不跑 `--verify` → 缺字、越界、孤立标题都可能漏过去

## 交付前检查

- [ ] `--check-spec` 通过（ERROR 为零）
- [ ] `--verify` 通过（含字体内嵌）
- [ ] 难度配比落在目标 ± 容差
- [ ] 每条 ≥5 分有 rubric，且合计等于分值
- [ ] 诊断表、错因分类、自诊断表齐全
- [ ] 分小节得分表已生成；时间之和接近 `duration_min`
- [ ] `check_sources.py` 通过（链接可达、quote 命中）
- [ ] 卷首标注"原创仿真卷，非官方真题"

## 边界

- 分档是**启发式参考**，不是标准化测量；卷面必须保留 `band_note` 说明。
- 证明题没有数值复核，必须人工复核答案。
- 证明题的可靠性依赖检索与交叉核对；技能不会自动判断"这个定理用得对不对"。
- 数学排版是"线性 + 分式块"，不是 LaTeX；复杂公式请拆成多行或改用图片。

## References

- 结构、留白、卷末四件：[references/paper-structure.md](references/paper-structure.md)
- 命题质量、难度、rubric、数值复核：[references/item-quality.md](references/item-quality.md)
- 字体安全、公式块、插图：[references/plain-text-math.md](references/plain-text-math.md)
