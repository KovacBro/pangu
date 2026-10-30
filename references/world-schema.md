# world.json 字段规范（单一数据源）

一份 `world.json` 同时喂给 `pangu.py validate`（校验/打分）、`pangu.py preview`（3D 页）、`pangu.py export`（世界档案）。**改设定只改这个文件**，再重跑脚本。

## 目录

1. 设计原则
2. 顶层结构
3. 逐段字段表
4. 单位与换算约定
5. 3D 预览专用字段
6. 最小可用示例
7. 校验规则清单

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

### 3.3 `cosmology`

| 字段 | 类型 | 说明 |
|---|---|---|
| `frame` | str | 框架标签，自由文本，如 `circumbinary-superearth`、`shell-world`、`no-star-tidal` |
| `topology` | str | 空间拓扑描述（欧氏/闭合/分层/非欧） |
| `has_stars` | bool | 有无恒星。无恒星世界仍需给出替代能源 |
| `stars` | obj[] | 见下 |
| `bodies` | obj[] | 见下。**第 0 个视为主角天体** |
| `sky_phenomena` | str[] | 居民抬头能看见的异常（痕迹律的落点），3–6 条 |
| `calendar` | obj | `{day_hours, year_days, months, month_days, epoch}` |

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
| `atmosphere` | obj\|null | | `{surface_pressure_kpa, composition{}, color, height_km}` |
| `biomes` | obj[] | | `{id, name, color, elevation}`，`elevation` 0–1 升序，供 3D 着色器插值 |
| `rings` | obj\|null | | `{inner_r, outer_r, color, opacity}`，半径单位为**行星半径倍数** |
| `visual_radius` | num | | 3D 显示半径（夸张值，非真实比例），缺省按 `radius_earth` 映射 |
| `note` | str | | 一句话特征 |

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
| `revisions` | obj[] | `{version, date, change}`，改设定必记 |

### 3.10 `consistency`

| 字段 | 类型 | 说明 |
|---|---|---|
| `score` | num | 0–100，由 `validate` 计算 |
| `checks` | obj[] | `{id, dim, question, verdict, note}`，`dim` ∈ `structure|energy|observation|evolution|narrative`，`verdict` ∈ `pass|warn|fatal` |
| `open_issues` | str[] | 未解决的遗留问题，交付时必须为空或经用户确认 |

### 3.11 `narrative`

| 字段 | 类型 | 说明 |
|---|---|---|
| `three_seconds` | str | 三秒讲完的印象 |
| `setpiece` | str | 最想拍成电影的一幕 |
| `hook` | str | 一句话钩子 |

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
| X01 | 通用 | `consistency.open_issues` 非空 | warn |
| X02 | 通用 | `physics` 缺失或 `constants` 为空 | fatal |

评分：100 − fatal×25 − warn×4，下限 0。`--strict` 模式下存在 fatal 则退出码 1。
