# 盘古 · 造世引擎（通用 agent 指令）

> 本文件是给「只认 `AGENTS.md` 的 harness」用的入口（Codex、Amp、Jules、以及大部分 IDE agent）。
> 它**不是**技能正文，只是指针 + 作业约定。正文在 `SKILL.md`。

## 这是什么

一套把「架空世界」当工程项目来做的工具：先立宇宙底层法则（数学/物理/化学/生物），再严格推导出星体、地形、气候、生态与文明，最后输出结构化数据、自洽性审查报告、行星地图和可交互 3D 预览。

1.1.3 起多了三件东西：**路标**（`plan`：现在第几斧、缺什么、下一步跑什么）、**菜单**（`options`：31 个命题 / 132 个选项，每项带代价与痕迹）、**推导**（`entail`：从已立之律推出居民必然看见的现象）。

1.1.4 起多了第四件：**抬头**（`sky`：把 world.json 里已写好的观测点、倾角、大气、恒星、卫星算成一张今夜星图、一张一年昼长表）。

1.1.5 起多了第五件：**账本**（`kernel` / `ledger` / `certify` / `replay`）。前四件解决「像不像、自不自洽」，这一件解决「错多少、哪些数根本不是算的」：八个物理内核各自对解析解或公开数，四本守恒账带容差，每个派生量带 ±，每条关键结论标明是算出来的、半算半填、经验式还是作者拍的。星表按 seed 确定性生成、可复算，**不是真实星表**；天光是经验模型（±0.5 等）；天球位置是圆轨道近似。`whatif --sky` 让「改一个数，今夜星空会怎样」当场可见；世界档案与预览页的第一屏是星图。

1.1.6 起多了第六件：**编年**（`chronicle`）。前五件把律、地、天、账都算出来了，「人」这一层却只有散文。编年层不编故事，只做正向推导：承载力 → 人口曲线（logistic）→ 人口刻度 → 事件时刻 → 事件文案。19 条规则（H01–H23），时刻由人口曲线**反解**，所以改一次 `carrying_capacity` 整条时间轴都会动。每条事件带 `src` 出处、`strength`（必然 / 很可能）与 `q`（相对时刻），同 seed 可复算 hash；`--check` 指出引用失效、人口越界与手改痕迹，`review` 多出 **D12 编年**。**不写人名与国名**——名字是作者的活，年份与因果是引擎的活。

## 何时触发

用户提出下列任一意图时，**先读 `SKILL.md` 全文**，再动手：

- 造一个世界 / 宇宙 / 星球，设计其物理法则
- "如果重力反过来会怎样""没有太阳怎么活""双恒星世界""三倍地球大"
- 给小说 / 游戏 / 剧本做底层宇宙设定
- 审查一个已有设定是否自洽
- 生成可旋转的 3D 星球预览
- "我现在造到第几步了""下一步该干什么""给我一些设定选项"
- "这个设定必然会导致什么现象"

## 怎么用

```bash
python scripts/pangu.py doctor                     # 环境自检 + 版本一致性，先跑这个

# —— 每一轮都从这里开始（别凭记忆推进）——
python scripts/pangu.py plan out/world.json        # 第几斧 / 缺什么 / 该问什么 / 下一步命令 / 六项门槛
python scripts/pangu.py plan out/world.json --brief   # 一行结论（循环里用）
python scripts/pangu.py plan out/world.json --next    # 只吐下一条命令
python scripts/pangu.py options --axe 3 --roll 2      # 抽 2 张选项卡（带代价、痕迹、连锁字段）
python scripts/pangu.py options out/world.json --adopt "Q3.1=B"   # 采纳（写 seed.brief，自动升版本）
python scripts/pangu.py options out/world.json --check            # 卡间互斥 / 卡与世界对账
python scripts/pangu.py entail out/world.json          # 从已立之律推出必然现象
python scripts/pangu.py entail out/world.json --write --yes       # 幂等回写 sky_phenomena
python scripts/pangu.py entail out/world.json --check             # 改设定后哪些旧推论失效了
python scripts/pangu.py entail --list                             # 36 条规则的触发条件与强度

# —— 编年（1.1.6）——
python scripts/pangu.py chronicle out/world.json       # 从承载力推出整条文明史
python scripts/pangu.py chronicle out/world.json --list        # 19 条规则：触发条件与强度
python scripts/pangu.py chronicle out/world.json --write --yes # 回写 history.chronicle
python scripts/pangu.py chronicle out/world.json --check       # hash 复算 / 引用失效 / 人口越界
python scripts/pangu.py chronicle out/world.json --from-year 8000 --to-year 14000  # 时间轴回放

# —— 抬头（1.1.4）——
python scripts/pangu.py sky out/world.json             # 今夜：天光 / 极限星等 / 星图 / 关键天体
python scripts/pangu.py sky out/world.json --year      # 一年昼长与极昼极夜
python scripts/pangu.py sky out/world.json --check     # S01 星表可复算 / S02 摘要一致 / S03 文本对账
python scripts/pangu.py sky out/world.json --md out/今夜.md   # 星图 PNG + 逐月表
python scripts/pangu.py whatif out/world.json --set "cosmology.bodies[0].axial_tilt_deg=80" --sky

# —— 对表与承载（1.1.4 增补）——
python scripts/pangu.py benchmark earth                # 25 条曲线对地球，出偏差表（review D9 同源）
python scripts/pangu.py capacity out/world.json        # NPP → 人口上限
python scripts/pangu.py capacity out/world.json --write --yes   # 回写 biology.carrying_capacity
python scripts/pangu.py map out/world.json --season --run       # 冬至/夏至双图

# —— 守恒与误差（1.1.5）——
python scripts/pangu.py kernel                         # 八个物理内核一轮自检（1.2–1.8）
python scripts/pangu.py kernel --only pde,geo --json    # 只跑指定内核
python scripts/pangu.py ledger out/world.json          # 四本账：能量/水/碳/元素 + 残差与容差
python scripts/pangu.py ledger out/world.json --write --yes   # 回写 conservation.ledger
python scripts/pangu.py certify out/world.json         # 算的 / 半算半填 / 经验式 / 拍的 + 覆盖率
python scripts/pangu.py certify out/world.json --md out/误差表.md
python scripts/pangu.py replay out/world.json          # 从 seed 重放 map 与 ca，对存档 hash
python scripts/pangu.py patch out/world.json --set "cosmology.bodies[0].radius_km=1e9"
                                                       # ↑ 1.1.5 起会被量纲硬域直接拒绝（--force-unit 放行）

# —— 收尾与试错 ——
python scripts/pangu.py review out/world.json          # 九项体检：能不能交（只读）
python scripts/pangu.py review out/world.json --fast   # 跳过地图/演化复算，秒级
python scripts/pangu.py review out/world.json --strict # 硬门槛未过即退出码 1
python scripts/pangu.py whatif out/world.json --scale "physics.constants[0].world_value=0.7" --recalc
python scripts/pangu.py whatif out/world.json --set "cosmology.bodies[0].albedo=0.6" --json

# —— 主干 ——
python scripts/pangu.py init --name "世界名" --seed "一句话种子" --out out/world.json
python scripts/pangu.py validate out/world.json --brief           # 一行式复检
python scripts/pangu.py validate out/world.json --fix-hint
python scripts/pangu.py preview out/world.json -o out/preview.html
python scripts/pangu.py export out/world.json --md out/世界档案.md
python scripts/pangu.py axioms --domain physics --roll 3
python scripts/pangu.py axioms --axe 3 --roll 3                   # 按斧位查积木
python scripts/pangu.py axioms --cost 空间 --roll 3               # 按代价类型查积木
python scripts/pangu.py patch out/world.json --set "physics.constants[0].world_value=3.6e-11"
python scripts/pangu.py patch out/world.json --get "cosmology.bodies[0].mass_earth"
python scripts/pangu.py patch out/world.json --set "..." --suggest   # 顺带给出密度/重力建议值
python scripts/pangu.py sweep out/world.json --param "cosmology.bodies[0].mass_earth" --percent 30 --recalc
python scripts/pangu.py sweep out/world.json --param "physics.constants[0].world_value" --from 1e-11 --to 1e-10 --log
python scripts/pangu.py diff out/old.json out/new.json            # 改了什么 + 斧位推进 + 要重跑什么
python scripts/pangu.py slice out/world.json                      # 第一人称切片体检
python scripts/pangu.py slice out/world.json --prompt             # 四种视角的写作提示
python scripts/pangu.py slice out/world.json --cites              # 切片引用的字段是否真的存在
python scripts/pangu.py redteam out/world.json --check
python scripts/pangu.py map out/world.json --run --write --yes    # 行星地图：板块/海平面/气候/河网/群系
python scripts/pangu.py ca out/world.json --check                 # 生态演化：同 seed 复算比对
```

- 只依赖 Python 标准库（≥3.9），无需 `pip install`
- Windows 上若 `python` 不可用，换成真实解释器路径
- 所有命令在**技能根目录**执行最稳妥

## 硬性作业约定

1. **渐进披露**：先读 `SKILL.md`；`references/` 下的文件按正文点名再读，不要一次性全量加载（会浪费上下文）。
2. **单一数据源**：`world.json` 是唯一真相。`preview.html` 与 `世界档案.md` 都是生成物，**禁止手改**。
3. **产物位置**：写到用户指定目录；没指定就写当前工作目录下的 `out/<id>/`，不要污染技能目录。
4. **先立律后长物**：物理层没定稿前，不许讨论生物与文明（这叫倒因为果，审查器会判 fatal）。
5. **有致命项不许交付**：`validate --strict` 非零退出时，必须先修或明确告知用户"这个世界有一处会崩"。
6. **改设定走 `patch`**：它会自动升 `meta.version`、记 `history.revisions[]`、立刻复检；改完用 `diff` 确认本次改动和必须重跑的下游产物。
7. **每轮先 `plan`**：斧位是字段完备度的判定，不是自述。`plan` 说在第 3 斧就是第 3 斧。
8. **选项卡是决策，不是数据**：`options --adopt` 只记选择，不会改 `world.json` 的物理字段；落差由 `R01` 提醒，改数据是下一步的事。

## 三律（灵魂）

- **逆行律**：至少一个底层维度与地球直觉明确相反
- **代价律**：每条反常识都要付出可量化的代价
- **痕迹律**：代价必须在居民抬头能看见的地方留下痕迹

没有代价的奇观是意淫，有代价的奇观才是世界。

## 生物与元素（1.1.2）

- **可操控视角**从 `biology.organisms[]` 读：`playable: true` 的物种必须有 `height_m` 与 `locomotion.speed_ms`；`preview` 的「生物」页签用它的眼高、步速、重力在 `planet_map.coarse` 上行走。
- **生命基座**写在 `biology.biochemistry`：`base`（碳基 / 硅基 / 碳硅杂合 / 其他）、`primary_element`、`structural_element`、`solvent`、`limits`；体成分写在 `composition`，合计必须为 1。
- **元素配比**写在 `chemistry.composition.planet / atmosphere / ocean`，按质量或体积分数，合计必须为 1。
- **新元素**写在 `chemistry.fictional_elements[]`，字形必须是 `⿸气⿰钅X`（半包围的「气」+「钅」+ 一个自选单字，如 `⿸气⿰钅辰`），并给出相态、丰度、生态作用与代价。`validate` 的 K01–K03 会检查这些。

## 选项卡与推论（1.1.3）

- **命题**共 31 个，编号 `Q<斧>.<序>`（Q1.1 … Q7.4），分七斧写在 `references/选项卡.md`。每斧 4–5 个命题，每个命题 2–5 个互斥选项。
- **选项五格**：设定 / 代价 / 痕迹 / 连锁（要顺手写的字段）/ 标签。缺「代价」的卡会被 `R01` 点名。
- **互斥**：标签以 `-` 开头表示排除（`-有恒星` 撞上别人的 `有恒星`）；`--adopt` 会拒绝，`--force` 才放行。
- **采纳记录**写进 `seed.brief.choices[]`（保留代价与痕迹），并升版本、记修订。
- **必然推论** 36 条（`E01`–`E36`），每条给出断言 / 出处字段 / 可观测痕迹 / 强度（`必然` 或 `很可能`）。回写以 `〔entail E01〕` 标记，幂等去重；`entail --check` 报告失效条目。
- **夜空六条**（1.1.4）：`E31` 没有真正的黑夜（≥2 星且总光度 ≥1 L☉）/ `E32` 没有星的世界 / `E33` 大得吓人的月亮（轨道 <20 R⊕）/ `E34` 看得见的星移（自转 <12 h）/ `E35` 整夜的星与整日的黑（倾角 >45°）/ `E36` 压扁的星（气压 >200 kPa）。

## 交付体检与反事实推演（1.1.3 第二批）

- **`review`** 一条命令跑九项：D1 自洽 / D2 反常识度 / D3 切片 / D4 红队 / D5 地图复算 / D6 演化复算 / D7 推论失效 / D8 选项卡一致 / D9 地球基准，最后给一个「能不能交」。**只读**，可反复跑。硬失败即不可交付，`--strict` 退出码 1。
- **`whatif`** 在内存副本上改设定（`--set` 定点改、`--scale` 倍率缩放且保留单位后缀），输出四层：代价（重力/温度/反常识度）、审查（评分 + 先崩的那一条）、现象（少了/多了/仍成立）、下游（若采纳要重跑什么）。`--recalc` 先抹平 P01 这类算术冲突。**永不写原世界**，`--write` 才另存一份假设世界。
- 与 `sweep` 的分工：`sweep` 扫一个数、只答「哪一步崩了」；`whatif` 任意多字段、答「世界变成什么样」。
- 一批小开关：`plan --axe N`、`options --unanswered` / `--md`、`validate --only`、`patch --history`、`entail --list` / `--exclude`、`slice --cites`、`axioms --id`、`PANGU_ASCII=1`（符号换 ASCII，GBK 控制台用）。

## 观测层（1.1.4）

- **画面优先**：`export` 的第一屏是「第一眼 · 星图 + 今夜一行」，参数表后移；`preview` 侧栏有一张「今夜星图」卡片（Canvas 2D，带时刻滑块，不动 3D 视图）。
- **数据契约**（全部可选，旧世界零影响）：`cosmology.starfield`（`seed` / `count` / `magnitude_dist` / `color_mix` / `galaxy{present,inclination_deg,width_deg,brightness}` / `constellations` / `hash`）与 `cosmology.sky`（`summary` / `checks` / `figures`）。两者由 `sky --write --yes` 生成，**不要手填**。`bodies[].orbit.phase_deg` 为 1.1.4 新增可选字段，缺省按 0。
- **`sky --check`**：S01 星表 hash 可复算 / S02 摘要与实算一致 / S03 天象文本与星图不打架。`validate` 里对应 `SK01`/`SK02`（缺省 skip，旧世界不掉分）。
- **只报不改**：`sky` 发现「文本说它是一颗小点，实算却是 −16 等」时只给软提示。改光度还是改写法，是作者的设定决策，不是引擎的。
- **两个示例**：`examples/helikon/`（三星，看不见银河）与 `examples/aster/`（单星，满天星）。前者不是 bug，是结论。

## 基准与承载力（1.1.4 增补）

- **`benchmark earth`**：地球参数喂进引擎，六条曲线对公开数据，出「目标 / 实测 / 结论」。这是唯一能证明「引擎是模型不是美术」的东西，`review` 的 **D9** 与它同源。改动 `mapgen` 的任何一个场之后**必须重跑**，它是回归网。
- **`capacity`**：Miami 模型 `NPP = min(f(T), f(P))` → 陆地 Gt C/yr → 可采收比例 → 人口上限。回写 `biology.carrying_capacity`（含 `assumptions`，不要把假设删掉）。
- **季节**：`map --season` 跑赤纬 ±倾角两套，出 4 张图；振幅按经验折半（海温滞后未建模）。
- **温室**：`atmosphere.greenhouse_delta_k` 是**声明值，优先**；没写才由成分估（`33 + 4.28·ln(CO₂e/560)`）。声明与估算差 >15 K 时档案里会点名，这是提示不是错误。
- **洋流**：`planet_map.climate.ocean_heat_transport` 0–1，默认 0；开了就把纬向梯度压平最多 35%。
- 已建模 / 未建模要分清楚：温度、降水、昼长、NPP、温室、恒星寿命**有模型**；板块速度、洋流环流、季节海温、文明层**没有**。对外不许说「精确模拟行星」。

## 守恒与误差（1.1.5）

- **`kernel`**：一条命令跑完八个物理内核（PDE 热传导/平流/浅水、Budyko–Sellers、灰体辐射、固体地球标度律、辛积分轨道、碳-硅酸盐、中性群落、量纲）。每项都有解析解或公开数对表，不过就是退出码 1。**改任何内核之后先跑它。**
- **`ledger`**：四本账，残差按相对值判（能量 ±1%、水 ±5%、碳 ±10%、元素 1e-6）。`skip` 表示缺字段，不算分也不假装；`info` 是储库（只报不判）。账不平最常见的原因是「声明温室与大气成分打架」——那是作者的设定决策，账本只负责摆出来。
- **`certify`**：把关键结论分四类——**算出来的 / 半算半填 / 经验式 / 作者拍的**，给覆盖率。半算半填专指「算一半、填一半」（如 地表温度 = 平衡温度 + 声明温室）。覆盖率 < 30% 的世界，别拿它的数字当模型结论。
- **`uq`**：派生量带 ±，来自假定输入区间（反照率 ±0.05、光度 ±1%、半径/质量 ±1%、CO₂ ±20%）。这是**敏感度**不是置信区间，一阶线性、按独立处理。
- **`replay`**：同 seed 逐位一致才算可复算；`--seed` 覆盖后按「应该不同」判定。可复算是「可证伪」的前提。
- **`patch` 量纲硬域**：`1e9` 写进温度字段会被拒（退出码 2）。`--force-unit` 是明知故犯的出口，不是常规操作。
- **两个新维度**：`validate` 的 C01–C03（守恒/量纲/适用域），`review` 的 D10/D11。都是软门槛——账不平会红，但不拦交付。
- **预览页的「账本」页签**：`preview` 生成的 HTML 里，1.1.5 的每一样都有画面（覆盖率环、误差条、守恒残差条、内核格子、hash 三列、基准偏差）。默认 6 秒；`--fast` 只算账本与适用域（0.3 秒），`--replay` 才真重放（约两分钟）。给用户看「错多少」时用它，不要只贴命令行输出。

## 更多

- 七斧流程与提问脚本：`references/七斧创世法.md`
- 设定菜单：`references/选项卡.md`
- 62 条反常识积木：`references/公理库.md`
- 检索配方：`references/检索与灵感策略.md`
- 五维十六问审查：`references/自洽性审查协议.md`
- 数据结构：`references/world-schema.md`
- 完整示例：`examples/helikon/`
- 本版开发文档：`docs/开发文档-v1.1.3.md`
