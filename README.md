# 盘古 1.1.6 Pangu

<img src="assets/icon.svg" width="72" align="right" alt="pangu">

[![version](https://img.shields.io/badge/version-1.1.6-E8B15C)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-4C7FA6)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-3776AB)](https://www.python.org)
[![agent skill](https://img.shields.io/badge/agent%20skill-SKILL.md-8A7BD6)](SKILL.md)
[![tests](https://img.shields.io/badge/selftest-121%2F121-3FA96A)](scripts/selftest.py)

**开天辟地式造世引擎** — 先立律，后长物。

一个**与宿主无关**的 agent 技能：从一句话种子出发，设定世界的数学 / 物理 / 化学 / 生物底层法则，再严格推导出它的山、水、生物与文明，最后给出可交互的 3D 预览。

不绑定任何平台。Claude、GPT、Gemini、本地模型，Claude Code、Codex、Cursor、Windsurf、Cline、Zed，或者你自己写的 harness —— 只要能读文件，就能用它；只要支持 MCP，就能把它当工具调。

> 地球不是模板，是一个样本。

---

## 1.1.6 新增了什么

1.1.1 有**地**，1.1.2 能**改**，1.1.3 知道**走到哪**，1.1.4 **抬头能看见**，1.1.5 **知道自己错多少**，1.1.6 **知道这三千年里发生了什么**，也知道**东西该叫什么**。

前几版把律、地、天都算出来了，唯独「人」这一层只有散文：`civilization` 是一段自我介绍，`history.eras` 是三个手写的纪元标题。这一版补上时间轴，而且用同一种方式补 —— **不编故事，只做正向推导**：

> 承载力 → 人口曲线（logistic）→ 人口刻度 → 事件时刻 → 事件文案

- **`chronicle` — 编年史，从地上长出来**：19 条规则（H01–H23），每条触发条件都落在 `world.json` 的某个字段上。年长来自 `calendar.year_days`，人口上限来自 `carrying_capacity.humans_subsistence`，「定历」来自 `year_days ÷ month_days` 的余数，禁忌 / 能源 / 技术路径 / 社会形状直接引用 `civilization.*` 的原文，国教锚定 `sky_phenomena` 里最显眼的那一条，余波由气候适配与种子决定。
- **可复算**：`--check` 按 seed 重推再对 hash。手改一句史书，hash 立刻对不上；改了下游字段却没重跑 `--write`，`--check` 与 `review` 的 **D12** 会点名。
- **每条都带出处**：事件带 `src`（引用哪几个字段）、`strength`（必然 / 很可能）与 `q`（在文明跨度上的相对时刻）。**没有出处的史不许存在** —— 这条规矩跟 `ca` 的 `source`、`entail` 的 `src` 是同一条。
- **时间轴回放**：`--from-year` / `--to-year` 截一段看，`--seed` 换一种抖动，`--md` 出表 + 逐条正文，`export` 自动把它挂在「九 · 历史」底下。
- **切片接上时间轴**：`slice --prompt` 自动带上「这个人之前发生过的 3 件事」（年份 / 强度 / 纪元 / 全境人口），`--at-year 3000` 可以把这个人钉在第 3000 年 —— 之后的事他一无所知。存档里没有编年史就明说没有，不替作者编。
- **`naming` — 名字的骨由引擎给，字归作者**：音系从 `meta.id` 的字母长出来（`helikon` → `h l k n` × `e i o`），不足 8 辅音 / 4 元音就补默认集，补了什么写进 `borrowed`；地名后缀由 `land_fraction` 判沿海 / 内陆。每批 10 个人名 + 10 个地名，每个都能拆音节、指回字段；`--check` 算两份 hash（重推一份、存档名字一份），手改一个字母就红。`--set-phonology` 让作者直接换一套读音。
- **地图从主产物里开出去**：`preview` 的 dock 上有一个「地图」按钮，点开同目录的 `map.html`（新窗口）—— 那边是 1440×720 的原生渲染，比把 180×90 的场塞进预览页再放大清楚得多。预览页因此回到 246 KB。`map.html` 这一版补上**每层图例**：色带直接由渲染用的 ramp 生成，标尺取自渲染用的同一份 ranges（高程 0–5.6 km、温度 247–304 K、降水 0–P95），切层即换；群系层给色块，板块层给边界与热点。
- **赫利孔算下来**：18 条事件、跨度 21,116 年。第 367 年一年正好 8 个月、历法不需要闰日（算术给的，不是祭司的功劳）；第 2,938 年种子入土，此时 4 万人，而理论口粮上限是 629 亿人；第 18,362 年走到顶点，只有理论上限的 4.6%。**那个 4.6% 是引擎给的，不是史书给的。**
- 数字：`review` 十一项 → **十二项**（D12 编年），`selftest` 105 → **121**（V13–V21 编年与地图入口、V22–V23 切片接编年、V24–V27 命名层，与 M1b）。

```bash
python scripts/pangu.py chronicle examples/helikon/world.json          # 从承载力推出整条文明史
python scripts/pangu.py chronicle examples/helikon/world.json --md -   # 出表 + 逐条正文
python scripts/pangu.py chronicle out/world.json --write --yes         # 回写 history.chronicle
python scripts/pangu.py chronicle out/world.json --check               # hash 复算 / 引用失效
```

**没有做的**：文明层仍然只有一层薄壳。编年史推**事件顺序与时刻**，不推政体、经济与战争的具体过程，也不写人名与国名 —— 名字是作者的活，年份与因果是引擎的活。

## 1.1.5 新增了什么

1.1.1 有**地**，1.1.2 能**改**，1.1.3 知道**走到哪**，1.1.4 **抬头能看见**，1.1.5 **知道自己错多少**。

这一版把 `docs/1.1.5-更新方案.md` 里画到 2.0 的十一个版本一次并了进来。要说清的是：**并进来的是内核与账本，不是一台全耦合的地球系统模式**。八个物理内核各自对解析解或公开数，四本守恒账带容差，每个派生量带 ±，每条关键结论标明来源。

- **`kernel` — 八个内核，一条命令**：PDE（热传导/平流/浅水）、Budyko–Sellers 能量平衡与冰-反照率、灰体辐射与水汽反馈、固体地球边界层标度、辛积分轨道与潮汐、碳-硅酸盐恒温器、Hubbell 中性群落与物种-面积、量纲硬域。任何一项不过就退出码 1。
- **`ledger` — 四本账**：能量（吸收 vs 出射长波）、水（库存 vs 面积×海深）、碳（`4πR²P/g` 与 CO₂ 储库）、元素（三本分账合计为 1）。能量 ±1%、水 ±5%、碳 ±10%。**建账第一天就抓到赫利孔一处矛盾**：它声明温室 33 K，但 10% CO₂、118 kPa 的大气按辐射解该有 51.5 K，均温差 18.6 K。账本只摆出来——按 1.1.4 的口径「声明优先、只报不改」，这条不平由作者定夺，不扣分。
- **`uq` — 每个数带 ±**：中心差分把输入区间推到输出。地球平衡温度 **254.3 ± 4.6 K**，主要来自反照率 ±0.05。这是**敏感度**不是置信区间，一阶线性、按独立处理。
- **`certify` — 适用域声明**：关键结论分四类——**算出来的 / 半算半填 / 经验式 / 作者拍的**，给覆盖率。「半算半填」专指算一半填一半：地表温度 = 平衡温度（算）+ 声明温室（拍）。赫利孔 16 条结论，算出来 8、半算半填 1、经验式 3、声明 4，覆盖率 **50%**。
- **`replay` — 可复算**：从存档 seed 重放 map 与 ca，对 hash 逐位核；`--seed` 覆盖时按「换 seed 就该不同」判定。
- **`benchmark` 6 → 25 条**：B07 板块速度从「未建模、只报不算」升级成真的标度律（1.72 cm/yr），新增曲线覆盖辐射、PDE、固体地球、能量平衡、轨道、碳循环、生态与守恒储库。**曲线只增不减。**
- **量纲进写盘路径**：`patch --set "…surface_temperature_k=1e9"` 直接拒绝（退出码 2），`--force-unit` 才放行。`validate` 加 C01–C03（新维度「定量」），`review` 九项 → 十一项（D10 守恒、D11 适用域）。
- **预览页多一个「账本」页签**：覆盖率环形图、误差表（值 ± 与相对条）、四本守恒账（残差条 + 容差竖线）、八个内核格子（点开看完整自检）、可复算三列 hash、量纲硬域与定量体检、地球/火星两个靶的偏差表。纯 DOM，不动 3D；3D 挂了降级页上也有入口。`preview --fast` 约 0.3 秒，`--replay` 才真重放。
- 数字：`selftest` 93 → **105**，`benchmark` 6 → **25**，`validate` 39 → 44，`review` 9 → 11。

```bash
python scripts/pangu.py kernel                                # 八个内核一轮自检
python scripts/pangu.py ledger examples/helikon/world.json    # 四本账，残差带容差
python scripts/pangu.py certify examples/helikon/world.json   # 哪些是算的、哪些是拍的
python scripts/pangu.py replay examples/helikon/world.json    # 从 seed 重放，对 hash
```

**没有做的**：三维环流、云、板块时间演化、生物地球化学、文明层、全耦合时间步。这些是方案里 1.3/1.5/1.7/1.9/1.10 的内容，1.1.5 只立了它们的**最小可验证内核**与对表口径。对外仍然不能说「精确模拟行星」。

## 1.1.4 新增了什么

1.1.1 有**地**，1.1.2 能**改**，1.1.3 知道**走到哪**，1.1.4 **抬头能看见**。

这一版不加新物理，只把已经写在 `world.json` 里的东西算出来：观测点、自转与倾角、大气、恒星、卫星——它们本来就是「抬头」的全部输入，只是此前没人算。

- **`sky` — 今夜星图**（`scripts/sky.py`）：五段输出（今夜 / 全天星图 / 关键天体 / 一年 / 判断）。天光是**经验模型**：空气辉光 21.9 mag/arcsec² 打底，叠暮光、叠明亮点光源散射、叠气压带来的尘埃散射，误差 ±0.5 等，输出全程标「简化模型」。`--at "日落后 2h"` 支持相对时刻，`--year` 出一年昼长与极昼极夜，`--allnight` 一夜六帧，`--md` 出星图 PNG + 逐月表，`--json` 给 agent。
- **星表是程序生成的**：按 `(seed, count, color_mix, galaxy)` 确定性生成，`--check` 可复算（S01/S02/S03）。**不接** HYG / Gaia——「这是本世界的星表，不是地球的」是设定的一部分。
- **`whatif --sky`**：反事实推演的第五层「抬头」。改倾角 → 昼长与极昼极夜怎么变；改气压 → 天光多亮、还能看见几颗星。
- **档案第一屏换成「第一眼」**：星图 + 一句话今夜，参数表全部后移。预览页也多了一张「今夜星图」卡片（Canvas 2D，带时刻滑块，不动 3D 视图）。
- **两个世界，两张天**：`examples/helikon/` 三颗恒星 → 夜空被压到 19 等、只剩两百来颗、银河被洗掉；`examples/aster/` 一颗 G2V → 一夜两千六百多颗、银河横过天顶。前者不是 bug，是结论。
- 数字：`entail` 30 → 36（E31–E36 全是夜空阈值），`validate` 37 → 39（SK01/SK02），`selftest` 63 → 93，MCP 17 → 20。

### 增补：对着真实世界的那一半（同日第二批）

上面的星图是「好看」。这一批是「对得上」——起因是一个很直接的问题：把地球丢进去，它算得对吗？

- **`benchmark earth`**：地球参数喂进引擎，六条曲线对公开数据，出目标 / 实测 / 结论。第一天就抓出两处真错：极区蒸发被 `temp<268` 一刀切归零（极地下不了雨）、副热带下沉支没建模（25° 比赤道还湿）。修完纬向降水 **r = 0.40 → 0.82**，纬向温度 **RMSE 6.7 K**，昼长对独立数值积分 **RMSE 0.02 h**。这张表现在是 `review` 的 **D9**。
- **`capacity`**：Miami 模型（`NPP = min(f(T), f(P))`）把气候场积成陆地 NPP，再按可采收比例与人均热量折算人口上限。星夜（地球参数）算出 **56.5 Gt C/yr、约 55.8 亿人**——量级对得上。第一次能回答「这颗星球养得活多少人」。
- **`map --season`**：用已经算好的倾角跑冬至/夏至两套气候，出四张图（北半球夏季降水 1457 mm / 冬季 391 mm，ITCZ 会跟着赤纬动）。
- **温室由成分估**：`33 + 4.28·ln(CO₂e/560)`，CO₂ 翻倍 **+2.97 K**（AR6 最佳估计 3.0）。声明值仍然优先，所以旧世界零影响；赫利孔的 10% CO₂ 会被点名「按成分该是 55 K，你写了 33 K」——只报不改。
- **恒星寿命与宜居带**：`t ≈ 10 Gyr × M/L`，附 Kasting 保守宜居带。
- 数字：`selftest` 78 → 93，`review` 八项 → 九项，MCP 18 → 20。

```bash
python scripts/pangu.py sky examples/helikon/world.json            # 今夜看见什么
python scripts/pangu.py sky examples/aster/world.json --year       # 一年昼长
python scripts/pangu.py whatif examples/helikon/world.json --set "cosmology.bodies[0].axial_tilt_deg=80" --sky
```

## 1.1.3 新增了什么（上一版）

1.1.1 让世界有了**地**，1.1.2 让**改动**可验证，1.1.3 让**流程可导航、想象力可供给**。

世界不是一次写完的，也不是靠灵感堆出来的。这一版做了三件事：

- **`plan` — 七斧状态机**（`scripts/rite.py`）：读 `world.json` 判定当前在第几斧，列出这一斧**还缺哪些字段**、该回答的 2–3 个问题、该做的检索，以及**按顺序的下一步命令**；另报六项交付门槛（自洽 / 反常识度 / 切片 / 红队 / 地图 / 选项卡一致）。斧位由字段完备度判定，不看自述；斧 6 可选，不写文明填 `exists:false` 就跳过。`--brief` 一行结论、`--next` 一条命令、`--json` 机读——给 agent 的循环用，别让报告吃掉上下文。
- **`options` — 选项卡**（`references/选项卡.md`，31 个命题 / 132 个选项）：每一斧有 4–5 个**必须回答的命题**，每个命题 2–5 个**互斥选项**，每个选项五格——设定 / 代价 / 痕迹 / 连锁（要顺手写的字段）/ 标签。`--adopt "Q3.1=B"` 采纳进 `seed.brief.choices`（保留代价与痕迹），自动升版本记修订；标签里 `-` 前缀表示排除（`-有恒星` 撞上别人的 `有恒星`），有冲突直接拒绝，`--force` 才放行。**选项不是命令**：可以一个都不选，也可以自己写第六个。
- **`entail` — 必然推论**（`scripts/entailment.py`，30 条规则）：从已立之律机械推出居民**必然**会看见什么——双影、不落的灯、恒黑之天、固定的晨昏线、碎云、没有翅膀、会沸腾的湖、没有冰的颜色、可走的潮间带、不是水的雨、会呼吸的地面、两面的叶子、不用闰的年……每条给断言 / 出处字段 / 可观测痕迹 / 强度（`必然` = 可由数值直接算出，`很可能` = 生态与社会的合理外推）。`--write --yes` 按 `〔entail E01〕` 幂等回写天象，`--check` 检出「改了设定却忘删旧天象」的失效条目。

三者咬成一条循环：**`plan` 告诉你该回答哪一问，`options` 给这一问几种活法，`entail` 把你选完的结果推成居民看得见的东西。**

十三条小改动（第一批）：

- `validate --brief`（一行式结论）｜`plan --next`（只吐一条命令）｜`axioms --axe N`（按斧位查积木）｜`sweep --log`（等比采样，跨数量级扫参数必开）｜`patch --suggest`（给出应填的 ρ / g / R，只建议不写盘）
- `doctor` 版本一致性（内核 / SKILL / README / CHANGELOG / MCP 五处对齐）｜`diff` 斧位对比（推进了几斧、门槛过了几个）｜`export` 新增「零 · 创作路线」｜`slice --prompt`（居民 / 孩童 / 外来者 / 敌对科学家四种视角）
- `R01` 选项卡一致性（卡间互斥 + 卡与世界对账，进机检与评分）｜`options --check`｜MCP 12 → 15 个 tool｜selftest 34 → 52 项

### 第一批之后：`review` 与 `whatif`

前面三个命令负责**把世界造出来**，这两个负责**判断能不能交**、以及**如果当初选另一条会怎样**。

- **`review` — 交付体检**（`scripts/review.py`）：一条命令跑完十二项 —— 自洽 / 反常识度 / 切片 / 红队 / 地图复算 / 演化复算 / 推论失效 / 选项卡一致 / 地球基准 / 守恒账本 / 适用域 / 编年史，最后给一个 **「可交付 / 不可交付」** 的单一判断。未过的硬门槛按修复顺序排好，每条附一句为什么和一条可直接跑的命令。**只读**，可以反复跑；`--fast` 秒级（跳过地图与演化复算），`--strict` 退出码 1 进 CI。
- **`whatif` — 反事实推演**（`scripts/whatif.py`）：在内存副本上改设定，回答「世界会变成什么样」——重力怎么动、哪条必然推论消失、审查从哪一条开始崩、若采纳要重跑什么。`--set` 定点改，`--scale` 按倍率缩放并**保留单位后缀**（`4.004e-11 m3kg-1s-2` → `2.8028e-11 m3kg-1s-2`），`--recalc` 先抹平 P01 这类算术冲突。**永不写原世界**，`--write` 才另存一份假设世界。
- 例：G × 0.7 后地表重力 1.76 → 1.23 g，E09「没有翅膀」自动消失（能飞了），恰好演示了「反常识是有代价的，代价一变，奇观就散」。
- 与 `sweep` 的分工：`sweep` 扫**一个数**、只回答「哪一步崩了」；`whatif` 任意多字段、回答「**世界变成什么样**」。

十条小开关：`plan --axe N`｜`options --unanswered` / `--md`（导出卡表）｜`validate --only`｜`patch --history`（修订历史）｜`entail --list` / `--exclude`｜`slice --cites`｜`axioms --id`｜`PANGU_ASCII=1`（符号换 ASCII，给 GBK 控制台）；MCP 15 → 17 个 tool，selftest 52 → 63 项。

详见 [CHANGELOG.md](CHANGELOG.md) 与 [docs/开发文档-v1.1.3.md](docs/开发文档-v1.1.3.md)。

---

## 1.1.2 新增了什么

1.1.1 让世界有了**地**，1.1.2 让改动本身**可验证**。世界不是一次写完的，是在「改一个数 → 看它崩不崩 → 对比上一版」里长出来的。

- **`patch` — 定点改 / 增 / 查**（`scripts/world_tuning.py`）：按点路径读写任意字段，替代手改 JSON。写盘即把 `meta.version` 补丁位 +1、往 `history.revisions[]` 追一条修订，并立刻报评分 / fatal 的增减。默认拒绝写不存在的字段（防手滑写出孤儿字段），`--create` 才放行；`--dry-run` 只看不写。
- **`sweep` — 参数敏感度扫描**：沿一个数值参数扫出连续谱，每步完整校验，标出安全窗与**第一个崩点**。`--recalc` 会在每步重算天体的密度 / 重力 / 半径，让扫描探索物理自洽的邻近世界——否则质量一动就先撞 P01 的四数自洽，满屏 fatal 看不出真正的临界点。
- **`diff` — 版本对比**：逐字段列出改动 / 新增 / 删除，给出评分、致命项、表面重力、温度、反常识度的变化，并推断必须重跑的下游产物（export / preview / map / ca / slice / redteam）。改设定不再是黑箱。
- **公理库按代价类型二次索引**：创作时想的往往不是「哪个学科」，而是「我想让世界付出什么代价」。`axioms --cost 空间` 直接捞「远行变得不可能」这类积木。
- **反常识度指数**：`validate` 新增 0–100 的偏离度（常数改写 / 新相互作用 / 定律偏离 / 守恒破缺 / 另类生化 / 虚构元素 / 时空尺度 / 天体构型），推荐区间 40–70。低于 40 提示「仍是地球换皮」，高于 70 提示「读者会放弃」。示例赫利孔为 66。
- **生物视角（可操控第一人称）**：预览页新增「生物」页签。选一个物种寄宿进去，用它的眼高、步速与表面重力在 72×36 粗场放大的地表行走：WASD / 方向键移动，Shift 疾走，空格跳跃，拖动转头，F 切第一/第三人称，R 重生。生物是低多边形方块模型（Minecraft / 罪恶都市那一档），走动时四肢摆动、尾巴摇摆；HUD 实时显示基座、主元素、体成分与新元素。
- **元素配比与生命基座**：`chemistry.composition` 声明行星 / 大气 / 海洋的元素含量（三项各自归一），`biology.biochemistry` 声明碳基 / 硅基 / 碳硅杂合、主元素、结构元素、溶剂与代价，`biochemistry.composition` 与每个物种的 `composition` 给体成分，`biology.organisms[]` 给可操控物种的体高、步速、感官与配色。
- **世界独有的新元素**：`chemistry.fictional_elements[]`，命名文法固定为 `⿸气⿰钅X` —— 半包围的「气」包住「钅」与一个自选单字。字形用 Unicode 表意描述序列无损传递，预览页把它画成一枚拼合字；每个元素还要交代相态、丰度、生态作用、代价与痕迹。`validate` 新增 K01–K03 三项机检，示例赫利孔造了「气钅辰 / 气钅昷 / 气钅参」三个。
- **校验 33 → 36 项、selftest 22 → 34 项、MCP 9 → 12 个 tool**（新增 `pangu_patch`、`pangu_sweep`、`pangu_diff`）。

详见 [CHANGELOG.md](CHANGELOG.md)。

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
| Zed / Continue / Cherry Studio | `adapters/mcp/pangu_mcp.py` | MCP tool，15 个 |
| 任意纯对话模型 | `adapters/generic/BOOTSTRAP.md` | 粘贴即用 |

细节见 `adapters/README.md`，排错见 `docs/跨harness移植说明.md`。

---

## 三十秒上手

```bash
python scripts/pangu.py doctor                     # 环境自检 + 版本一致性

python scripts/pangu.py init --name "赫利孔" \
    --seed "三倍地球大，天上有两个太阳" --out out/helikon.json

# 1.1.3：导航 + 选项 + 推论（每一轮都从这三条开始）
python scripts/pangu.py plan     out/helikon.json            # 在第几斧 / 缺什么 / 下一步命令
python scripts/pangu.py plan     out/helikon.json --brief    # 一行结论（循环里用）
python scripts/pangu.py options  --axe 3 --roll 2            # 抽 2 张选项卡（带代价与痕迹）
python scripts/pangu.py options  out/helikon.json --adopt "Q3.1=B"   # 采纳 → seed.brief
python scripts/pangu.py options  out/helikon.json --check    # 卡间互斥 / 卡与世界对账
python scripts/pangu.py entail   out/helikon.json            # 从已立之律推出必然现象
python scripts/pangu.py entail   out/helikon.json --write --yes   # 幂等回写 sky_phenomena
python scripts/pangu.py entail   out/helikon.json --check    # 改设定后哪些旧推论失效了
python scripts/pangu.py review   out/helikon.json            # 十一项体检：能不能交
python scripts/pangu.py whatif   out/helikon.json --scale "physics.constants[0].world_value=0.7" --recalc
                                                             # 反事实：重力再低 30% 会怎样
python scripts/pangu.py sky      out/helikon.json             # 抬头：今夜的天光 / 极限星等 / 星图
python scripts/pangu.py sky      out/helikon.json --year       # 一年昼长与极昼极夜
python scripts/pangu.py sky      out/helikon.json --md out/今夜.md   # 星图 PNG + 逐月表
python scripts/pangu.py benchmark earth                       # 25 条曲线对地球，出偏差表
python scripts/pangu.py capacity out/helikon.json             # 这颗星球养得活多少人
python scripts/pangu.py map      out/helikon.json --season --run   # 冬至/夏至双图

# 1.1.5：守恒、误差与可复算
python scripts/pangu.py kernel   --json                       # 八个内核一轮自检
python scripts/pangu.py ledger   out/helikon.json             # 四本账：能量/水/碳/元素
python scripts/pangu.py certify  out/helikon.json --md out/误差表.md   # 算的 / 拍的 / 覆盖率
python scripts/pangu.py replay   out/helikon.json             # 从 seed 重放 map 与 ca
python scripts/pangu.py preview  out/helikon.json             # 3D 预览 + 「账本」页（1.1.5）
python scripts/pangu.py preview  out/helikon.json --fast      # 账本只在，跳过内核/基准（0.3 s）
python scripts/pangu.py preview  out/helikon.json --replay    # 真重放核对 hash（约两分钟）

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

# 1.1.2：改设定 / 扫参数 / 比版本
python scripts/pangu.py patch    out/helikon.json --set "cosmology.bodies[0].albedo=0.35"
python scripts/pangu.py patch    out/helikon.json --get "physics.constants[0].world_value"
python scripts/pangu.py sweep    out/helikon.json --param "cosmology.bodies[0].mass_earth" --percent 30 --recalc
python scripts/pangu.py diff     out/world-v1.json out/world-v2.json
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
| 流程不可导航 | 每轮都要重读方法论，才知道自己在第几步、下一步干什么 | **`plan`**：斧位 + 缺口 + 该问的问题 + 下一步命令 + 六项门槛 |
| 灵感断供 | 想得出来的都是「双星 + 超级地球」，改猛了像噪声 | **`options`**（132 个带代价的选项）+ **`entail`**（30 条从设定推现象的规则） |
| 交付靠自觉 | 六条体检命令，漏一条就是漏一条，没人说「能交」 | **`review`**：九项一命令、一个判断、修复按顺序排好 |
| 不敢改 | 改坏了要整轮重来，所以宁可不动 | **`whatif`**：先在副本上推演后果，代价 / 现象 / 崩点一次看清 |

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

推进方式从 1.1.3 起是固定的：**每轮先 `plan` 看斧位与缺口**，缺想法就用 `options --axe N` 抽张卡（带着代价与痕迹），落地走 `patch`，复检用 `validate --brief`；七斧收齐后用 `entail` 把设定推成现象，再交给 `map` / `ca` / `slice` / `redteam`，最后 `review` 一把过、`preview` / `export` 出成品。中途想试另一条路，用 `whatif` 先在副本上推演，不写原世界。

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
│   └── mcp/pangu_mcp.py        MCP stdio 服务器（零依赖，21 个 tool）
├── docs/
│   ├── 开发文档-v1.0.md         1.0 架构、算法、接口、验收矩阵、路线图
│   ├── 开发文档-v1.1.md         1.1 范围、四项功能定义、验收门槛
│   ├── 开发文档-v1.1.1.md       1.1.1 行星地图与 CA 强化：数据契约、算法、验收
│   ├── 开发文档-v1.1.2.md       1.1.2 调参层：patch / sweep / diff 的契约与判定
│   ├── 开发文档-v1.1.3.md       1.1.3 导航与选项：plan / options / entail 的契约与判定
│   ├── 开发文档-v1.1.4.md       1.1.4 观测层与增补层：sky / benchmark / capacity 的口径
│   ├── 开发文档-v1.1.5.md       1.1.5 守恒与误差：八个内核、四本账、± 与适用域
│   ├── 开发文档-v1.1.6.md       1.1.6 编年层：推演链、19 条规则、数据契约与判定
│   ├── 1.1.4-更新方案.md        1.1.4 的立稿与落地复盘（§15 差距清单、§16 增补）
│   ├── 1.1.5-更新方案.md        通往真实世界模型的十一个大版本路线图（1.1.5 全量并入）
│   ├── 跨harness移植说明.md     各宿主加载机制、配置样例、排错
│   ├── 3D预览层规范.md          渲染层技术规格
│   └── 优化建议.md              已知短板与改进方向
├── references/
│   ├── 七斧创世法.md            每斧的提问脚本 / 推导链 / 常见错误
│   ├── 公理库.md                62 条反常识积木（含代价与痕迹）
│   ├── 选项卡.md                31 个命题 / 132 个选项的设定菜单（按七斧分段）
│   ├── 检索与灵感策略.md        四类检索配方与取反技巧
│   ├── 自洽性审查协议.md        五维十六问
│   └── world-schema.md          JSON 全字段规范 + 机检清单
├── scripts/
│   ├── pangu.py                 CLI：plan / options / entail / review / whatif / init / validate / preview / export
│   │                                / axioms / doctor / slice / redteam / ca / map / patch / sweep / diff
│   ├── world_schema.py          校验内核：天体物理计算、评分、反常识度、元素与基座检验、卡间互斥与对账
│   ├── rite.py                  七斧状态机：斧位判定、缺口、下一步命令、六项交付门槛
│   ├── options_lib.py           选项卡解析与检索：列 / 抽 / 采纳 / 未答命题
│   ├── entailment.py            必然推论：36 条后果规则、幂等回写、失效检测
│   ├── chronicle.py             编年层：19 条事件规则、logistic 反解时刻、hash 可复算
│   ├── naming.py                命名层：slug→音系、地形→后缀语义，音系+seed→人名/地名（双 hash 对账）
│   ├── review.py                交付体检：十二项编排与判定（只读）
│   ├── whatif.py                反事实推演：副本改动、现象增减、分级与下游
│   ├── world_tuning.py          调参层：点路径读写、参数扫描（含等比）、版本对比、斧位差、下游重跑推断
│   ├── ca_engine.py             生态演化引擎：编译、跑、复算比对、地图耦合
│   ├── mapgen.py                行星地图引擎：板块、海平面、气候、河网、群系、出图
│   ├── png_writer.py            零依赖 PNG 编码器（zlib + struct）
│   ├── preview_template.html    单文件预览模板（3D + 地面视角 + 演化视图 + 可操控生物视角）
│   ├── pde.py                   1.2 连续介质内核：热传导 / 平流 / 浅水（对解析解）
│   ├── atmos.py                 1.3 能量平衡 + 冰-反照率：全球均温、极地放大、雪球分岔
│   ├── radiation.py             1.4 灰体两流 + 水汽反馈：温室、CO₂ 敏感性
│   ├── geo.py                   1.5 固体地球标度：瑞利数、板块速度、地幔热流
│   ├── orbit.py                 1.6 轨道：辛积分、近日点进动、潮汐去旋
│   ├── chem.py                  1.7 碳-硅酸盐恒温器：CO₂ ODE、暗淡年轻太阳
│   ├── life.py                  1.8 生命动力学：中性群落、物种-面积、营养级
│   ├── units.py                 1.1.5 量纲与取值域：硬域拒绝、软域提示
│   ├── conservation.py          1.1.5 守恒账本：能量 / 水 / 碳 / 元素
│   ├── uq.py                    1.1.5 误差传播：输入区间 → 输出 ±
│   ├── certify.py               1.1.5 适用域声明：算的 / 半算半填 / 经验 / 拍的
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

1.1.3 起，示例也演示了新的三件工具：`seed.brief` 记录了采纳的 7 张选项卡（含每张的代价与痕迹）；`entail` 从已定设定推了 7 条必然现象进 `sky_phenomena`（带 `〔entail E01〕` 标记，可幂等复算、可检出失效）；`plan` 报「七斧已收齐、门槛 6/6」。其中「一年正好 8 个双星周期、历法不需要闰日」就是 E30 算出来的——**不是设定者的巧思，是开普勒第三定律的结算**。

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
