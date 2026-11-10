---
name: pangu
description: 盘古 1.1.6 · 开天辟地式造世引擎。以"律先于物"为原则，先设定世界底层的数学/物理/化学/生物法则，再推导其宏观与中观形态，突破"行星绕恒星、碳基需氧"的地球桎梏，造出三倍地球大的双日照地、无恒星的能量世界、非欧几何宇宙等"理论上不该存在却完全自洽"的虚拟世界。能从设定推演整颗行星的地图（板块→盆地→水量定海平面→年辐照定温度→风带与迎风坡定降水→洼地填充定河网→群系），再让元胞自动机按宜居度长生态；1.1.2 把"改设定"变成可验证的操作（patch 定点改/增/查并自动升版本记修订，sweep 沿单个参数扫出连续谱与崩点，diff 对比两版并列出必须重跑的下游产物，公理库按代价类型检索，反常识度指数给出"换皮还是过度"的量化参照），同时补上"人"：用第一人称寄宿行星上的某一物种、在低多边形地表行走（WASD/鼠标可操控），为行星与生物声明元素含量配比与生命基座（碳基/硅基/碳硅杂合/其他），并按「气」半包围 +「钅」+ 单字的造字法设计世界特有的新元素及其相态、丰度、生态作用与代价。1.1.3 把七斧流程做成了可执行的状态机：`plan` 读 world.json 判定当前在第几斧、还缺哪些字段、这一斧该问什么、下一步该跑哪条命令，并给出六项交付门槛；`options` 提供按斧分段的「命题 → 互斥选项 → 代价」菜单（31 个命题 / 132 个选项，含 5 个标签的互斥机制，采纳后写进 seed.brief 并自动升版本）；`entail` 从已立之律机械推出居民必然会看见的现象（30 条后果规则：双影、恒黑之天、固定的晨昏线、没有翅膀、不用闰的年……），并按编号幂等回写天象、检出被改设定弄失效的旧推论；`review` 把八项体检（自洽 / 反常识度 / 切片 / 红队 / 地图复算 / 演化复算 / 推论失效 / 选项卡一致）汇成一条命令与一个「能不能交」的判断，`whatif` 在内存副本上改设定、推演「世界会变成什么样」（重力怎么动、哪条必然推论消失、先崩在哪一环）且永不写原世界；1.1.4 补上"抬头"这一层：`sky` 把 world.json 里已经写好的观测点、倾角、大气、恒星、卫星算成一张今夜星图（天光亮度、极限星等、地平线上可见星数、银河可见性、每颗恒星的 alt-az 与视星等）与一张一年昼长表，星表按 seed 确定性生成、不引真实星表；`whatif --sky` 让「改一个数，今夜星空会怎样」当场可见；世界档案的第一屏换成「第一眼·星图」。1.1.5 把「离地球差多少」变成可执行的账：`kernel` 一条命令跑完八个物理内核（PDE 热传导/平流/浅水、Budyko–Sellers 能量平衡、灰体辐射与水汽反馈、固体地球边界层标度、辛积分轨道与潮汐、碳-硅酸盐恒温器、Hubbell 中性群落的物种-面积指数、量纲硬域）并对解析解与公开数；`ledger` 出四本守恒账（能量/水/碳/元素，残差带容差），不平就点名——它建账第一天就抓到「声明温室 33 K 与 10% CO₂ 该有的 51.5 K 差 18.6 K」；`uq` 给每个派生量配 ±（地球平衡温度 254.3 ± 4.6 K），`certify` 把关键结论分成算出来的 / 半算半填 / 经验式 / 作者拍的并给覆盖率，`replay` 从 seed 重放 map 与 ca 对账 hash；`patch` 接入量纲硬域（把 1e9 写进温度字段直接拒绝），`benchmark` 从 6 条扩到 25 条，`review` 九项扩到十一项；生成的预览页多一个「账本」页签，把覆盖率环形图、误差条、四本守恒账、八个内核格子、可复算 hash 与基准偏差表全部画出来。全程以多轮对话与用户共创、以网页检索抓取前沿科学与奇想作为灵感对照，产出自洽性审查报告、结构化 world.json、通俗世界档案、行星地图与可交互 3D 预览页。当用户提出"造一个世界/宇宙""设计一个星球的物理法则""如果重力反过来会怎样""做一个不靠太阳的生物圈""写一个双恒星世界的设定""给小说/游戏做底层宇宙规则""做个能转的 3D 星球预览""推演一张星球地图""改一下这个世界的重力/参数看看会怎样""对比这两版设定""让我用这个星球上生物的视角走一走""这个世界的生物是碳基还是硅基""设计几种这个世界独有的元素""我现在造到第几步了""下一步该干什么""给我一些设定选项""这个设定必然导致什么现象""这个世界能交付了吗""全部体检一遍""如果当初选另一条会怎样""把重力再调低 30% 会崩吗""这个世界的夜空有多亮""抬头能看见什么星""画一张星图""这个星球养得活多少人""这东西离地球有多远""这三千年里发生了什么""给我一条编年史""这段历史是不是编的"等需求时使用。1.1.6 把最后一块散文补成推演：`chronicle` 用承载力与历法反解出文明的时间轴（19 条规则：第一笔 / 定历 / 立禁 / 种子入土 / 城市 / 文字 / 出海 / 成国 / 争地 / 大疫 / 变法 / 国教 / 顶点 / 余波，外加双日之民 / 没有黑夜 / 两段睡眠 / 晨昏线四条异物理事件），每条事件带 src 出处与强度、同 seed 可复算 hash；`--check` 能指出哪条史书的依据已经失效、哪条人口超过了地能养的上限；`review` 因此多出 D12 编年。
license: MIT
metadata:
  title: 盘古 1.1.6 · 开天辟地造世引擎
  version: 1.1.6
  entrypoint: scripts/pangu.py
  runtime: python>=3.9 (仅标准库)
  install: python install.py --target all
---

# 盘古 1.1.6 · 开天辟地造世引擎

盘古不是"写设定"，是**立律**。区别在于：设定回答"这个世界有什么"，律回答"这个世界为什么只能长成这样"。

地球不是模板，是**一个样本**。世界的引力常数可以不是 6.674e-11，光速可以不是 c，碳可以不是生命骨架，一天可以不是自转给的。本技能的任务是：让用户（或你）重写这些常数与规则，然后严格推导——推导出山怎么长、雨怎么下、生物怎么喘气、文明怎么计时——直到它**自洽到能骗过物理学家**，同时**奇诡到没人想过**。

1.1.1 补上了 1.1 缺的那层：**地**。`map` 子命令从设定推演整颗行星——板块碰撞长出山脉，水量与盆地容积共同定海平面，年辐照与温室定温度，风带与迎风坡定降水，洼地填充定河网，最后用世界自己声明的群系高程带划出沙漠、森林、冰盖。地图还会喂给 `ca`：宜居度高的格子先长生产者，生长概率按宜居度缩放。

1.1.2 补的是**改动本身**。世界不是一次写完的，是在「改一个数 → 看它崩不崩 → 对比上一版」里长出来的。所以这一版加了调参层：`patch` 按点路径改 / 增 / 查字段，写盘即升版本、记修订；`sweep` 沿单个参数扫出连续谱，标出安全窗与第一个崩点；`diff` 对比两版并推断哪些下游产物必须重跑；公理库多了按代价类型的二次索引；`validate` 多了一个 0–100 的反常识度指数，用来判断「仍是换皮」还是「已超出可理解范围」。

1.1.3 补的是**路标**与**选项**。世界不是一次写完的，也不是靠灵感堆出来的。`plan` 把七斧从文档里的表变成引擎里的状态机——任何时刻一条命令就能回答「我在第几斧、还缺什么、下一步问什么、跑什么命令」，外加六项交付门槛；`options` 把「这一斧必须回答哪些问题、每个问题有几种活法」做成 31 个命题 / 132 个选项的菜单，每个选项都标着代价、痕迹和要顺手写的字段，用 `-标签` 表达互斥；`entail` 则反过来，从已立之律推出居民**必然**会看见的现象（30 条规则），并把这些现象按编号幂等写回天象表，改设定后还能指出哪条旧推论已经失效。三者串成一条循环：`plan` 指路 → `options` 给活法 → `patch` 落地 → `validate --brief` 复检 → `entail` 推出痕迹 → `slice` / `map` / `ca` / `redteam` 验证 → 回到 `plan`。

1.1.4 补的是**抬头**。前几版把世界造得越来越完整，可观众的第一屏始终是参数表。这一版把已经写在 world.json 里的观测点、自转与倾角、大气、恒星与卫星算成三样东西：一张今夜星图（`sky`）、一张一年昼长表（`sky --year`）、一句「改一个数，今夜会怎样」（`whatif --sky`）。天光是**经验模型**：空气辉光 21.9 mag/arcsec² 打底，叠暮光、叠明亮点光源的散射、叠气压带来的尘埃散射，误差 ±0.5 等，输出里全程标着「简化模型」。星表由 `(seed, count, color_mix, galaxy)` 确定性生成、`--check` 可复算——它是**这个世界的**星表，不是 Gaia/HYG 的转述，也不是「真实天空」。赫利孔算下来是一张尴尬的图：三颗恒星的照度把夜空压在 19 等上下，肉眼只剩两百来颗星，银河被洗掉了；对照组 `examples/aster/`（一颗 G2V、一天 24 小时）则是一夜两千六百多颗、银河横过天顶。一个引擎，两张天。

同一天还补了三件「对着真实世界」的欠账，口径与上一段相反：不再加画面，而是**加对表**。`benchmark earth` 把地球参数喂进引擎，六条曲线（纬向年均温、纬向年降水、昼长、逃逸速度、平衡温度、陆地 NPP）对公开数据，出偏差表——**它是唯一能证明「这是模型不是美术」的东西**。建这张表的第一天就抓出两处真错：极区蒸发被 `temp<268` 一刀切归零（导致极地下不了雨），以及副热带下沉支根本没建模（导致 25° 比赤道还湿）；修完纬向降水的相关系数从 0.40 升到 0.82。`capacity` 用 Miami 模型把气候场积成 NPP，再按可采收比例折算人口上限——第一次能回答「这颗星球养得活多少人」。`map --season` 用已算好的倾角跑冬至/夏至两套气候，出四张图。温室也从「手填一个 ΔT」变成「由 CO₂/CH₄/N₂O 分压估，声明值优先」，于是 CO₂ 真的能改变世界（`33 + 4.28·ln(CO₂e/560)`，翻倍 +2.97 K，正好是 AR6 的最佳估计）。

1.1.3 还顺手堵了十三处小口子：`validate --brief`（一行结论）、`axioms --axe`（按斧位查积木）、`sweep --log`（等比采样）、`patch --suggest`（给出自洽的密度/重力建议值）、`doctor` 的版本一致性自检、`diff` 的斧位对比、档案里的「创作路线」、`slice --prompt` 的四种视角、`R01`（选项卡一致性）、MCP 15 个 tool、selftest 52 项。

1.1.6 补的是**时间**。前几版把律、地、天都算出来了，唯独「人」这一层只有散文：`civilization` 是一段自我介绍，`history.eras` 是三个手写的标题。这一版补上时间轴，用的还是同一种办法——**不编故事，只做正向推导**：承载力 → 人口曲线（logistic）→ 人口刻度 → 事件时刻 → 事件文案。19 条规则（H01–H23）里，年长来自 `calendar.year_days`，人口上限来自 `carrying_capacity.humans_subsistence`，「定历」来自 `year_days ÷ month_days` 的余数，禁忌、能源、技术路径、社会形状直接引用 `civilization.*` 的原文，国教锚定 `sky_phenomena` 里最显眼的一条。事件时刻由 logistic **反解**，所以改一次承载力，整条时间轴都会动。每条事件都带 `src` 出处与 `strength`（必然 / 很可能）；`--check` 用 seed 重推对 hash，手改一句就报错、引用失效会点名、人口越过承载力会被判「史比地能养的多」；`review` 因此多出 **D12 编年**。赫利孔算下来 18 条事件、跨度 21,116 年：第 367 年一年正好 8 个月不需要闰日，顶点只到理论上限的 **4.6%**——那个百分比是引擎给的，不是史书给的。

同一版里主产物也打通了：`preview` 的 dock 上多一个「地图」按钮，点了开同目录的 `map.html`（新窗口，1440×720 原生渲染）。**别把 180×90 的场塞进预览页放大**——试过，糊。同目录没有 `map.html` 或加了 `--no-map` 时按钮隐藏。`map.html` 这一版补上了每层图例：色带由渲染用的 ramp 直接生成、标尺用渲染用的同一份 ranges，切层即换（群系给色块，板块给边界与热点）。

回看上一版：1.1.2 补的是「人」这一层。预览页多了**生物视角**：选一个物种寄宿进去，用它的眼高、步速和重力在行星表面行走（WASD / 鼠标，低多边形、Minecraft 那一档的方块生物），HUD 直接告诉你它的基座、主元素与体成分。为此 world.json 新增三块可声明数据：`chemistry.composition`（行星 / 大气 / 海洋的元素配比，三项各自归一）、`biology.biochemistry`（碳基 / 硅基 / 杂合，主元素、结构元素、溶剂、代价，以及 `composition` 体成分）与 `biology.organisms[]`（可操控物种的体高、步速、感官、配色与体成分）。世界若存在超出地球周期表的新元素，写进 `chemistry.fictional_elements[]`，命名文法固定为 `⿸气⿰钅X`：半包围的「气」包住「钅」与一个自选单字，字形用 Unicode 表意描述序列无损传递，预览页会把它画成一枚拼合字。

## 宿主无关：这份技能不绑定任何一家 agent

本技能刻意只依赖三样东西：**Markdown 文本**（你能读）、**Python 标准库**（无需 pip）、**本目录内的文件**。没有厂商 API、没有平台专有工具、没有联网必需项（检索能力用不用都能跑，只是没有检索时灵感校准会弱一档）。

因此它可以用三种方式被任意 agent / harness 加载，任选其一：

| 方式 | 适用宿主 | 加载什么 |
|---|---|---|
| **A. 原生技能目录** | Claude Code / Claude.ai Skills、OpenAI Codex、Cline、Roo、OpenHands、以及任何支持 `SKILL.md` 约定或"把目录塞进上下文"的框架 | 整个目录，入口 `SKILL.md` |
| **B. 指令文件指针** | Codex / Amp / Jules（`AGENTS.md`）、Cursor（`.cursor/rules/*.mdc`）、Windsurf（`.windsurf/rules/*.md`）、Gemini CLI（`GEMINI.md`） | 只写一个几十行的指针文件，告诉它去哪读 `SKILL.md` |
| **C. MCP 工具服务器** | 任何支持 MCP 的客户端（Claude Desktop、Cursor、Zed、Continue、Cherry Studio、自研 harness） | `adapters/mcp/pangu_mcp.py`，把引擎暴露成 21 个 tool |

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

| # | 斧 | 中文 | 干什么 | 写进 world.json | 典型问题 | 这一斧的菜单 / 工具 |
|---|---|---|---|---|---|---|
| 1 | Chaos | 混沌 | 采集种子意象、美学基调、禁忌 | `meta` `seed` | "一句话说出这世界最怪的一幕" | `options --axe 1`（Q1.1–Q1.4） |
| 2 | Dichotomy | 分判 | 时空框架、宇宙拓扑、有无恒星 | `cosmology` | "天上有什么？几颗？有没有'天'？" | `options --axe 2`（Q2.1–Q2.5，选项最多的一斧） |
| 3 | Nomos | 立律 | 物理常数、守恒律改动、新相互作用 | `physics` `mathematics` | "哪条守恒律被打破了？" | `options --axe 3` + `axioms --axe 3` + `sweep --list` |
| 4 | Materia | 炼质 | 元素表、键合规则、材料与相态 | `chemistry` | "最硬的物质是什么做的？" | `options --axe 4` + `axioms --axe 4` |
| 5 | Genesis | 化生 | 能量货币、遗传载体、生态金字塔 | `biology` | "生物靠吃什么活着？" | `options --axe 5` + `ca` |
| 6 | Anima | 启智 | 意识、社会、技术的另类路径（可选） | `civilization` | "他们怎么计时？怎么知道一年过去了？" | `options --axe 6`（不写就填 `exists:false`） |
| 7 | Cosmogony | 演界 | 历史推演、自洽审查、3D 呈现、交付 | `history` `consistency` `narrative` | "这世界会怎么灭亡？" | `options --axe 7` + `entail` + `chronicle` + `map` / `slice` / `redteam` / `export` |

**硬约束**：第 3 斧（立律）结束前，不得讨论任何具体生物或文明。先有律，后有物。违反即"倒因为果"，会被审查器判为致命错误。

## 一张图：每轮只跑三条命令

不要凭记忆推进七斧。**每一轮都从 `plan` 开始**，它读 `world.json` 告诉你现在在哪一斧、还缺什么、下一步跑什么：

```bash
python scripts/pangu.py plan out/world.json          # 现在第几斧 / 缺什么 / 下一步命令
python scripts/pangu.py options --axe 3 --roll 2     # 这一步有哪些活法（带代价与痕迹）
python scripts/pangu.py validate out/world.json --brief   # 一行复检：分数 / 斧位 / 下一步
```

循环的形状是固定的：

```
plan ──▶ options（选或自创）──▶ patch（落地）──▶ validate --brief ──▶ plan …
                                                        │
                                        七斧收齐后 → entail → map / ca / slice / redteam → review → preview / export
                                                                                              ▲
                                     anywhere：whatif（"如果改这一条会怎样"）─────────────────┘
```

三条铁律：

1. **斧位由字段决定，不由自述决定**。你说「我写到第 5 斧了」不算，`plan` 说算才算。
2. **`plan` 报告 ≠ 审查通过**。它只回答「能不能往下走」，能不能交付看 `review`（十二项体检，一个判断）。
3. **每斧都要能答出「代价」**。答不出的选项，用 `options` 换一张，别硬写。

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

## 想象力的两个供给口：选项卡与必然推论

盘古不靠灵感，靠**菜单**与**推导**。

### 选项卡：先知道有几条路，再选一条

`references/选项卡.md` 有 31 个命题（Q1.1 … Q7.4），每个命题 2–5 个**互斥**选项，每个选项五格：

| 格 | 意思 | 例 |
|---|---|---|
| 设定 | 一句话说清这条路是什么 | 「引力改号，同质量相斥」 |
| 代价 | 必须付的账，可量化 | 「物质无法靠引力聚集成团，没有星球」 |
| 痕迹 | 居民抬眼能看见的异常 | 「抛出的石头加速飘向天顶」 |
| 连锁 | 要顺手写哪些字段 | `physics.new_interactions`、`broken_symmetries` |
| 标签 | 互斥标记，`-` 前缀表示排除 | `-正引力`、`斥力` |

用法：

```bash
options --axe 3                       # 看第 3 斧全部命题与选项
options --axe 3 --roll 2 --seed 7     # 抽 2 张（同 seed 可复算）
options world.json --adopt "Q3.1=B"   # 采纳：写进 seed.brief.choices，自动升版本记修订
options world.json --check            # 体检：卡间互斥 / 卡与世界对不上 / 还剩几题没答
```

三条用法约定：

1. **可以不选**。菜单只负责让你知道还有别的活法；自己写第六个答案也是合法答案。
2. **采纳不等于改数据**。`--adopt` 只记决策，不会帮你删掉 `cosmology.stars`——落差由 `R01` 提醒，改数据是下一步的事。
3. **互斥会被拒绝**。`-有恒星` 撞上别人的 `有恒星`，`--adopt` 直接退 2；确认要覆盖才加 `--force`。

### 必然推论：把「想不出来」变成「算出来」

第 7 斧最容易空着的是 `sky_phenomena`——现象靠想，想不到就整层空缺。`entail` 反过来做：从你已经立好的律，机械推出居民**必然**会看见什么。

```bash
entail world.json                 # 只看（36 条规则命中几条）
entail world.json --write --yes   # 按 〔entail E01〕 标记幂等回写 sky_phenomena
entail world.json --check         # 改了设定后，哪些旧推论已经失效
```

例：行星周期 355.9 d ÷ 双星互绕 44.49 d = 8.00 → 「一年正好 8 个双星周期，历法不需要闰日」。**这不是设定者的巧思，是开普勒第三定律的结算。** 这样的句子比任何形容词都更像一个真实的世界。

两条约定：

- **只正推，不反推**。先有常数，再出现象；从现象倒推设定就是倒因为果。
- **强度只有两档**：`必然`（可由数值直接算出）、`很可能`（生态与社会的合理外推）。

### 收尾与试错：`review` 与 `whatif`

**`review` — 交付体检。** 交付前跑过六条命令的人都知道漏一条有多容易。`review` 把它们汇成一条：十二项（自洽 / 反常识度 / 切片 / 红队 / 地图复算 / 演化复算 / 推论失效 / 选项卡一致 / 地球基准 / 守恒账本 / 适用域 / 编年史）+ 一个判断 + 按修复顺序排好的清单。**只读**，可以反复跑。

```bash
review world.json            # 十二项体检，给「能不能交」
review world.json --fast     # 跳过地图/演化复算，秒级（循环末尾用）
review world.json --strict   # 硬门槛未过即退出码 1（CI 用）
```

**`whatif` — 反事实推演。** 设定是选出来的，但选之前没人知道另一条会怎样。`whatif` 在内存副本上改设定，回答「世界会变成什么样」：重力怎么变、哪条必然推论消失、审查从哪一条开始崩、要重跑什么。

```bash
whatif world.json --scale "physics.constants[0].world_value=0.7" --recalc
whatif world.json --set "cosmology.bodies[0].albedo=0.6"
```

与 `sweep` 的分工：`sweep` 扫一个数、只回答「哪一步崩了」；`whatif` 任意多字段、回答「世界变成什么样」。**它永远不写原世界**，要留下这次假设才 `--write out/假设.json`。没有「也许」。

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
| 呈现层 | `preview.html` | 3D 预览（多恒星系统 + 行星特写 + 双光源昼夜）+ 地面视角 + 演化视图 + 生物视角（可操控第一人称） |
| 阅读层 | `世界档案.md` | 通俗版，含"三律"、常数表、生态、文明、审查报告 |
| 审查层 | `审查报告.json` | 五维评分 + 致命项 + 修补建议（`export --json-out` 产出） |

**单一数据源原则**：`preview.html` 与 `世界档案.md` 全部由 `world.json` 生成。禁止手改生成物，否则 3D 与文档会漂移。

## 命令速查

命令中的 `scripts/` 相对**本技能目录**；路径建议一律用绝对路径。

```bash
# 0. 环境自检（python 版本、模板是否存在、CDN 可达性、五处版本号是否一致）
python scripts/pangu.py doctor

# 0.5 导航与供给（每一轮都从这三条开始，别凭记忆推进）
python scripts/pangu.py plan out/world.json                 # 第几斧 / 缺什么 / 该问什么 / 下一步命令
python scripts/pangu.py plan out/world.json --brief         # 一行结论：分数 / 斧位 / 下一步（循环里用）
python scripts/pangu.py plan out/world.json --next          # 只吐下一条命令
python scripts/pangu.py options --axe 3                     # 第 3 斧的命题与全部选项
python scripts/pangu.py options --axe 2 --roll 2 --seed 7   # 抽 2 张卡（带代价与痕迹，可复算）
python scripts/pangu.py options out/world.json --adopt "Q3.1=B"   # 采纳：写 seed.brief，自动升版本
python scripts/pangu.py options out/world.json --check      # 卡间互斥 / 卡与世界对账 / 还剩几题没答
python scripts/pangu.py entail out/world.json               # 从已立之律推出居民必然看见什么
python scripts/pangu.py entail out/world.json --write --yes  # 幂等回写 sky_phenomena（〔entail E01〕）
python scripts/pangu.py entail out/world.json --check        # 改了设定后，哪些旧推论已经失效
python scripts/pangu.py entail --list                        # 36 条规则：编号 / 触发条件 / 强度
python scripts/pangu.py entail out/world.json --exclude E02  # 反向点名（与 --only 互补）

# 0.6 收尾与试错
python scripts/pangu.py review out/world.json                # 十二项体检，一个「能不能交」的结论
python scripts/pangu.py review out/world.json --fast         # 跳过地图/演化复算（秒级）
python scripts/pangu.py review out/world.json --strict       # 硬门槛未过即退出码 1
python scripts/pangu.py whatif out/world.json --scale "physics.constants[0].world_value=0.7" --recalc
python scripts/pangu.py whatif out/world.json --set "cosmology.bodies[0].albedo=0.6" --json
python scripts/pangu.py whatif out/world.json --set "cosmology.bodies[0].axial_tilt_deg=80" --sky

# 0.7 抬头（1.1.4）：把已写好的观测点/倾角/大气/恒星算成星图
python scripts/pangu.py sky out/world.json                   # 今夜：天光 / 极限星等 / 星图 / 关键天体
python scripts/pangu.py sky out/world.json --at "日落后 2h"   # 相对时刻；也可 "22:10" / "双星合前 30m"
python scripts/pangu.py sky out/world.json --year            # 一年昼长与极昼极夜
python scripts/pangu.py sky out/world.json --allnight        # 一夜六帧
python scripts/pangu.py sky out/world.json --check           # S01 星表可复算 / S02 摘要一致 / S03 文本对账
python scripts/pangu.py sky out/world.json --md out/今夜.md   # 星图 PNG + 逐月表，直接贴进档案
python scripts/pangu.py sky out/world.json --write --yes     # 回写 cosmology.sky 与 starfield.hash

# 0.8 对表与承载（1.1.4 增补）：引擎离地球多远 / 这颗星球养得活多少人
python scripts/pangu.py benchmark earth                      # 25 条曲线对公开数据，出偏差表
python scripts/pangu.py benchmark earth --json               # 给 agent
python scripts/pangu.py capacity out/world.json              # NPP → 人口上限
python scripts/pangu.py capacity out/world.json --write --yes  # 回写 biology.carrying_capacity
python scripts/pangu.py map out/world.json --season --run    # 冬至 / 夏至双图

# 0.9 守恒与误差（1.1.5）：把「我错多少」变成可读的表
python scripts/pangu.py kernel                               # 八个物理内核一轮自检（1.2–1.8）
python scripts/pangu.py kernel --only pde,radiation --json    # 只跑这两项
python scripts/pangu.py ledger out/world.json                 # 四本账：能量/水/碳/元素，带容差
python scripts/pangu.py ledger out/world.json --write --yes   # 回写 conservation.ledger
python scripts/pangu.py certify out/world.json                # 哪些是算的、哪些是拍的（含覆盖率）
python scripts/pangu.py certify out/world.json --md out/误差表.md  # 出表，可直接并进档案
python scripts/pangu.py certify out/world.json --write --yes  # 回写 certification
python scripts/pangu.py replay out/world.json                 # 从 seed 重放 map / ca，对 hash
python scripts/pangu.py replay out/world.json --seed 12345    # 换 seed 就该不同（预期）
python scripts/pangu.py preview out/world.json --fast          # 预览页的「账本」页签（0.3 秒）
python scripts/pangu.py preview out/world.json --replay        # 同上，但真重放对 hash（两分钟）

# 0.95 编年（1.1.6）：这三千年里发生了什么
python scripts/pangu.py chronicle out/world.json               # 从承载力推出整条文明史
python scripts/pangu.py chronicle out/world.json --list        # 19 条规则：编号 / 触发条件 / 强度
python scripts/pangu.py chronicle out/world.json --seed 7      # 换一种抖动（同 seed 可复算）
python scripts/pangu.py chronicle out/world.json --from-year 8000 --to-year 14000   # 时间轴回放
python scripts/pangu.py chronicle out/world.json --kind war    # 只看某一类事件
python scripts/pangu.py chronicle out/world.json --md out/编年史.md
python scripts/pangu.py chronicle out/world.json --write --yes # 回写 history.chronicle
python scripts/pangu.py chronicle out/world.json --check       # hash 复算 / 引用失效 / 人口越界

# 1. 从种子生成骨架 world.json（先填 meta/cosmology 占位，后续斧头逐段补写）
python scripts/pangu.py init --name "赫利孔" --seed "三倍地球大，天上有两个太阳" --out out/world.json

# 2. 校验 + 自洽打分（可机检部分）
python scripts/pangu.py validate out/world.json
python scripts/pangu.py validate out/world.json --brief    # 一行式：分数 / fatal / 斧位 / 下一步
python scripts/pangu.py validate out/world.json --strict   # 有 fatal 即非零退出

# 3. 生成 3D 预览页
python scripts/pangu.py preview out/world.json -o out/preview.html   # 3D + 地图 + 账本 + 星图，单文件
python scripts/pangu.py preview out/world.json --no-map              # 不挂「地图」入口

# 4. 生成世界档案 Markdown
python scripts/pangu.py export out/world.json --md out/世界档案.md

# 5. 查公理库（可复用的反常识设定积木）
python scripts/pangu.py axioms              # 列全部
python scripts/pangu.py axioms --domain physics --roll 3   # 物理类随机抽 3 条
python scripts/pangu.py axioms --cost-list  # 代价类型索引（时间/空间/能量/…）
python scripts/pangu.py axioms --cost 空间 --roll 3        # 「我想让远行变得不可能」
python scripts/pangu.py axioms --axe 3 --roll 3            # 按斧位过滤：立律斧只看物理积木

# 6. 改设定（不要手改 JSON；patch 会自动升版本、记修订、立刻体检）
python scripts/pangu.py patch out/world.json --get "physics.constants[0].world_value"
python scripts/pangu.py patch out/world.json --set "physics.constants[0].world_value=3.6e-11"
python scripts/pangu.py patch out/world.json --set "seed.new_key=1" --create   # 新建字段
python scripts/pangu.py patch out/world.json --set "..." --dry-run            # 只看不写
python scripts/pangu.py patch out/world.json --set "cosmology.bodies[0].mass_earth=30" --suggest
                                                                        # 改完顺带给出密度/重力的自洽值

# 7. 扫参数（沿一个数扫出连续谱，找安全窗与崩点）
python scripts/pangu.py sweep out/world.json --list                        # 可扫哪些参数
python scripts/pangu.py sweep out/world.json --param "cosmology.bodies[0].mass_earth" --percent 30 --steps 7 --recalc
python scripts/pangu.py sweep out/world.json --param "physics.constants[0].world_value" --from 3.2e-11 --to 4.8e-11 --steps 5
python scripts/pangu.py sweep out/world.json --param "physics.constants[0].world_value" --from 1e-11 --to 1e-10 --steps 9 --log
                                                                        # 跨数量级扫参数时用等比采样

# 8. 对比版本（改了什么、哪条被修好、哪些产物必须重跑）
python scripts/pangu.py diff out/world-v1.json out/world-v2.json

# 9. 第一人称切片体检（两百字验尸：字数 / 定稿 / 引用 / 现象 / 时序）
python scripts/pangu.py slice out/world.json
python scripts/pangu.py slice out/world.json --prompt                  # 四种视角的写作提示（自动带编年前情）
python scripts/pangu.py slice out/world.json --prompt --at-year 3000   # 把这个人钉在第 3000 年：只给那之前的史
python scripts/pangu.py slice out/world.json --prompt --persona skeptic # 敌对科学家版（用来验尸）

# 9.5 命名层（名字的骨由音系与地形给，字归作者）
python scripts/pangu.py naming out/world.json                          # 音系 + 10 人名 + 10 地名
python scripts/pangu.py naming out/world.json --kind place --count 20   # 只要地名，要 20 个
python scripts/pangu.py naming out/world.json --set-phonology "c=q,w,x;v=u,a"   # 换一套读音
python scripts/pangu.py naming out/world.json --write --yes            # 写回 civilization.names
python scripts/pangu.py naming out/world.json --check                  # hash 复算 + 引用失效 + 重名

# 10. 红队审查（让 AI 扮演敌对物理学家提问，未结案不许交付）
python scripts/pangu.py redteam out/world.json            # 生成质疑
python scripts/pangu.py redteam out/world.json --write    # 回写 world.json（按 id 幂等）
python scripts/pangu.py redteam out/world.json --check    # 体检靶点与结案率

# 11. 生态演化（把 biology.evolution 编译成元胞自动机）
python scripts/pangu.py ca out/world.json                 # 只编译：看规则、代价、强迫项
python scripts/pangu.py ca out/world.json --run           # 跑演化并出快照图
python scripts/pangu.py ca out/world.json --check         # 同 seed 复算，与 summary 逐项比对

# 12. 行星地图（从设定推演地形、海平面、气候、河网、群系）
python scripts/pangu.py map out/world.json                # 只推演：看海洋占比、山峰、均温、河流
python scripts/pangu.py map out/world.json --run          # 出七层图 + 正射地球 + map.html
python scripts/pangu.py map out/world.json --write --yes  # 把摘要与粗粒度场写回 world.json（喂 CA）
python scripts/pangu.py map out/world.json --check        # 同 seed 复算 + 六项地图体检

# 13. 一批小开关（排查 / 复用 / 兼容）
python scripts/pangu.py plan out/world.json --axe 3                 # 只看斧 3 的细账
python scripts/pangu.py options out/world.json --unanswered           # 只列还没答的命题
python scripts/pangu.py options out/world.json --md out/选项表.md     # 已采纳的卡导出成表
python scripts/pangu.py validate out/world.json --only P01,R01        # 只跑指定检查项
python scripts/pangu.py patch out/world.json --history -n 5           # 版本修订历史
python scripts/pangu.py slice out/world.json --cites                  # 引用清单是否真的存在
python scripts/pangu.py axioms --id P03                               # 点名一条积木
$env:PANGU_ASCII=1   # 或 export PANGU_ASCII=1：符号换 ASCII，给 GBK 控制台
```

**演化模型的铁律**：规则不能凭空写，每条必须带 `source` 指回 `world.json` 的某个字段，否则编译失败；summary 里的数字必须是真跑出来的，`ca --check` 会复算打假，1.1.1 起连最终格子的 `final_hash` 都要逐位对齐。

**地图的铁律**：海平面不是手填的，是水量与盆地容积解出来的；群系颜色和名字来自 `bodies[0].biomes[]`，不是引擎内置的地球群系。`map --write` 只写摘要和 72×36 的粗粒度场，**不写整张图**——图是派生文件，world.json 仍是单一数据源。

**调参层的铁律**：改设定走 `patch`，不要手改 JSON；`patch` 会顺手把 `meta.version` 补丁位 +1、往 `history.revisions[]` 写一条修订，并立刻报评分与 fatal 的增减。扫参数时，`mass_earth` 这类质量参数要配 `--recalc`，否则声明的密度/重力会先撞 P01，满屏 fatal 看不出真正的临界点。`diff` 给出的「需要重跑」清单是义务，不是建议。

**导航层的铁律**：每一轮先跑 `plan`，别凭记忆推进。斧位是「字段完备度」的判定——不服气就补字段，不要改判定。`plan` 报「本斧已收」只说明**能往下走**，不代表写得好；能不能交付看 `validate --strict` 与六项门槛。改动后若 `entail --check` 报失效，说明有旧天象还挂在 `sky_phenomena` 里，删掉或重跑回写，别让它继续冒充事实。

## 质量红线

- ❌ **倒因为果**：先想好"龙"，再补物理。顺序必须反过来
- ❌ **无代价奇观**：任何"这世界就是很厉害"而没有价格标签的设定
- ❌ **地球换皮**：只改了颜色和名字，法则一模一样。至少一条法则必须是新的
- ❌ **数据打架**：`world.json` 里质量、半径、重力、密度四者不自洽（`validate` 会算）
- ❌ **检索堆砌**：把搜索结果整段贴进设定
- ❌ **卡与世界两张皮**：`seed.brief` 里选了「无恒星」，`cosmology.stars` 里却还挂着三颗（`R01` 会抓，`options --check` 能看明细）
- ❌ **编出来的天象**：写 `sky_phenomena` 时凭感觉加一条，却答不出「由哪个字段推得」。答不出就说明它不该存在，或者该先改设定
- ✅ **每次改设定，`meta.version` +0.1，并在 `history.revisions[]` 留一条记录**（`patch` 会自动做）
- ✅ **反常识度控制在 40–70**：低于 40 是换皮，高于 70 读者会放弃（`validate` 会算）
- ✅ **交付前跑一遍 `plan`**：斧位到 7、`missing` 为空、六项门槛全过，才算「写完了」

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
| `references/公理库.md` | 62 条可复用反常识设定积木（物理/数学/化学/生物/宇宙/文明），含代价与痕迹 | 第 2–6 斧卡住时 |
| `references/选项卡.md` | 31 个命题 / 132 个选项的设定菜单，按七斧分段，每项带代价、痕迹、连锁字段与互斥标签 | 每一斧要选方向时（`options` 读取它） |
| `references/检索与灵感策略.md` | 检索配方、query 模板、取反技巧、结果改写规范 | 每斧的"搜"环节 |
| `references/自洽性审查协议.md` | 五维十六问、致命项清单、修补话术 | 第 7 斧 |
| `references/world-schema.md` | `world.json` 全字段规范与最小示例 | 写 JSON 前必读 |
| `scripts/pangu.py` | 主 CLI：plan / options / entail / sky / init / validate / preview / export / axioms / patch / sweep / diff / doctor / slice / redteam / ca / map / chronicle / naming | 每次操作 |
| `scripts/world_schema.py` | 结构校验、单位换算、天体物理计算、打分、反常识度、公理库解析、选项卡互斥与对账 | 被 import，勿单独运行 |
| `scripts/rite.py` | 七斧状态机：斧位判定、缺口、下一步命令、六项交付门槛 | `plan` 调用 |
| `scripts/options_lib.py` | 选项卡解析与检索：列 / 抽 / 采纳 / 未答命题 | `options` 调用 |
| `scripts/entailment.py` | 必然推论：36 条后果规则、幂等回写、失效检测 | `entail` 调用 |
| `scripts/sky.py` | 观测层：星表生成、天球坐标、天光与极限星等、昼长、星图（ASCII/PNG）、星空体检 | `sky` / `whatif --sky` / `export` 调用 |
| `scripts/chronicle.py` | 编年层：19 条事件规则、logistic 人口曲线反解时刻、hash 可复算、引用失效检测 | `chronicle` / `review` D12 / `export` 调用 |
| `scripts/naming.py` | 命名层：slug → 音系，地形 → 后缀语义，音系 + seed → 人名 / 地名；拆音节与双 hash 对账 | `naming` 调用 |
| `scripts/benchmark.py` | 地球基准：六条曲线对公开数据，出偏差表 | `benchmark` / `review` D9 调用 |
| `scripts/review.py` | 交付体检：十二项编排与判定（只读） | `review` 调用 |
| `scripts/whatif.py` | 反事实推演：副本改动、现象增减、分级与下游 | `whatif` 调用 |
| `scripts/world_tuning.py` | 调参层：点路径读写、参数扫描（含等比）、版本对比、斧位差、下游重跑推断 | `patch` / `sweep` / `diff` 调用 |
| `scripts/ca_engine.py` | 生态演化引擎：编译、跑、复算比对、快照出图、地图耦合 | `ca` 子命令调用 |
| `scripts/mapgen.py` | 行星地图引擎：板块、海平面、气候、河网、群系、出图与交互页 | `map` 子命令调用 |
| `scripts/png_writer.py` | 零依赖 PNG 编码器（zlib + struct） | 被 `ca_engine` import |
| `scripts/preview_template.html` | 3D 预览前端（Three.js，单文件自包含） | 被 `preview` 子命令读取 |
| `examples/helikon/` | 完整示例：「赫利孔」三阳世界（看不见星星的那一个） | 不确定标准时对照 |
| `examples/aster/` | 对照示例：「星夜」单星世界（满天星、银河可见） | 星图该长什么样时对照 |
| `AGENTS.md` | 通用 agent 指令文件（Codex/Amp/Jules 等直接读） | 宿主只认 `AGENTS.md` 时 |
| `install.py` | 一键把入口铺到各 harness | 首次安装 / 换宿主 |
| `adapters/mcp/pangu_mcp.py` | MCP stdio 服务器，把引擎暴露为 21 个 tool | 客户端只支持 MCP |
| `docs/开发文档-v1.1.3.md` | 导航与选项卡那一版的范围、数据契约、算法、验收与限制 | 维护引擎时 |
| `docs/开发文档-v1.1.6.md` | 编年层：推演链、19 条规则的依据、数据契约、判定口径与已知限制 | 维护编年层时 |
| `adapters/generic/BOOTSTRAP.md` | 纯对话版启动提示词（无文件系统也能用） | 宿主不能读文件 |
| `docs/跨harness移植说明.md` | 兼容矩阵、各宿主配置样例、排错 | 装载失败时 |

## 交付前的最后一句话

在给出成品前，问自己一句：**"如果我是一个住在这个世界里的物理学家，我会觉得哪条不对？"**

答不出来，才算造完了。
