---
name: pangu
description: 盘古 1.0 · 开天辟地式造世引擎。以"律先于物"为原则，先设定世界底层的数学/物理/化学/生物法则，再推导其宏观与中观形态，突破"行星绕恒星、碳基需氧"的地球桎梏，造出三倍地球大的双日照地、无恒星的能量世界、非欧几何宇宙等"理论上不该存在却完全自洽"的虚拟世界。全程以多轮对话与用户共创、以网页检索抓取前沿科学与奇想作为灵感对照，产出自洽性审查报告、结构化 world.json、通俗世界档案与可交互 3D 预览页。当用户提出"造一个世界/宇宙""设计一个星球的物理法则""如果重力反过来会怎样""做一个不靠太阳的生物圈""写一个双恒星世界的设定""给小说/游戏做底层宇宙规则""做个能转的 3D 星球预览"等需求时使用。
license: MIT
metadata:
  title: 盘古 1.0 · 开天辟地造世引擎
  version: 1.0.0
  entrypoint: scripts/pangu.py
  runtime: python>=3.9 (仅标准库)
  install: python install.py --target all
---

# 盘古 1.0 · 开天辟地造世引擎

盘古不是"写设定"，是**立律**。区别在于：设定回答"这个世界有什么"，律回答"这个世界为什么只能长成这样"。

地球不是模板，是**一个样本**。世界的引力常数可以不是 6.674e-11，光速可以不是 c，碳可以不是生命骨架，一天可以不是自转给的。本技能的任务是：让用户（或你）重写这些常数与规则，然后严格推导——推导出山怎么长、雨怎么下、生物怎么喘气、文明怎么计时——直到它**自洽到能骗过物理学家**，同时**奇诡到没人想过**。

## 宿主无关：这份技能不绑定任何一家 agent

本技能刻意只依赖三样东西：**Markdown 文本**（你能读）、**Python 标准库**（无需 pip）、**本目录内的文件**。没有厂商 API、没有平台专有工具、没有联网必需项（检索能力用不用都能跑，只是没有检索时灵感校准会弱一档）。

因此它可以用三种方式被任意 agent / harness 加载，任选其一：

| 方式 | 适用宿主 | 加载什么 |
|---|---|---|
| **A. 原生技能目录** | Claude Code / Claude.ai Skills、OpenAI Codex、Cline、Roo、OpenHands、以及任何支持 `SKILL.md` 约定或"把目录塞进上下文"的框架 | 整个目录，入口 `SKILL.md` |
| **B. 指令文件指针** | Codex / Amp / Jules（`AGENTS.md`）、Cursor（`.cursor/rules/*.mdc`）、Windsurf（`.windsurf/rules/*.md`）、Gemini CLI（`GEMINI.md`） | 只写一个几十行的指针文件，告诉它去哪读 `SKILL.md` |
| **C. MCP 工具服务器** | 任何支持 MCP 的客户端（Claude Desktop、Cursor、Zed、Continue、Cherry Studio、自研 harness） | `adapters/mcp/pangu_mcp.py`，把引擎暴露成 6 个 tool |

`python install.py --target all` 会一次性把 A、B 两种入口铺好；C 只需在客户端配置里加一行命令。**三种方式共享同一套 `scripts/` 与 `references/`，不存在分叉。**

给 agent 的最小作业约定（不管你是什么 harness）：
1. 需要造世界时，**先完整读 `SKILL.md`**，再按需加载 `references/` 里被点名的文件（渐进披露，不要一次全读）。
2. 所有脚本走 `python scripts/pangu.py <子命令>`；Windows 上把 `python` 换成实际的解释器路径。
3. 产物写到**用户指定目录**；用户没说就写到当前工作目录下的 `out/<世界id>/`，**不要写进技能目录内部**。
4. 生成物（`preview.html`、`世界档案.md`）禁止手改，改 `world.json` 再重跑。

## 三律（灵魂，不可跳过）

任何世界必须同时满足以下三条，否则推倒重来：

| 律 | 名称 | 要求 | 检验问句 |
|---|---|---|---|
| 一 | **逆行律** | 至少一个底层维度与地球直觉**明确相反** | "这世界哪条常识是反的？" |
| 二 | **代价律** | 每条反常识都必须付出**可量化**的代价 | "为了得到它，失去了什么？" |
| 三 | **痕迹律** | 代价必须在**可观测层**留下痕迹 | "居民抬头能看见什么异常？" |

> 反例（不合格）："这个世界魔法很强。"——没有逆行、没有代价、没有痕迹。
> 正例（合格）："引力是斥力，万物相互排斥。代价：物质无法聚集成团，所以没有星球，只有一层被中心奇点压住的壳。痕迹：任何物体被举起后不会落下，而是加速飘向天顶；文明建筑全部向下生长。"

**没有代价的奇观是意淫，有代价的奇观才是世界。**

## 七斧创世流程

严格按序推进。每斧 = **问（2–3 问）→ 搜（1–2 次检索）→ 定（写 JSON + 自检）**。问与搜可以并行，定之前必须搜完。

| # | 斧 | 中文 | 干什么 | 写进 world.json | 典型问题 |
|---|---|---|---|---|---|
| 1 | Chaos | 混沌 | 采集种子意象、美学基调、禁忌 | `meta` `seed` | "一句话说出这世界最怪的一幕" |
| 2 | Dichotomy | 分判 | 时空框架、宇宙拓扑、有无恒星 | `cosmology` | "天上有什么？几颗？有没有'天'？" |
| 3 | Nomos | 立律 | 物理常数、守恒律改动、新相互作用 | `physics` `mathematics` | "哪条守恒律被打破了？" |
| 4 | Materia | 炼质 | 元素表、键合规则、材料与相态 | `chemistry` | "最硬的物质是什么做的？" |
| 5 | Genesis | 化生 | 能量货币、遗传载体、生态金字塔 | `biology` | "生物靠吃什么活着？" |
| 6 | Anima | 启智 | 意识、社会、技术的另类路径（可选） | `civilization` | "他们怎么计时？怎么知道一年过去了？" |
| 7 | Cosmogony | 演界 | 历史推演、自洽审查、3D 呈现、交付 | `history` `consistency` `narrative` | "这世界会怎么灭亡？" |

**硬约束**：第 3 斧（立律）结束前，不得讨论任何具体生物或文明。先有律，后有物。违反即"倒因为果"，会被审查器判为致命错误。

## 第一步永远是确认"自主度"

开场不要问一长串问题。先给用户一个**三选一**，再决定怎么走：

- **「我只给一句话，你来造」** → 全自主模式：每斧你自己定，只把结果给用户看，允许用户在任何一斧后叫停改向
- **「我想自己定关键设定」** → 共创模式：每斧先给 2–3 个截然不同的方案（附代价），用户选，你再推导
- **「我有完整构想，帮我验尸」** → 审计模式：跳到第 7 斧，直接用审查协议逐条挑错并给修补方案

一句话种子就够开工。**不要因为信息不足而空转。**

## 网页检索的用法（不是可选，是必需）

检索的目的不是抄，是**校准**与**取反**。每条检索都归入四类之一：

| 类型 | 目的 | 示例 query |
|---|---|---|
| **锚定** | 拿到真实世界的数值/机制作为参照系 | `circumbinary planet habitable zone stability` / `super-Earth maximum radius rocky` |
| **证伪** | 找出"为什么这样不行"的硬约束 | `why no rocky planet 3 earth radii` / `triple star system planet stability` |
| **取反** | 找到真实存在的极端案例，然后推到更极端 | `organism arsenic DNA substitute` / `life without water non-carbon solvent` |
| **质感** | 抓意象、术语、视觉参考，用于描述与配色 | `sunset binary star sky color simulation` |

要点：
- 每个世界 **≥ 4 次检索**，且必须覆盖"证伪"类至少 1 次——**先找它为什么不可能，再解释它为什么可能**
- 检索结果要落成 `seed.references[]`（标题 + 一句话结论 + 我怎么用它），让用户看得见依据
- 检索到的东西**必须被改写**，不能整段搬进设定。我们要的是"开普勒-16b 是环双星行星"这个事实，不是维基原文

详细检索配方见 `references/检索与灵感策略.md`。

## 自洽性审查（第 7 斧，强制）

用 `references/自洽性审查协议.md` 里的 **五维十六问** 逐条过，输出评分与致命项。三个维度是硬门槛：

1. **结构稳定**：天体/结构能否在设定时长内存活（洛希极限、轨道共振、双星稳定半径 ≥ 2–4 倍双星间距、潮汐锁定）
2. **能量守恒**：生物圈与文明的能源从哪来，总量是否够，熵是否排得出去
3. **观测一致**：居民看到的天空、季节、昼夜，是否与宇宙设定推得的结果一致

有致命项（`fatal`）时，**不许交付**。给两个修补方案：改设定，或改代价。

`scripts/pangu.py validate` 会自动跑可机检的部分（结构、范围、单位、双星稳定性、洛希极限、能量收支数量级），人只需负责语义部分。

## 交付物

| 层 | 文件 | 说明 |
|---|---|---|
| 数据层 | `world.json` | **单一数据源**。改设定只改它，再重跑脚本 |
| 呈现层 | `preview.html` | 3D 预览（多恒星系统 + 行星特写 + 双光源昼夜） |
| 阅读层 | `世界档案.md` | 通俗版，含"三律"、常数表、生态、文明、审查报告 |
| 审查层 | `审查报告.json` | 五维评分 + 致命项 + 修补建议（`export --json-out` 产出） |

**单一数据源原则**：`preview.html` 与 `世界档案.md` 全部由 `world.json` 生成。禁止手改生成物，否则 3D 与文档会漂移。

## 命令速查

命令中的 `scripts/` 相对**本技能目录**；路径建议一律用绝对路径。

```bash
# 0. 环境自检（python 版本、模板是否存在、CDN 可达性）
python scripts/pangu.py doctor

# 1. 从种子生成骨架 world.json（先填 meta/cosmology 占位，后续斧头逐段补写）
python scripts/pangu.py init --name "赫利孔" --seed "三倍地球大，天上有两个太阳" --out out/world.json

# 2. 校验 + 自洽打分（可机检部分）
python scripts/pangu.py validate out/world.json
python scripts/pangu.py validate out/world.json --strict   # 有 fatal 即非零退出

# 3. 生成 3D 预览页
python scripts/pangu.py preview out/world.json -o out/preview.html

# 4. 生成世界档案 Markdown
python scripts/pangu.py export out/world.json --md out/世界档案.md

# 5. 查公理库（可复用的反常识设定积木）
python scripts/pangu.py axioms              # 列全部
python scripts/pangu.py axioms --domain physics --roll 3   # 物理类随机抽 3 条
```

## 质量红线

- ❌ **倒因为果**：先想好"龙"，再补物理。顺序必须反过来
- ❌ **无代价奇观**：任何"这世界就是很厉害"而没有价格标签的设定
- ❌ **地球换皮**：只改了颜色和名字，法则一模一样。至少一条法则必须是新的
- ❌ **数据打架**：`world.json` 里质量、半径、重力、密度四者不自洽（`validate` 会算）
- ❌ **检索堆砌**：把搜索结果整段贴进设定
- ✅ **每次改设定，`meta.version` +0.1，并在 `history.revisions[]` 留一条记录**

## 与「世界观构建」技能的分工

| | 盘古（本技能） | 世界观构建 |
|---|---|---|
| 层级 | **宇宙底层**：律、常数、星体、物质、生态 | **人文表层**：地区、势力、年表、地图、人物 |
| 输出 | `world.json`（axioms + cosmos + biosphere） | `world.json`（regions + factions + eras） |
| 关系 | **上游** | **下游** |

联动方式：盘古先跑完第 5 斧，把 `cosmology`/`physics`/`biology` 定为"不可违反的物理层"；再把 `world.json` 交给世界观构建，在其 `rules` 字段中声明"物理模型见上游"，后续地区与势力必须服从盘古设定的昼夜、季节、重力和能源。**顺序不能反**——先造地，再住人。

## 技能资源

| 文件 | 用途 | 何时加载 |
|---|---|---|
| `references/七斧创世法.md` | 每一斧的提问脚本、推导链、常见错误、检查点 | 开始任一新世界 |
| `references/公理库.md` | 60+ 条可复用反常识设定积木（物理/数学/化学/生物/宇宙/文明），含代价与痕迹 | 第 2–6 斧卡住时 |
| `references/检索与灵感策略.md` | 检索配方、query 模板、取反技巧、结果改写规范 | 每斧的"搜"环节 |
| `references/自洽性审查协议.md` | 五维十六问、致命项清单、修补话术 | 第 7 斧 |
| `references/world-schema.md` | `world.json` 全字段规范与最小示例 | 写 JSON 前必读 |
| `scripts/pangu.py` | 主 CLI：init / validate / preview / export / axioms / doctor | 每次操作 |
| `scripts/world_schema.py` | 结构校验、单位换算、天体物理计算、打分 | 被 import，勿单独运行 |
| `scripts/preview_template.html` | 3D 预览前端（Three.js，单文件自包含） | 被 `preview` 子命令读取 |
| `examples/helikon/` | 完整示例：「赫利孔」三阳世界 | 不确定标准时对照 |
| `AGENTS.md` | 通用 agent 指令文件（Codex/Amp/Jules 等直接读） | 宿主只认 `AGENTS.md` 时 |
| `install.py` | 一键把入口铺到各 harness | 首次安装 / 换宿主 |
| `adapters/mcp/pangu_mcp.py` | MCP stdio 服务器，把引擎暴露为 6 个 tool | 客户端只支持 MCP |
| `adapters/generic/BOOTSTRAP.md` | 纯对话版启动提示词（无文件系统也能用） | 宿主不能读文件 |
| `docs/跨harness移植说明.md` | 兼容矩阵、各宿主配置样例、排错 | 装载失败时 |

## 交付前的最后一句话

在给出成品前，问自己一句：**"如果我是一个住在这个世界里的物理学家，我会觉得哪条不对？"**

答不出来，才算造完了。
