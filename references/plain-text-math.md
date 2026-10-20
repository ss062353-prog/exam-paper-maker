# 可打印 PDF 的数学写法（字体安全）

用 ReportLab 直接排版时，**字体缺字**是最容易翻车的地方。以下是实测有效的规则。

## 1. 符号写法

| 想要 | 写法 | 备注 |
| --- | --- | --- |
| 上下标 | `<super>2</super>`、`<sub>n</sub>`、`x<sub>0</sub>` | ReportLab 段落标记，**不要**用 Unicode 的 ² ˣ ₙ |
| 极限 | `lim(x→x0)`、`lim(n→∞)` | 线性写法比堆叠分数更抗窄栏 |
| 根号 | `√(x + 4)` | √、∞、→、ε、δ、≠、≤、≥ 在常见中文字体里都有 |
| 减号 | `-`（ASCII 连字符） | 加粗段里 U+2212 常缺字 |
| 并集 | `∪` | 只在正文字体里用 |
| 区间 | `(-1, 0) ∪ (0, 2]` | 括号用 ASCII |
| 乘号 | `·` 或省略 | `x·sin x` |

## 2. 字体规则（踩过的坑）

- 正文用宋体（如 `STSONG.TTF`），标题与加粗用黑体（`simhei.ttf`），并用 `registerFontFamily` 把粗体映射到黑体。
- **加粗段里只放中文与常规标点**。实测黑体缺少 `−`（U+2212）、`²`、`∪` 等符号，落进 `<b>...</b>` 里会**静默缺字**（PDF 里看不见，抽文字才发现）。
  - 安全写法：只把序号加粗，例如 `<b>1.</b> 答案是 (-1, 0) ∪ (0, 2]`，不要写成 `<b>1. (-1, 0) ∪ (0, 2]</b>`。
- TTF 子集会被嵌入 PDF，换机器打印不掉字；`UnicodeCIDFont("STSong-Light")` 依赖阅读器自带字体，仅作兜底。
- 跨平台字体候选：Windows `STSONG.TTF` / `simhei.ttf`；macOS `Songti.ttc` / `PingFang.ttc`；Linux `NotoSansCJK-Regular.ttc` / `wqy-zenhei.ttc`。可用 `--font` 显式指定。

## 3. 生成后必须做的自动校验

`--verify` 用 `pdfplumber` 抽文本 + 量边界，做四项断言：

1. **页数**符合预期；
2. **每页关键内容**都在（章节标题、题型、典型题干片段）；
3. **正文不越边距**：所有词的 `x0/x1` 落在页边距内（带容差）；
4. **缺字检测**：断言应出现的符号串出现，同时断言缺字后才会出现的畸形串不出现。

## 4. 渲染自查（可选）

```bash
pdftoppm -png -r 100 paper.pdf page
```

注意 CID 字体在 Poppler 下会被替换成本机字体，渲染观感与实际打印略有差异；以文本抽取 + 字体嵌入检查为准。

## 5. 公式块与插图

**分式/极限块**（无 LaTeX 依赖）：

```json
"math": [{"kind": "fraction", "apply": "lim(x→2)", "num": "x² - 4", "den": "x - 2", "suffix": "= ?"}]
```

渲染为"极限前缀 + 分子/分母带横线 + 后缀"。复杂公式请拆成多行，或改用插图。

**插图**：

```json
"figures": [{"path": "assets/hole.png", "width_cm": 8.5, "caption": "图 1"}]
```

路径必须在 `--asset-root` 之内（防目录穿越）；支持 PNG/JPEG。

## 6. markup 白名单

默认只允许 `<b> <i> <u> <super> <sub> <br>`。`<img>`、`<a>`、`<font>` 等会被转义成文本。
需要原样透传时用 `--allow-raw-markup`——**只对你自己写的 spec 使用**。
