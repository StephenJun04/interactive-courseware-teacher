# 构建与数据格式

## 运行环境

命令里的 `python3`、`node` 必须指向有相应依赖的解释器。Codex 桌面可先用 `load_workspace_dependencies` 查询已有运行时；其他环境检查可用解释器。不要写死某台机器的路径。

- PyMuPDF 提供 `fitz`：提取文本、裁图和生成 PDF 页面 JPEG。
- `mathjax-full`：Node 构建时将 LaTeX 转为静态 SVG，网页打开时不需要 Node 或网络。
- Playwright：仅用于可选浏览器测试；可用已安装的 Chrome 或 Playwright Chromium。

缺少依赖时优先在当前任务的临时目录隔离配置。例如用虚拟环境安装 `pymupdf`，在任务的 Node 目录安装 `mathjax-full`。不修改全局配置或 skill 安装目录：

```bash
python3 -m venv /path/work/venv
/path/work/venv/bin/python -m pip install pymupdf
npm install --prefix /path/work/node --no-audit --no-fund mathjax-full
NODE_PATH=/path/work/node/node_modules /path/work/venv/bin/python /path/skill/scripts/build_reader.py --lesson /path/work/lesson.json --pdf /path/source.pdf --out /path/output/textbook.html
```

Node 需在 `PATH` 中；`NODE_PATH` 解决在任务目录安装的包对 skill 脚本不可见的问题。无公式的讲义不需要数学渲染依赖。`Math SVG: True` 仅说明渲染器输出了 SVG，还需目视核对公式，没有错误框或丢失符号。

## JSON 约定

完整可运行示例：[lesson.sample.json](../templates/lesson.sample.json)。所有 JSON 数学字符串按 JSON 规则转义反斜线，例如 `"\\sum_i x_i"` 解析后才是 `\sum_i x_i`。

顶层：`title`（必填）、`subtitle`（可选）、`source_name`（来源标识）、`scope: {start_page, end_page}`、`lessons` 数组。`reading_mode` 默认 `continuous`（全篇展开，左右独立）；设置 `paged` 可逐讲切换。明确设置 scope；校验器才能检查范围内漏页。

每讲：`page`、`title`、可选 `kicker`、`blocks`。每个物理页一讲，按页码升序，禁止重复；每讲至少一个解释块。题目 `id` 在同讲内唯一，避免共享错误次数或单选组。

| block `type` | 数据与用途 |
| --- | --- |
| `paragraph` | `text`，普通正文，支持 `**强调**`，不接受任意 HTML |
| `code` | `text`，原样显示代码，自动转义 HTML，容器内横向滚动 |
| `table` | `columns` 文本数组、`rows` 等长单元格数组，单元格为文本或数字 |
| `heading` / `note` | `text`；note 用“课件原文／教师补充／待核对”文字明确来源 |
| `equation` | `latex`、可选 `caption`，静态 SVG |
| `list` | `items`，字符串数组或含 `text` 的对象数组 |
| `example` | `title`、可选 `intro`、`steps` 数组；每步可有 `text` 和 `latex` |
| `figure` | 可选 `page`（默认本讲页码）、`caption`、`rect_rel: [x0,y0,x1,y1]`（0–1，原 PDF 页内相对坐标）；不设裁框则使用整页 |
| `interactive` | `kind`、`config`、可选 `title` / `caption`，见下文 |
| `quiz` | `questions` 数组、可选 `title` / `caption`，见下文 |

`source_note`、`teacher_addition` 不是渲染字段。把需要学生看见的来源或补充写进 `note.text`，不能仅放在未知字段中。

### 实验

- `convolution`：`config.input`、`config.kernel` 为非空、规则、有限数值矩阵，核不超过输入；`bias` 为有限数值，默认 0。实现的是单通道、stride=1、padding=0 的 cross-correlation；输入固定，核可编辑，输出格可点击查看乘加过程。
- `output_shape`：整数 `N`、`F`、`P`、`S`；当前滑块范围分别为 3–32、1–9、0–6、1–5。有效窗口要求 `N+2P >= F`；实验也能显示无有效窗口状态。不要配置超出界面范围的初始值。

### 题目

通用字段：`id`、`type`、`question`、`hint`、`explanation`。答案为本地教学自测而内嵌在 HTML，不适合保密考试。

- `single_choice`：`options` 为文本数组，`answer` 为从 0 开始的正确选项索引。
- `numeric`：有限数值 `answer`，非负有限 `tolerance`（默认 0）。
- `multi_part`：非空 `parts`，每问包含 `label`、有限数值 `answer`、可选 `tolerance`。当前只有数字小问，整题统一对错反馈。
- 可选 `remedial: {question: "针对误区的追问"}`：第一次答错时追加静态追问，当前讲内答对不会移除。连续模式在页面保留这个追问；逐讲模式切讲或刷新不恢复这个追问，不包含独立判分。

## 重建与计时

首次渲染全部 PDF 页面，后续构建默认复用输出目录内 `.courseware-cache/`。缓存键含 PDF 内容 SHA-256、预览缩放、JPEG 质量和 PyMuPDF 版本，来源或参数变化自动失效；损坏缓存会重新渲染。

- `--cache-dir /path/work/pdf-cache`：把缓存放到当前任务的工作目录，让不同输出复用同一来源。
- `--no-cache`：完全跳过缓存读写，用于比较或排查问题。
- `--metrics-json /path/work/build-metrics.json`：保存公式渲染、PDF 处理、总构建耗时及缓存命中状态。计时不包含审阅、撰稿和浏览器 QA，不能用于声称端到端提速。

不要每次创建虚拟环境或安装依赖。先验证当前任务/宿主已有环境，缺什么才补什么；无公式时不要安装 MathJax。浏览器测试优先使用已有 Chrome，只有没有可用浏览器时才下载 Chromium。缓存不进入分享包，也不能代替原始页码或内容核对。

## 构建与测试边界

`check_lesson.py` 检查部分结构、页码和题型，不独立复算答案，也不是完整 JSON schema 验证。先审查必填字段、范围、数值与数学，再运行脚本。

`build_reader.py --zip` 将 HTML 和原 PDF 打包；需修改教材时另保留 `lesson.json`。`--scale` 与 `--jpeg-quality` 可平衡预览清晰度和大课件文件体积；页面图像在构建时全部内嵌，浏览器仅懒加载显示。

冒烟测试默认使用 `examples/demo_reader.html`；正式测试先构建到任务目录，并传 `--html`。Python 环境需有 `playwright`，浏览器通过 `--browser-executable` 指定，未指定时使用本机 Chrome（如可用）或 Playwright 的 Chromium。测试会生成临时页面副本，不修改输入文件；`--screenshots /path/work/screenshots` 可保存截图。它检查阅读器框架，不证明任意课程的教学和数学正确。
