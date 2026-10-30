# 盘古 1.1.1 Pangu

<img src="assets/icon.svg" width="72" align="right" alt="pangu">

[![version](https://img.shields.io/badge/version-1.1.1-E8B15C)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-4C7FA6)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-3776AB)](https://www.python.org)
[![agent skill](https://img.shields.io/badge/agent%20skill-SKILL.md-8A7BD6)](SKILL.md)
[![tests](https://img.shields.io/badge/selftest-22%2F22-3FA96A)](scripts/selftest.py)

**开天辟地式造世引擎** — 先立律，后长物。

一个**与宿主无关**的 agent 技能：从一句话种子出发，设定世界的数学 / 物理 / 化学 / 生物底层法则，再严格推导出它的山、水、生物与文明，最后给出可交互的 3D 预览。

不绑定任何平台。Claude、GPT、Gemini、本地模型，Claude Code、Codex、Cursor、Windsurf、Cline、Zed，或者你自己写的 harness —— 只要能读文件，就能用它；只要支持 MCP，就能把它当工具调。

> 地球不是模板，是一个样本。

---

## 1.1.1 新增了什么

1.1 让世界**跑起来**，1.1.1 补上它缺的那层：**地**。

- **行星地图**（`scripts/mapgen.py`）：从 `world.json` 推演整颗星球。板块按球面 Voronoi 切开，边界类型由相对运动判定；汇聚带隆起山脉，张裂带下陷，热点留下火山链。海平面不是手填的，由**水量与盆地容积**解出来；温度由年辐照、转轴倾角、大气温室与海拔递减推；降水由自转风带、海陆分布和迎风坡推；河流走洼地填充后的最陡下降与汇流累积。
- **七层图 + 交互页**：高程 / 群系 / 温度 / 降水 / 构造 / 宜居度 / 晕渲，加一张正射地球，再加 `map.html`（切图层、滚轮缩放、悬停读经纬度/海拔/温度/降水/宜居度）。
- **地图喂给 CA**：`map --write` 把 72×36 的宜居度/温度/高程粗场写进 `world.json`；CA 的初始分布按宜居度偏置，生产者的生长概率按宜居度缩放。生态相不再是均匀噪声。
- **CA 修了三个真问题**：逐规则邻居半径（以前半径 1 的规则会偷看半径 2 的邻居）、经纬网格按 cos(lat) 面积加权、`final_hash` 逐格复算（不只比六个 summary 数）。
- **示例赫利孔补了温室项**：10% CO₂ / 118 kPa 在旧数据里没有 `greenhouse_delta_k`，平衡温度 255 K 是颗雪球。补 33 K 后表面 288 K，海洋、降水、河流才成立——地图模块第一次跑就把这个漏洞照出来了。
- **校验 31 → 33 项**（`M10`/`M11`）；selftest 17 → 22 项；MCP 7 → 9 个 tool。

详见 [CHANGELOG.md](CHANGELOG.md)。

---

## 1.1 新增了什么

1.0 能把世界**造出来**，1.1 让世界**跑起来、验得过、能反驳**：

- **生态演化引擎**（`scripts/ca_engine.py`）：把 `biology.evolution` 编译成元胞自动机。每条规则必须带 `source` 指回设定字段，编译期就抓规则冲突与阈值不可达；`ca --check` 同 seed 复算，六项 summary 逐位对齐——抄来的数字会被打回。
- **零依赖出图**（`scripts/png_writer.py`）：纯 `zlib` + `struct` 写 PNG，不引 Pillow，`ca --run` 直接出快照序列图。
- **地面视角**：站在地表抬头，双日按球面三角真算的方位角 / 高度角走，影子方向 = 恒星方位 + 180°。
- **演化视图**：2D 生态相 + 密度曲线 + 天文强迫场 + 环境监测面板；曲线取最近 320 步滚动窗口，长时程不再糊成一片。
- **两个新体检**：`slice`（第一人称切片，两百字验尸）、`redteam`（红队审查，让 AI 扮演敌对物理学家提问，未结案不许交付）。
- **校验 17 → 31 项**，新增历法一致性、地面观察点、切片、红队、演化落地与周期性灾变证据。

详见 [CHANGELOG.md](CHANGELOG.md)。

---

## 怎么装（三种方式，任选其一）

```bash
python install.py --list        # 看所有安装目标

# A. 装成原生技能目录（Claude Code / Codex / Cline / OpenHands 等）
python install.py --target skill                       # → ~/.claude/skills/pangu

# B. 在项目里铺指针文件（Cursor / Windsurf / Gemini / Codex / Amp）
python install.py --target all --dest .

# C. 当 MCP 工具服务器用（Zed / Continue / Cherry Studio / Claude Desktop）
python install.py --print-mcp                          # 打印配置片段
```

`--dry-run` 可先预览会写哪些文件。安装器幂等，重复执行不会产生重复内容。

**纯对话环境**（网页版聊天、不能读文件的模型）：直接贴 `adapters/generic/BOOTSTRAP.md`，那是同一套方法论的压缩版。

### 兼容矩阵

| Harness | 入口 | 说明 |
|---|---|---|
| Claude Code / Claude.ai Skills | `SKILL.md` | 目录名建议 `pangu`，与 frontmatter 一致 |
| OpenAI Codex CLI / Amp / Jules | `AGENTS.md` | 每轮自动读取 |
| Cursor | `adapters/cursor/pangu.mdc` | 由 description 触发 |
| Windsurf | `adapters/windsurf/pangu.md` | `model_decision` 触发 |
| Gemini CLI | `adapters/gemini/GEMINI.md` | 项目根自动读取 |
| Cline / Roo / Kilo | `AGENTS.md` | 工作区规则 |
| Zed / Continue / Cherry Studio | `adapters/mcp/pangu_mcp.py` | MCP tool，9 个 |
| 任意纯对话模型 | `adapters/generic/BOOTSTRAP.md` | 粘贴即用 |

细节见 `adapters/README.md`，排错见 `docs/跨harness移植说明.md`。

---

## 三十秒上手

```bash
python scripts/pangu.py doctor                     # 环境自检

python scripts/pangu.py init --name "赫利孔" \
    --seed "三倍地球大，天上有两个太阳" --out out/helikon.json

# 按七斧填完 world.json 后
python scripts/pangu.py validate out/helikon.json --fix-hint
python scripts/pangu.py preview  out/helikon.json
python scripts/pangu.py export   out/helikon.json --md out/世界档案.md

# 1.1：体检 + 演化
python scripts/pangu.py slice    out/helikon.json --check    # 第一人称切片体检
python scripts/pangu.py redteam  out/helikon.json --check    # 红队体检
python scripts/pangu.py ca       out/helikon.json --run      # 生态演化 + 快照图
python scripts/pangu.py ca       out/helikon.json --check    # 同 seed 复算比对

# 1.1.1：行星地图
python scripts/pangu.py map      out/helikon.json --run      # 七层图 + 正射地球 + map.html
python scripts/pangu.py map      out/helikon.json --check    # 同 seed 复算 + 六项体检
python scripts/pangu.py map      out/helikon.json --write --yes  # 写回摘要与 CA 粗场
```

`preview` 生成的 HTML 双击即开，不需要服务器、不需要构建、不需要联网（首次需从 CDN 取一次 Three.js，之后走缓存；完全离线时会降级为数据视图）。

---

## 它解决什么问题

普通的世界观生成有三个死穴：

| 病灶 | 症状 | 盘古的解法 |
|---|---|---|
| 倒因为果 | 先想要龙，再补物理，设定互相打架 | **七斧顺序**：物理层没立完，不许谈生物 |
| 地球换皮 | 改颜色改名字，法则一模一样 | **逆行律**：至少一个底层维度必须与直觉相反 |
| 无代价奇观 | 越夸张越没解释，一问就崩 | **代价律 + 痕迹律**：每个奇观标价，且必须留下可观测痕迹 |

---

## 核心概念

### 三律（缺一不可）

1. **逆行律** — 这世界哪条常识是反的？
2. **代价律** — 为了得到它，失去了什么？（必须可量化）
3. **痕迹律** — 居民抬头能看见什么异常？

### 七斧

```
混沌 → 分判 → 立律 → 炼质 → 化生 → 启智 → 演界
定调    定天    定法    定料    定活    定人    定史
```

每斧三步：**问**（2–3 个有区分度的问题）→ **搜**（网页检索校准）→ **定**（写入 JSON 并自检）。

### 检索四类

**锚定**（真实数值）｜ **证伪**（为什么不行）｜ **取反**（极端案例再推远）｜ **质感**（意象与配色）

其中「证伪」不可省——**先找它为什么不可能，再解释它为什么可能**。

---

## 目录结构

```
盘古/
├── SKILL.md                    技能正文（Agent Skills 开放格式）：三律、七斧、命令速查
├── AGENTS.md                   通用 agent 指令入口（Codex / Amp / Jules / Cline…）
├── install.py                  跨 harness 安装器（skill / agents / cursor / windsurf / gemini / mcp）
├── README.md                   本文件
├── adapters/                   入口适配层（不含业务逻辑，只做加载）
│   ├── README.md               兼容矩阵与排错
│   ├── claude/CLAUDE.md        项目级入口
│   ├── cursor/pangu.mdc        Cursor 规则
│   ├── windsurf/pangu.md       Windsurf 规则
│   ├── gemini/GEMINI.md        Gemini CLI 入口
│   ├── generic/BOOTSTRAP.md    纯对话版（自包含提示词）
│   └── mcp/pangu_mcp.py        MCP stdio 服务器（零依赖，9 个 tool）
├── docs/
│   ├── 开发文档-v1.0.md         1.0 架构、算法、接口、验收矩阵、路线图
│   ├── 开发文档-v1.1.md         1.1 范围、四项功能定义、验收门槛
│   ├── 开发文档-v1.1.1.md       1.1.1 行星地图与 CA 强化：数据契约、算法、验收
│   ├── 跨harness移植说明.md     各宿主加载机制、配置样例、排错
│   ├── 3D预览层规范.md          渲染层技术规格
│   └── 优化建议.md              已知短板与改进方向
├── references/
│   ├── 七斧创世法.md            每斧的提问脚本 / 推导链 / 常见错误
│   ├── 公理库.md                62 条反常识积木（含代价与痕迹）
│   ├── 检索与灵感策略.md        四类检索配方与取反技巧
│   ├── 自洽性审查协议.md        五维十六问
│   └── world-schema.md          JSON 全字段规范 + 机检清单
├── scripts/
│   ├── pangu.py                 CLI：init / validate / preview / export / axioms / doctor
│   │                                / slice / redteam / ca / map
│   ├── world_schema.py          校验内核：天体物理计算、评分、公理库解析
│   ├── ca_engine.py             生态演化引擎：编译、跑、复算比对、地图耦合
│   ├── mapgen.py                行星地图引擎：板块、海平面、气候、河网、群系、出图
│   ├── png_writer.py            零依赖 PNG 编码器（zlib + struct）
│   ├── preview_template.html    单文件预览模板（Three.js 3D + 地面视角 + 演化视图）
│   └── selftest.py              验收自测（对齐开发文档 §9）
└── examples/helikon/            完整示例「赫利孔」三阳世界
    ├── world.json
    ├── preview.html
    ├── 世界档案.md
    ├── 审查报告.json
    ├── surface.png              地面视角截图
    ├── evolution.png            演化视图截图
    └── map/                     行星地图：七层图 + 正射地球 + map.html + CA 快照
```

---

## 示例：赫利孔

一颗**三倍地球半径**的岩石行星，天上**两个太阳**。

这句话在地球物理下是自相矛盾的：半径 3 R⊕ 的岩石行星会吸积成迷你海王星，失去固体表面。盘古的处理是给它标价：

- **改 G**：G' = 0.60 G，使 26.4 M⊕ 的表面重力停在 1.76 g，地壳撑得住
- **压双星**：间距压到 0.30 AU，行星放在 1.20 AU（4 倍间距，稳定）
- **捡了个便宜**：周期比 = (a_行星/a_双星)^1.5 = 4^1.5 = **8**。一年恰好八个双星周期，历法不需要闰日——这是开普勒第三定律的必然，不是设定者的巧合
- **代价**：每 44 天一次潮汐应力峰值，全球每年 1.1 万次 4 级以上地震；造山带沿潮汐节拍分布
- **痕迹**：两道颜色不同的影子；每 44 天一次 90 分钟的「双星合」；日落后天空是钴蓝而非黑色

自洽评分 100/100（0 fatal / 0 warn）。

---

## 与「世界观构建」技能的关系

| | 盘古 | 世界观构建 |
|---|---|---|
| 层级 | 宇宙底层：律、常数、星体、生态 | 人文表层：地区、势力、年表、地图 |
| 输出 | axioms + cosmos + biosphere | regions + factions + eras |

**盘古是上游**。先造地，再住人。顺序不能反。

---

## 依赖与限制

- Python ≥ 3.9，**零第三方包**（安装器、CLI、MCP 服务器全都只用标准库）
- 3D 层需要浏览器支持 WebGL；Three.js 从 CDN 加载，带四路回退与离线降级页
- 3D 图**不表示真实比例**：轨道与天体半径采用双尺度压缩（数量级差 5 位以上，同屏无意义）
- 浏览器端演化是延续轨迹，与 Python 端复算存在少量统计残差，面板里直接显示偏差百分比
- 平衡温度公式忽略温室效应，实际表面温度可能高 30–50 K
- 检索能力由宿主提供，盘古只给出检索配方；无联网时"搜"环节退化为"凭知识锚定"，仍可产出但校准变弱

---

## 许可

MIT。改设定只改 `world.json`，然后重跑脚本——不要手改生成物，否则文档、3D 与报告会互相漂移。
