# world.json 字段规范（单一数据源）

一份 `world.json` 同时喂给 `pangu.py validate`（校验/打分）、`pangu.py preview`（3D 页）、`pangu.py export`（世界档案）。**改设定只改这个文件**，再重跑脚本。

## 目录

1. 设计原则
2. 顶层结构
3. 逐段字段表（含 `seed.brief` / `cosmology.energy_source` / 推论标记）
4. 单位与换算约定
5. 3D 预览专用字段
6. 最小可用示例
7. 校验规则清单（37 项，含 R01）
8. 改设定
9. 五个配套命令（plan / options / entail / review / whatif）

---

## 1. 设计原则

- **律先于物**：`physics` 必须能解释 `cosmology`，`cosmology` 必须能解释 `biology`。JSON 的字段顺序即推导顺序
- **四数自洽**：`radius_km`、`mass_earth`、`density_gcc`、`gravity_g` 四者互相约束，任填三个，第四个必须能算出来（误差 ±3%）
- **数值优先于形容词**：不写"重力很大"，写 `gravity_g: 1.79`
- **每个反常识都要有 `cost` / `consequence` 字段**，没有就说明是空想

---

## 2. 顶层结构

```jsonc
{
  "meta":         { },  // 身份：名字/版本/一句话/美学
  "seed":         { },  // 种子：原始意图、核心悖论、检索依据
  "cosmology":    { },  // 宇宙：恒星、天体、天空现象、历法
  "physics":      { },  // 物理：常数、定律、破缺、新相互作用
  "mathematics":  { },  // 数学：几何、数系、认知局限
  "chemistry":    { },  // 化学：元素、溶剂、键、材料
  "biology":      { },  // 生物：能量货币、光合、遗传、营养级
  "civilization": { },  // 文明：技术路径、计时、能源、社会（可 null）
  "history":      { },  // 历史：纪元、修订记录
  "consistency":  { },  // 审查：评分、逐条裁决
  "narrative":    { }   // 叙事：三秒印象、名场面、钩子
}
```

除 `meta` / `seed` / `cosmology` / `physics` 外，其余段可为 `null`（表示"该斧未开"）。`validate` 会提示缺失但不报致命。

---

## 3. 逐段字段表

### 3.1 `meta`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | str | ✅ | 小写 slug，用于文件名，如 `helikon` |
| `name` | str | ✅ | 世界中文名 |
| `subtitle` | str | | 副标题，如「三阳世界」 |
| `version` | str | ✅ | 语义化，初始 `1.0`，每次改写 +0.1 |
| `created` | str | ✅ | `YYYY-MM-DD` |
| `author` | str | | `盘古 / 用户名` 或 `自主生成` |
| `tagline` | str | | 十字以内的一句话气质 |
| `aesthetic` | str[] | | 3–5 个色/质形容词，驱动 3D 配色与文档文风 |
| `tags` | str[] | | 检索用标签 |
| `autonomy` | str | | `auto` \| `co-create` \| `audit`，记录本次共创模式 |

### 3.2 `seed`

| 字段 | 类型 | 说明 |
|---|---|---|
| `prompt` | str | 用户原话，尽量保真 |
| `core_paradox` | str | **一句话悖论**：这世界最不可能的地方 |
| `resolution` | str | **一句话解释**：凭什么它可能（对应代价律） |
| `references` | obj[] | `{title, url, takeaway, use}`，至少 4 条，至少 1 条属"证伪"类 |
| `forbidden` | str[] | 用户明确不要的元素，推导时避开 |
| `brief` | obj | **1.1.3 可选**：创作简报，见 §3.2.1 |

#### 3.2.1 `seed.brief`（1.1.3，可选）

记录「采纳了哪些选项卡」。它是**决策层**，不改任何物理字段；缺省不影响评分（`R01` 记 skip）。

```jsonc
{
  "updated": "2026-11-02",
  "choices": [
    {
      "qid": "Q2.1",              // 命题号，Q<斧>.<序>
      "axe": 2,                    // 属于第几斧
      "title": "天上有什么？",
      "option": "B",               // 选项字母
      "label": "内层双星互绕，行星绕两者公转",   // 设定原文
      "cost": "行星轨道必须 ≥2.5 倍双星间距……",  // 代价（必须非空）
      "trace": "两道颜色不同的影子……",           // 痕迹
      "tags": ["有恒星", "双星"],   // `-` 前缀表示排除，用于互斥判定
      "fields": ["cosmology.stars[0..1].orbit"],  // 要顺手写的字段
      "date": "2026-11-02"
    }
  ]
}
```

- 同一 `qid` 只保留一条；`options --adopt` 后写覆盖先写，并按 `Qn.m` 排序。
- `card_conflicts` 查卡间互斥；`card_world_mismatch` 查卡与数据的一致性（`有恒星` / `锁定` / `光合` / `水溶剂` / `碳基` 五个标签可机检，其余只当备注）。

### 3.3 `cosmology`

| 字段 | 类型 | 说明 |
|---|---|---|
| `frame` | str | 框架标签，自由文本，如 `circumbinary-superearth`、`shell-world`、`no-star-tidal` |
| `topology` | str | 空间拓扑描述（欧氏/闭合/分层/非欧） |
| `has_stars` | bool | 有无恒星。无恒星世界仍需给出替代能源 |
| `energy_source` | str | **1.1.3 建议**：无恒星世界的替代能源（如 `潮汐摩擦 + 放射性衰变`）。`has_stars=false` 时斧 2 会检查它；`entail` 的 E03/E27 读它 |
| `stars` | obj[] | 见下 |
| `bodies` | obj[] | 见下。**第 0 个视为主角天体** |
| `sky_phenomena` | str[] | 居民抬头能看见的异常（痕迹律的落点），3–6 条。`entail --write` 追加的条目以 `〔entail Exx〕` 结尾 |
| `calendar` | obj | `{day_hours, year_days, months, month_days, epoch}`；**1.1.4 可选** `month_names: str[]`（`sky --year` 用它给月份起名，缺省「第 N 月」） |
| `starfield` | obj | **1.1.4 可选**：星表参数，见 §3.3.3。缺省也能跑，标「默认星表（未登记）」 |
| `sky` | obj | **1.1.4 可选**：星空摘要 `{summary{limit_mag,visible_stars,sky_brightness,milky_way,moment,note}, checks[], figures[]}`，由 `sky --write --yes` 生成，**不要手填** |

**星体 `stars[]`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `name` | str | `A` / `长明` |
| `class` | str | 光谱型，可自创，如 `G2V`、`K7V`、`X0-dark` |
| `mass_solar` `radius_solar` `luminosity_solar` | num | 以太阳为单位 |
| `temp_k` | num | 表面温度 |
| `color` | str | `#RRGGBB`，供 3D 与文档配色 |
| `orbit` | obj | `{parent, a_au, period_days, eccentricity}`；`parent` 可为质心标签或另一星 id |
| `note` | str | 一句话特征 |

**天体 `bodies[]`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` / `name` | str | ✅ | |
| `kind` | str | ✅ | `planet` `moon` `ring` `station` `shell` `anomaly` |
| `radius_km` | num | ✅ | 真实半径 |
| `radius_earth` | num | | 冗余字段，`validate` 会核对 |
| `mass_earth` | num | ✅ | 以地球质量为单位 |
| `density_gcc` | num | | g/cm³ |
| `gravity_g` | num | | 表面重力，以地球 g 为单位 |
| `rotation_hours` | num | | 自转周期；潮汐锁定填 `null` 并在 `note` 说明 |
| `axial_tilt_deg` | num | | 转轴倾角，决定季节 |
| `albedo` | num | | 反照率 0–1 |
| `orbit` | obj | ✅ | 同上结构，`a_au` 相对 `parent` |
| `atmosphere` | obj\|null | | `{surface_pressure_kpa, composition{}, color, height_km, greenhouse_delta_k}`。**1.1.4**：`greenhouse_delta_k` 不写时由 `composition` 估算（`33 + 4.28·ln(CO₂e/560)`，气压按 `(P/101.325)^0.15` 放大）；写了就以声明值为准 |
| `biomes` | obj[] | | `{id, name, color, elevation}`，`elevation` 0–1 升序，供 3D 着色器插值 |
| `rings` | obj\|null | | `{inner_r, outer_r, color, opacity}`，半径单位为**行星半径倍数** |
| `visual_radius` | num | | 3D 显示半径（夸张值，非真实比例），缺省按 `radius_earth` 映射 |
| `note` | str | | 一句话特征 |

### 3.3.3 `cosmology.starfield`（1.1.4，可选）

星表是**程序生成**的，不是真实星表。给它参数就能复算，给它 hash 才能体检。

```json
"starfield": {
  "seed": 7,
  "count": 12000,
  "magnitude_dist": "power-law",
  "color_mix": {"K": 0.2, "G": 0.5, "F": 0.2, "M": 0.1},
  "galaxy": {"present": true, "inclination_deg": 32, "width_deg": 18, "brightness": 0.6},
  "constellations": [{"name": "长明之弧", "stars": [[0.0, 12.0], [0.4, 14.0]]}],
  "hash": "a1b2c3d4"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `seed` | int | 决定整片天的随机种子；缺省取 `seed` 顶层里的整数值，再缺省 0 |
| `count` | int | 星数，50–200000；缺省 2000 |
| `magnitude_dist` | str | 目前只实现 `power-law`（星数按 10^(0.45 m) 增长，m ∈ −1.5…6.5） |
| `color_mix` | obj | 光谱型占比 `O/B/A/F/G/K/M`，合计不必为 1（内部归一） |
| `galaxy.present` | bool | 是否撒银河带（再多星系没有意义：银河是银道面密集暗星的叠加） |
| `galaxy.inclination_deg` | num | 银道面相对赤道的倾角 |
| `galaxy.width_deg` | num | 银带半宽（高斯 σ 的两倍） |
| `galaxy.brightness` | num | 0–1；≥0.3 且天光 ≤21 mag/arcsec² 才算「可见」 |
| `constellations` | obj[] | 手写星座连线，`stars: [[ra_deg, dec_deg], …]`。引擎**不自动生成**星座神话 |
| `hash` | str | 参数指纹前 8 位，`sky --write --yes` 生成；`sky --check` 用它复算比对（S01） |

`bodies[].orbit.phase_deg` 也是 1.1.4 新增的可选字段（卫星相位，缺省 0）。

### 3.3.1 `bodies[].planet_map`（1.1.1，可选）

行星地图的输入与派生摘要。作者只写 `tectonics/hydrosphere/climate`；`summary/checks/hash/figures/coarse` 由 `pangu.py map --write --yes` 生成，不要手填。

| 字段 | 类型 | 说明 |
|---|---|---|
| `seed` | int | 地图随机种子 |
| `tidal_locked` | bool | 强制潮汐锁定（`rotation_hours: null` 也会判锁定） |
| `tectonics.plates` | int | 板块数，缺省 6 + 2.2×R⊕，夹在 6–16 |
| `tectonics.hotspots` | int | 热点数，缺省 2 + R⊕，夹在 2–7 |
| `tectonics.relief_km` | num | 总起伏上限，缺省 8.8/g^0.8 |
| `hydrosphere.solvent` | str | 溶剂名（水、氨、甲烷……） |
| `hydrosphere.mean_depth_km` | num | 平均海深目标，缺省 0.30×2×relief |
| `hydrosphere.inventory_km3` | num | 水体积，缺省 area×0.50×mean_depth |
| `climate.mean_precip_mm` | num | 年降水目标，缺省由气压推 |
| `climate.temp_optimum_k` / `temp_tolerance_k` | num | 宜居度温度窗 |
| `climate.ocean_heat_transport` | num | **1.1.4**：0–1，洋流热输运强度。开了就把纬向温度梯度压平最多 35%（默认 0，与旧行为一致） |
| `summary` | obj | 派生：海洋/陆地占比、最高峰、最深海、均温、年降水、河流格、湖泊、冰、宜居度、构造统计 |
| `checks` | obj[] | 六项地图体检（M01–M06） |
| `hash` | str | 八位字段哈希，同 seed 可复算 |
| `sea_level_km` / `inventory_km3` / `relief_total_km` | num | 解出的海平面与水量、总起伏 |
| `figures` | str[] | 相对 `world.json` 的图路径（`map/*.png`） |
| `coarse` | obj | 72×36 的 `habitat/temperature/elevation` base36 + `ocean` 01 串；喂 CA |

### 3.3.2 `biology.evolution.map_coupling`（1.1.1，可选）

| 字段 | 类型 | 说明 |
|---|---|---|
| `field` | str | `habitat` / `temperature` / `elevation` |
| `initial_from_map` | bool | 初始分布按地图偏置 |
| `initial_bias` | num | 0–1，越大越偏向宜居处 |
| `growth_gain` | num | 生长概率随地图缩放的指数 |
| `rules` | str[] | 只耦合这些规则；缺省耦合所有产生产者/消费者的规则 |

`grid.area_weighted: true` 时密度按 cos(lat) 加权（仅 `lon-closed` 有意义）。

### 3.4 `physics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `constants` | obj[] | `{symbol, earth_value, world_value, delta, why}`；`delta` 为相对地球的比值或说明 |
| `laws` | obj[] | `{name, statement, deviation, consequence}`；`deviation` 写"标准/改写/废除" |
| `broken_symmetries` | str[] | 被放大的对称性破缺 |
| `new_interactions` | obj[] | `{name, range, effect, cost}`，至少 1 条用于支撑核心悖论 |
| `conservation_notes` | str | 守恒律保留/泄漏情况 |

### 3.5 `mathematics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `geometry` | str | 欧氏 / 球面 / 双曲 / 分形 |
| `number_system` | str | 居民实际使用的数系 |
| `peculiarity` | str | 数学上的异常 |
| `consequence` | str | 导致的技术天花板 |

### 3.6 `chemistry`

| 字段 | 类型 | 说明 |
|---|---|---|
| `periodic_status` | str | 元素表是否与地球一致 |
| `solvent` | obj | `{name, note}`，生命溶剂 |
| `key_bonds` | str | 主导键合方式 |
| `signature_materials` | obj[] | `{name, formula, property, use}`，3–5 条 |
| `abiotic_notes` | str | 非生物成因的特殊物质 |

### 3.7 `biology`

| 字段 | 类型 | 说明 |
|---|---|---|
| `energy_currency` | obj | `{name, note}`，能量货币（地球是 ATP） |
| `carrying_capacity` | obj | **1.1.4**：`capacity --write` 生成，含 `land_npp_gtc_yr` / `harvest_fraction` / `humans_subsistence` / `assumptions`。不要手填，也不要把 `assumptions` 删掉 |
| `metabolism_summary` | str | 一句话代谢路线 |
| `photosynthesis` | obj\|null | `{pigment, absorbs[], appearance}` |
| `genetic_carrier` | obj | `{name, note}` |
| `trophic_levels` | obj[] | `{name, share, examples[]}`，`share` 之和 ≈ 1 |
| `sentient` | obj | `{exists, name, note}` |
| `mass_extinctions` | str[] | 大灭绝记录，给历史纵深 |

### 3.8 `civilization`（可 `null`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `exists` | bool | |
| `name` | str | 文明统称 |
| `tech_path` | str | 技术树的另类路径 |
| `timekeeping` | str | **必须引用 `calendar`**，说清他们怎么知道过了一年 |
| `energy_source` | str | |
| `social_shape` | str | |
| `taboo` | str | 因物理约束形成的社会禁忌（代价律的社会投影） |

### 3.9 `history`

| 字段 | 类型 | 说明 |
|---|---|---|
| `eras` | obj[] | `{name, span, summary}` |
| `revisions` | obj[] | `{version, date, change, fields?}`，改设定必记；`fields` 是 1.1.2 新增的可选字段（本次改了哪些路径，最多 40 条）。用 `patch` 改设定会自动追加，不必手写 |

### 3.10 `consistency`

| 字段 | 类型 | 说明 |
|---|---|---|
| `score` | num | 0–100，由 `validate` 计算 |
| `checks` | obj[] | `{id, dim, question, verdict, note}`，`dim` ∈ `structure|energy|observation|evolution|narrative|quantitative`，`verdict` ∈ `pass|warn|fatal|skip` |
| `open_issues` | str[] | 未解决的遗留问题，交付时必须为空或经用户确认 |

### 3.11 `narrative`

| 字段 | 类型 | 说明 |
|---|---|---|
| `three_seconds` | str | 三秒讲完的印象 |
| `setpiece` | str | 最想拍成电影的一幕 |
| `hook` | str | 一句话钩子 |

### 3.12 `conservation`（1.1.5，可选）

由 `pangu ledger <world> --write --yes` 生成，**不要手填**。

| 字段 | 类型 | 说明 |
|---|---|---|
| `ledger` | obj[] | `{id, book, name, inflow, outflow, residual, unit, tol, ok, status, note}`，`status` ∈ `ok|warn|info|skip` |
| `ok` | bool | 所有**可算**账是否配平（`info` 储库不计） |
| `scored` / `skipped` | int | 参与判定的账数 / 缺字段的账数 |
| `generator` | str | `conservation/<version>` |

`residual` 是相对值；`info` 表示「储库，只报不判」；`skip` 表示缺字段，不算分也不假装。

### 3.13 `certification`（1.1.5，可选）

由 `pangu certify <world> --write --yes` 生成，**不要手填**。

| 字段 | 类型 | 说明 |
|---|---|---|
| `coverage` | num | 算出来的 / 关键结论，0–1 |
| `total` / `computed` / `mixed` / `empirical` / `declared` | int | 四类计数（`mixed` = 半算半填） |
| `claims` | obj[] | `{path, name, kind, value, pm, note}`，`kind` ∈ `computed|mixed|empirical|declared` |
| `not_modeled` | str[] | 这个引擎**明确没有**建模的部分 |
| `generator` | str | `certify/<version>` |

`mixed` 专指算一半填一半（如 地表温度 = 平衡温度 + 声明温室）。**不要**把 `mixed` 当 `computed` 引用。

---

## 4. 单位与换算约定

| 量 | 单位 | 参考值 |
|---|---|---|
| 距离（天体） | AU | 地球 1 AU |
| 半径 | km | 地球 6371 km |
| 质量 | 地球质量 | 5.972e24 kg |
| 重力 | 地球 g | 9.807 m/s² |
| 时间 | 小时 / 天 | 地球日 24 h |
| 温度 | K | 太阳表面 5772 K |
| 气压 | kPa | 地球海平面 101.325 kPa |

**四数关系**（`validate` 用此核对）：

```
density_gcc = mass_earth * 5.514 / (radius_earth ** 3)
gravity_g   = mass_earth / (radius_earth ** 2) * (G_world / G_earth)
```

若 `physics.constants` 中给了 `G` 的改值，重力计算自动带入该比值——这是"三倍地球大小仍能站人"的关键杠杆。

**双星稳定判据**（`validate` 检查）：环双星行星轨道半长轴须 ≥ 2.5 × 双星间距，否则判 `warn`；< 2.0 判 `fatal`。

**洛希极限**：`d_roche ≈ 2.44 * R_primary * (ρ_primary/ρ_secondary)^(1/3)`，卫星轨道小于它判 `fatal`。

---

## 5. 3D 预览专用字段

预览层只读四处，其余字段一律忽略（因此可以先写宇宙、后写生物，视图片刻可用）：

1. `meta.name` / `subtitle` / `tagline` / `aesthetic`
2. `cosmology.stars[]`（位置、颜色、相对大小）
3. `cosmology.bodies[]`（`radius_km`、`visual_radius`、`biomes[]`、`atmosphere`、`rings`、`rotation_hours`、`orbit`）
4. `biology.photosynthesis.appearance`（驱动晨昏色调，可选）

**尺度压缩规则**：真实半径与轨道相差 5 个数量级，无法同屏。预览层采用双尺度——
- 轨道半径：`a_au * ORBIT_SCALE`
- 天体半径：`visual_radius`（缺省 `1.2 + 1.6*log10(radius_earth+1)`）

因此 3D 图**不表示真实比例**，只表示拓扑与运动关系。这一点必须在页面 HUD 上注明。

---

## 6. 最小可用示例

```jsonc
{
  "meta": {"id":"demo","name":"示例界","version":"1.0","created":"2026-10-27",
           "tagline":"一天有两次日落","aesthetic":["铁锈","青金","灰白"]},
  "seed": {"prompt":"随便造个","core_paradox":"双日之下仍有黑夜","resolution":"双星互食周期造出长夜",
           "references":[{"title":"Kepler-16b","url":"","takeaway":"环双星行星存在","use":"结构合法性依据"}]},
  "cosmology": {
    "frame":"circumbinary","topology":"三维欧氏 + 层级双星","has_stars":true,
    "stars":[
      {"id":"A","name":"长明","class":"G2V","mass_solar":1.0,"radius_solar":1.0,
       "luminosity_solar":1.0,"temp_k":5780,"color":"#FFF6E2",
       "orbit":{"parent":"AB","a_au":0.30,"period_days":44.2,"eccentricity":0.02}},
      {"id":"B","name":"短烛","class":"K4V","mass_solar":0.72,"radius_solar":0.74,
       "luminosity_solar":0.21,"temp_k":4400,"color":"#FFC98A",
       "orbit":{"parent":"AB","a_au":0.30,"period_days":44.2,"eccentricity":0.02}}
    ],
    "bodies":[
      {"id":"demo-p","name":"示例界","kind":"planet","radius_km":19113,"radius_earth":3.0,
       "mass_earth":26.4,"density_gcc":5.51,"gravity_g":1.79,"rotation_hours":31.4,
       "axial_tilt_deg":18.2,"albedo":0.31,
       "orbit":{"parent":"AB","a_au":1.20,"eccentricity":0.03,"inclination_deg":2.1,"period_days":357.4},
       "atmosphere":{"surface_pressure_kpa":118,"composition":{"N2":0.68,"O2":0.19,"CO2":0.09},
                     "color":"#7FB6D9","height_km":180},
       "biomes":[{"id":"ash","name":"灰烬平原","color":"#8C7B63","elevation":0.0},
                 {"id":"rust","name":"锈林","color":"#A0522D","elevation":0.42},
                 {"id":"ice","name":"极冠","color":"#DCE6F0","elevation":0.78}],
       "rings":null,"visual_radius":3.0,"note":"三倍地球半径"}
    ],
    "sky_phenomena":["双影","双星互食长夜"],
    "calendar":{"day_hours":31.4,"year_days":357.4,"months":8,"month_days":44.7,"epoch":"落火元年"}
  },
  "physics":{"constants":[{"symbol":"G","earth_value":"6.674e-11","world_value":"4.004e-11",
            "delta":"0.60","why":"降低表面重力以支撑三倍半径的固体行星"}],
            "laws":[],"broken_symmetries":[],"new_interactions":[],"conservation_notes":""},
  "biology":null,"civilization":null,"history":{"eras":[],"revisions":[]},
  "consistency":{"score":0,"checks":[],"open_issues":[]},
  "narrative":{"three_seconds":"","setpiece":"","hook":""}
}
```

---

## 7. 校验规则清单

`pangu.py validate` 执行以下机检项（见 `scripts/world_schema.py`）：

| ID | 维度 | 规则 | 级别 |
|---|---|---|---|
| S01 | 结构 | `meta.id/name/version/created` 齐全且格式合法 | fatal |
| S02 | 结构 | `cosmology.bodies` 非空，每个 body 有 `id/name/kind/radius_km/mass_earth` | fatal |
| S03 | 结构 | `biomes` 若存在则 `elevation` 升序且在 0–1 | warn |
| S04 | 结构 | `stars[].orbit.a_au` 与 `period_days` 满足开普勒第三定律（±15%） | warn |
| P01 | 结构 | 四数自洽：密度、重力可由半径/质量/G 推出（±3%） | fatal |
| P02 | 结构 | `gravity_g` 在 0.05–4.0 之外 | warn |
| P03 | 结构 | 双星稳定：行星 `a_au` ≥ 2.5 × 双星间距 | warn / fatal |
| P04 | 结构 | 卫星轨道 ≥ 洛希极限 | fatal |
| E01 | 能量 | 行星接收辐照量 `L_total/(4πa²)` 推算平衡温度在 150–400 K | warn |
| E02 | 能量 | `biology.trophic_levels[].share` 之和在 0.9–1.1 | warn |
| E03 | 能量 | `atmosphere.surface_pressure_kpa` 在 20–500 之外 | warn |
| O01 | 观测 | `calendar.year_days` 与行星 `orbit.period_days` 一致（±5%） | warn |
| O02 | 观测 | `calendar.day_hours` 与 `rotation_hours` 一致（±10%，潮汐锁定除外） | warn |
| N01 | 叙事 | `narrative` 三项非空 | warn |
| N02 | 叙事 | `seed.references` ≥ 4 条 | warn |
| M10 | 观测 | 有 `planet_map.summary` 时：占比/温度/峰值范围合法、`hash` 存在、`coarse` 长度对 | warn |
| M11 | 观测 | 地图是否喂给 CA（`coarse` 场存在） | skip |
| R01 | 叙事 | **1.1.3**：已采纳的卡之间无互斥、卡与世界数据一致、每张卡都写了代价 | warn（无卡时 skip） |
| SK01 | 观测 | **1.1.4**：`starfield.hash` 与参数复算一致 | warn（无星表时 skip） |
| SK02 | 观测 | **1.1.4**：`cosmology.sky.summary` 与实算一致（极限星等 ±0.6、可见星 ±20%） | warn（无摘要时 skip） |
| X01 | 通用 | `consistency.open_issues` 非空 | warn |
| X02 | 通用 | `physics` 缺失或 `constants` 为空 | fatal |
| C01 | 定量 | **1.1.5**：守恒账本配平（能量/水/碳/元素，容差见 `conservation`） | warn（无账可算时 skip） |
| C02 | 定量 | **1.1.5**：天体与大气字段不越量纲硬域（`units.check`） | warn |
| C03 | 定量 | **1.1.5**：`certification.coverage` ≥ 30% | warn（未 certify 时 skip） |

评分：`100 − 25×fatal − 4×warn − 2×缺失段`，钳在 0–100。`--strict` 模式下存在 fatal 则退出码 1。

> 1.1.5 起校验项为 44 项（1.1.4 为 39）。`R01` 是唯一会读 `seed.brief` 的检查；卡里缺 `cost` 会被点名——没写代价的选项就是免费奇观。`SK01`/`SK02` 与 `sky --check` 同源：**缺省即 skip**，旧世界不因没登记星表而掉分。
>
> `C01` 有一个特例：如果账本唯一的不平来自「声明值压过模型」（目前是 `C02`，即作者声明了温室但与大气成分推算不符），它判 **pass 并在说明里点名**——1.1.4 的口径是「声明优先、只报不改」，所以这不是自相矛盾，而是作者决策。账本本身照常显示残差，`ledger` 命令也会把 `explained` 单独列出来。

---

## 8. 改设定（1.1.2）

不要手改 JSON。所有改动走 `patch`，它会顺手升版本、记修订、立刻复检：

```bash
python scripts/pangu.py patch world.json --get "cosmology.bodies[0].mass_earth"
python scripts/pangu.py patch world.json --set "cosmology.bodies[0].mass_earth=30.0" \
       --note "加质量，看地壳撑不撑得住"
python scripts/pangu.py diff world-v1.json world-v2.json       # 改了什么 + 要重跑什么
```

- 路径文法：`a.b[0].c`，与切片 `cites`、红队 `target`、CA `source` 同源。
- 默认拒绝写不存在的字段；要新建或往数组末尾追加，加 `--create`。
- 改 `mass_earth` / `radius_earth` / G 后，`density_gcc` 与 `gravity_g` **不会自动跟着变**，`validate` 会报 P01。这是设定决策：要么手动改声明，要么用 `sweep --recalc` 看自洽解长什么样。

反常识度（`validate` 派生量里的 `weirdness`）是信息量指标：推荐 40–70，低于 40 是换皮，高于 70 读者会放弃。它不参与评分。

`patch --suggest` 会顺手把「照这个质量/半径/G，密度与重力应该是多少」算给你（只建议、不写盘）：ρ = M×5.514/R³，g = M/R²×(G'/G)。

---

## 9. 五个配套命令（1.1.3）

| 命令 | 读什么 | 写什么 | 什么时候用 |
|---|---|---|---|
| `plan world.json` | 全字段 + `validate` | 不写盘 | 每轮开工第一件事；`--brief` 一行、`--next` 一条命令、`--axe N` 只看一斧 |
| `options [world] --axe N / --roll / --adopt` | `references/选项卡.md` + `seed.brief` | 只写 `seed.brief.choices`（走 `record_revision`） | 缺想法时抽卡；定了方向就采纳 |
| `entail world.json --write --yes` | `cosmology` / `physics` / `chemistry` / `biology` | 只往 `cosmology.sky_phenomena` 追加 `〔entail Exx〕` 条目 | 斧 7 补天象；改设定后 `--check` 验活 |
| `review world.json` | 全部 + 真跑地图/演化复算 | **不写盘** | 交付前一次；`--fast` 秒级、`--strict` 进 CI |
| `whatif world.json --set/--scale` | 全部（副本） | 默认不写盘；`--write` 另存假设世界 | 「如果改这一条会怎样」；与 `sweep` 的分工见下 |

四条只读/半只读命令的共同约定：**只补自己的那一段，不动别人的字段**。`plan` 与 `review` 不改任何东西，`options` 不碰物理层，`entail` 不反推设定，`whatif` 只改内存副本。这条边界是 1.1.3 能在 1.1.2 之上平滑升级的原因。

`review` 与 `whatif` 的判据：

| | `review` | `whatif` |
|---|---|---|
| 回答 | 能不能交（八项，一个结论） | 改了会怎样（代价 / 审查 / 现象 / 下游） |
| 副作用 | 无 | 只在 `--write` 时写一个新文件 |
| 与 `plan` 的关系 | 复用其六项门槛的口径，另加演化与推论 | 不涉及斧位 |
| 与 `sweep` 的关系 | `sweep` 的结果可以拿来当 `whatif` 的输入假设 | `sweep` 扫一个数，`whatif` 任意多字段 |
