# -*- coding: utf-8 -*-
"""
盘古 · 必然推论引擎
===================
1.1.3 新增：想象力不该只靠灵感，也可以靠**推导**。

给定一份已立好律的 world.json，本模块按一组「后果规则」机械推出：
    这个世界的居民**必然**会看见什么、摸到什么、没法做什么。

每条推论都带三样东西：
    claim  一句话断言（必须是可证伪的）
    why    由哪个字段推得（source path）
    trace  可观测的痕迹（可直接写进 sky_phenomena）

`entail --write` 会把痕迹按幂等方式回写 `cosmology.sky_phenomena`，
用 `〔entail E01〕` 标记出处；`entail --check` 检查回写过的推论是否仍然成立。

设计约束：
  · 只做**正向推导**（设定 → 现象），绝不反推（现象 → 设定），否则就是倒因为果
  · 规则只用 world.json 里已声明的数，不猜、不补、不发明新常数
  · 强度只有两档：必然（可由数值直接算出）/ 很可能（生态与社会的合理外推）
"""

from __future__ import annotations

import re
from typing import Any

import world_schema as ws

MARK_RE = re.compile(r"〔entail (E\d{2})〕")


# ════════════════════════════════════════════════════════════════════
# 取值助手
# ════════════════════════════════════════════════════════════════════

def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _num(v: Any, d: float = 0.0) -> float:
    return ws._num(v, d)


def _bodies(world: dict) -> list:
    return [b for b in _list(_dict(world.get("cosmology")).get("bodies"))
            if isinstance(b, dict)]


def _stars(world: dict) -> list:
    return [s for s in _list(_dict(world.get("cosmology")).get("stars"))
            if isinstance(s, dict)]


def _b0(world: dict) -> dict:
    bs = _bodies(world)
    return bs[0] if bs else {}


def _cal(world: dict) -> dict:
    return _dict(_dict(world.get("cosmology")).get("calendar"))


def _atm(world: dict) -> dict:
    return _dict(_b0(world).get("atmosphere"))


def _pm(world: dict) -> dict:
    return _dict(_b0(world).get("planet_map"))


def _pms(world: dict) -> dict:
    return _dict(_pm(world).get("summary"))


def _gravity(world: dict) -> float:
    d = ws.compute_derived(world)
    bs = d.get("bodies") or []
    return _num((bs[0] if bs else {}).get("gravity_g_calc"), 0.0)


def _solvent(world: dict) -> str:
    sv = _dict(world.get("chemistry")).get("solvent")
    if isinstance(sv, dict):
        return str(sv.get("name") or "").strip()
    return str(sv or "").strip()


def _has_satellite(world: dict) -> bool:
    ids = {b.get("id") for b in _bodies(world)}
    for b in _bodies(world)[1:]:
        parent = str(_dict(b.get("orbit")).get("parent") or "")
        if parent in ids:
            return True
    return False


# ════════════════════════════════════════════════════════════════════
# 规则
# ════════════════════════════════════════════════════════════════════

def _mk(eid, name, claim, why, trace, src, strength="必然"):
    return {"id": eid, "name": name, "claim": claim, "why": why,
            "trace": trace, "src": list(src), "strength": strength,
            "phenomenon": f"「{name}」{trace}〔entail {eid}〕"}


def _r01(world):   # 双星 → 双影
    st = _stars(world)
    if len(st) < 2:
        return None
    t1, t2 = _num(st[0].get("temp_k")), _num(st[1].get("temp_k"))
    dt = int(abs(t1 - t2)) if t1 and t2 else 0
    return _mk(
        "E01", "双影",
        f"任何直立物体同时投出两道影子，一锐一糊；两星色温差 {dt} K，影子边缘颜色不同。",
        f"cosmology.stars 有 {len(st)} 颗恒星，两颗的方位角随互绕周期分开，"
        f"任何点光源都会在障碍后留下独立的本影。",
        f"正午时两道影子几乎重合成一个厚影；影子夹角随双星周期每日变化。",
        ["cosmology.stars[0].temp_k", "cosmology.stars[1].temp_k"])


def _r02(world):   # 三颗以上恒星 → 没有真正黑夜
    st = _stars(world)
    if len(st) < 3:
        return None
    return _mk(
        "E02", "不落的灯",
        f"天上共有 {len(st)} 颗恒星，最远的一颗从不落下，夜里只是「暗了一些」。",
        "层级三合星中，外层伴星的角距离远大于内双星，其方位长期固定；"
        "它的照度虽低，却足以在地面留下可辨的第二道弱影。",
        "夜里没有完全的黑暗，最暗时也能看见地面轮廓；「黑夜」在他们的语言里是「弱光」。",
        ["cosmology.stars[].orbit.a_au", "cosmology.stars[].luminosity_solar"])


def _r03(world):   # 无恒星 → 天空恒黑
    cos = _dict(world.get("cosmology"))
    if cos.get("has_stars") is not False and _stars(world):
        return None
    es = str(cos.get("energy_source") or "")
    return _mk(
        "E03", "恒黑之天",
        "天空永远是黑的，没有日出日落，只有热源的强弱变化。",
        f"cosmology.has_stars=false，能量来自「{es or '行星内部'}」；"
        "可见光的唯一来源是岩浆、生物发光与地缝。",
        "居民的方位感来自地热梯度而非太阳；「日出」这个词在他们语言里不存在。",
        ["cosmology.has_stars", "cosmology.energy_source"])


def _r04(world):   # 潮汐锁定 → 永昼永夜
    b0 = _b0(world)
    locked = (b0.get("rotation_hours") in (None, 0)
              or _pm(world).get("tidal_locked") is True)
    if not locked:
        return None
    return _mk(
        "E04", "固定的晨昏线",
        "一半星球永远是白天，一半永远是夜；两半之间是一条可以走到的线。",
        "自转被潮汐锁定，昼夜不再由旋转给出，而由经度给出。",
        "晨昏线上太阳永远贴在地平线，影子无限拉长；越过这条线就是永夜。",
        ["cosmology.bodies[0].rotation_hours"])


def _r05(world):   # 快自转 → 碎云与小气旋
    rot = _num(_b0(world).get("rotation_hours"), 0)
    if not (0 < rot < 14):
        return None
    return _mk(
        "E05", "碎云",
        "云被撕成一格一格的小块，气旋小而多，天气变化以小时计。",
        f"自转周期 {rot:g} 小时，科氏力强，罗斯贝半径小，涡旋无法长成大片。",
        "天空像撒了一把棉絮；同一地点一天能经历四次晴雨。",
        ["cosmology.bodies[0].rotation_hours"])


def _r06(world):   # 慢自转 → 昼夜两世界
    rot = _num(_b0(world).get("rotation_hours"), 0)
    if not (rot > 40):
        return None
    return _mk(
        "E06", "昼与夜是两种世界",
        f"一天 {rot:g} 小时，正午与午夜是两个气候完全不同的星球。",
        "自转慢，地表在长昼里持续增温、长夜里持续失温，昼夜温差可达数十度。",
        "夜里结霜、正午起尘卷；生物要么昼伏，要么夜伏，没有全天候活动者。",
        ["cosmology.bodies[0].rotation_hours"])


def _r07(world):   # 大倾角 → 极端季节
    tilt = _num(_b0(world).get("axial_tilt_deg"), 0)
    if not (tilt > 40):
        return None
    return _mk(
        "E07", "半年的太阳",
        f"转轴倾角 {tilt:g}°，极昼与极夜会伸到中纬度：夏天太阳不落，冬天太阳不起。",
        "倾角越大，晨昏线与极圈越低；超过 45° 时极圈进入温带。",
        "夏天的夜晚天边仍是亮的；冬天有连续几十天看不见太阳，只有天光。",
        ["cosmology.bodies[0].axial_tilt_deg"])


def _r08(world):   # 近零倾角 → 无季节
    tilt = _b0(world).get("axial_tilt_deg")
    if tilt is None or not (0 <= _num(tilt) < 5):
        return None
    return _mk(
        "E08", "没有四季",
        "没有季节：气候只由纬度决定，一年到头是同一个天气。",
        "倾角接近 0，年辐照不随公转变化；只有轨道偏心率还能给出一点起伏。",
        "他们的历法里没有「春」「秋」，只有旱季与雨季；「年」这个概念可能根本不必要。",
        ["cosmology.bodies[0].axial_tilt_deg"])


def _r09(world):   # 高重力 → 无飞行
    g = _gravity(world)
    if not (g > 1.5):
        return None
    return _mk(
        "E09", "没有翅膀",
        f"表面重力 {g:.2f} g：任何靠拍翼起飞的生物都太大、太重，天空里没有大型飞行者。",
        "升力 ∝ 翼面积 × 速度²，而维持质量所需的升力 ∝ g；g 越大，可实现的翼载越低。",
        "只有滑翔与弹跳，没有翱翔；「鸟」这个词在他们的语言里可能指虫。",
        ["cosmology.bodies[0].gravity_g"])


def _r10(world):   # 低重力 → 巨型生物与大气逃逸
    g = _gravity(world)
    if not (0 < g < 0.6):
        return None
    return _mk(
        "E10", "大而轻的世界",
        f"表面重力只有 {g:.2f} g：生物可以长到地球上限的数倍，但大气在缓慢逃逸。",
        "结构强度随尺度按平方增长、重量按立方增长；重力越小，可支撑的体型越大。"
        "同时逃逸速度低，轻气体持续流失。",
        "有比树更高的动物；天空的颜色随地质年代变淡——大气在变薄。",
        ["cosmology.bodies[0].gravity_g"])


def _r11(world):   # 高压 → 声音传得远
    p = _num(_atm(world).get("surface_pressure_kpa"), 0)
    if not (p > 200):
        return None
    return _mk(
        "E11", "听得见的远方",
        f"气压 {p:g} kPa：声音传得极远、音调低沉，远处的人喊一声就能听见。",
        "声速 ∝ √(气压/密度)，高压气体让声波衰减更慢，也让低频更易传播。",
        "没有「悄悄话」；战争靠鼓与号角，情报靠喊。",
        ["cosmology.bodies[0].atmosphere.surface_pressure_kpa"])


def _r12(world):   # 低压 → 水低温沸腾
    p = _num(_atm(world).get("surface_pressure_kpa"), 0)
    if not (0 < p < 40):
        return None
    return _mk(
        "E12", "会沸腾的湖",
        f"气压只有 {p:g} kPa：水在不到 80 °C 就沸腾，声音传不远。",
        "沸点随气压下降；低气压也意味着声波能量更快散失。",
        "湖面会在午后冒泡；他们的「煮熟」与地球不是同一个温度。",
        ["cosmology.bodies[0].atmosphere.surface_pressure_kpa"])


def _r13(world):   # 强温室 → 无冰盖
    gh = _num(_atm(world).get("greenhouse_delta_k"), 0)
    if not (gh > 60):
        return None
    return _mk(
        "E13", "没有冰的颜色",
        f"温室补偿 {gh:g} K：两极也不结冰，全球没有白色。",
        "强温室抹平了纬向温差，极区温度仍高于冰点。",
        "这个世界没有「雪」这个词；白色只能从生物或矿物里得到。",
        ["cosmology.bodies[0].atmosphere.greenhouse_delta_k"])


def _r14(world):   # 低反照率 → 温差大
    alb = _num(_b0(world).get("albedo"), 0.3)
    if not (0 < alb < 0.15):
        return None
    return _mk(
        "E14", "吸光的土地",
        f"反照率 {alb:g}：地表几乎把收到的光全吃下去，昼夜温差被放大。",
        "吸收率高 → 白天升温快；夜里没有云层回辐射 → 降温也快。",
        "地面在正午烫得不能赤脚，黎明前却结霜。",
        ["cosmology.bodies[0].albedo"])


def _r15(world):   # 长年
    y = _num(_cal(world).get("year_days"), 0)
    if not (y > 500):
        return None
    return _mk(
        "E15", "长得记不住的一年",
        f"一年 {y:g} 天：没有人能凭记忆比较两个年份，历史必须靠记录。",
        "年长超过个体寿命的若干分之一时，经验无法跨年传递。",
        "他们最早的技术之一是记账；「老人」是图书馆而非顾问。",
        ["cosmology.calendar.year_days"])


def _r16(world):   # 短年
    y = _num(_cal(world).get("year_days"), 0)
    if not (0 < y < 100):
        return None
    return _mk(
        "E16", "密到数不清的纪年",
        f"一年只有 {y:g} 天：纪年编号增长极快，长时段的记忆被压缩。",
        "年短意味着季节循环快，代际与年份的对应关系很快失效。",
        "他们用「第几个王朝」而非「公元几年」；数字大到没人念全。",
        ["cosmology.calendar.year_days"])


def _r17(world):   # 日长异常
    d = _num(_cal(world).get("day_hours"), 0)
    if not (d and abs(d - 24) / 24 > 0.30):
        return None
    return _mk(
        "E17", "不是二十四小时的一天",
        f"一天 {d:g} 小时：作息、劳动与睡眠都必须重新分配。",
        "昼夜长度直接决定休息节律与劳动窗口，与地球的 24 小时无关。",
        "他们可能睡两觉（昼中与夜中），也可能连续清醒一整个白天。",
        ["cosmology.calendar.day_hours"], "很可能")


def _r18(world):   # 有卫星 → 大潮
    if not _has_satellite(world):
        return None
    return _mk(
        "E18", "可走的潮间带",
        "每天有两次明显的潮汐，海岸线在一天里进退数公里。",
        "卫星引力在行星表面造成潮差；潮差随卫星质量与轨道距离变化。",
        "海岸有一圈只有退潮时能走的「潮路」，城市按潮汐而非按太阳作息。",
        ["cosmology.bodies[1].mass_earth", "cosmology.bodies[1].orbit.a_au"], "很可能")


def _r19(world):   # 无卫星 → 无潮间带
    if _has_satellite(world) or len(_bodies(world)) > 1:
        return None
    return _mk(
        "E19", "不动的海",
        "海面几乎不涨落，只有风浪；没有潮间带生态。",
        "没有大卫星，只剩太阳的潮汐力，约为月球潮汐的千分之一量级。",
        "他们的「海」是一个恒定平面；「退潮」不是本地词汇。",
        ["cosmology.bodies"], "很可能")


def _r20(world):   # 高海洋占比
    of = _num(_pms(world).get("ocean_fraction"), 0)
    if not (of > 0.9):
        return None
    return _mk(
        "E20", "没有远方",
        f"海洋占 {of * 100:.0f}%：没有大陆，只有群岛与漂流文明。",
        "陆地碎片化后，长距离运输只能靠船，帝国的尺度被航程限制。",
        "他们的地图是海图；「领土」= 一条航线加几个补给点。",
        ["cosmology.bodies[0].planet_map.summary.ocean_fraction"], "很可能")


def _r21(world):   # 低海洋占比
    of = _num(_pms(world).get("ocean_fraction"), -1)
    if not (0 <= of < 0.15):
        return None
    return _mk(
        "E21", "盐与沙",
        f"海洋只占 {of * 100:.0f}%：大片内陆，盐湖与沙暴是常态。",
        "水量不足以填满盆地，蒸发量大于补给的内陆区变成盐壳。",
        "所有的路都经过井；「水权」是最硬的政治。",
        ["cosmology.bodies[0].planet_map.summary.ocean_fraction"], "很可能")


def _r22(world):   # 极高海拔
    me = _num(_pms(world).get("max_elevation_km"), 0)
    if not (me > 12):
        return None
    return _mk(
        "E22", "走到呼吸不到的地方",
        f"最高峰 {me:g} km：峰顶气压不足海平面的一半，人会缺氧。",
        "气压随高度指数衰减，超过 5.5 km 后血氧饱和度显著下降。",
        "所有文明都把「高山」与「死亡」写进同一个词；山口有关卡也有关税。",
        ["cosmology.bodies[0].planet_map.summary.max_elevation_km"], "很可能")


def _r23(world):   # 非水溶剂
    sv = _solvent(world)
    if not sv or sv in ("水", "water", "H2O", "水基"):
        return None
    return _mk(
        "E23", f"{sv}的雨",
        f"降雨与河流不是水，而是{sv}：雨滴的黏度、沸点、密度全都要重算。",
        "溶剂决定液体的物理性质，进而决定雨滴大小、河流速度与「湿」的含义。",
        f"下雨时衣服上的残留不是水痕，而是{sv}的结晶；「擦干」是很晚才发明的动作。",
        ["chemistry.solvent"])


def _r24(world):   # 虚构元素
    els = [e for e in _list(_dict(world.get("chemistry")).get("fictional_elements"))
           if isinstance(e, dict)]
    if not els:
        return None
    names = "、".join(str(e.get("name") or e.get("symbol") or "?") for e in els[:3])
    return _mk(
        "E24", "会发光的矿",
        f"这里有地球上不存在的元素（{names}），它们参与生态，也参与交易。",
        "chemistry.fictional_elements 声明了这些元素的相态、丰度与生态作用。",
        f"矿区的土壤颜色与别处不同；当地人用自造字写元素名，外来者念不出来。",
        ["chemistry.fictional_elements"])


def _r25(world):   # 守恒破缺
    bs = [str(x) for x in _list(_dict(world.get("physics")).get("broken_symmetries")) if x]
    if not bs:
        return None
    return _mk(
        "E25", "算不平的账",
        f"守恒律被打破（{'、'.join(bs[:3])}）：任何一笔能量账目都差一点点。",
        "physics.broken_symmetries 声明了破缺方向；破缺意味着存在未建模的泄漏通道。",
        "老仪器与新仪器测出的同一常数不一致；他们有天生的怀疑主义者。",
        ["physics.broken_symmetries"])


def _r26(world):   # 慢光
    gr = None
    for c in _list(_dict(world.get("physics")).get("constants")):
        if not isinstance(c, dict):
            continue
        if str(c.get("symbol", "")).strip().upper() in ("C", "光速"):
            wv = ws._parse_first(c.get("world_value"))
            ev = ws._parse_first(c.get("earth_value"))
            if wv and ev:
                gr = wv / ev
    if not gr or gr > 0.01:
        return None
    return _mk(
        "E26", "看见的都是旧事",
        f"光速只有地球的 {gr:.3g} 倍：看见的一切都滞后，远处的事早已不是那样。",
        "光行时间随距离线性增长，天文观测与日常视觉都出现可测延迟。",
        "他们崇拜「旧光」；天文学的核心技术是高精度延迟校正，而不是望远镜口径。",
        ["physics.constants[].world_value"])


def _r27(world):   # 潮汐加热
    cos = _dict(world.get("cosmology"))
    es = str(cos.get("energy_source") or "")
    if "潮汐" not in es:
        return None
    return _mk(
        "E27", "会呼吸的地面",
        "地面在缓慢地鼓与落，幅度以厘米计，周期与轨道一致。",
        "潮汐加热把轨道能量转成行星内部的热，热通过地壳缓慢释放，造成可测的形变。",
        "他们的地震仪是最精密的仪器；建筑的地基要按「呼吸」的相位设计。",
        ["cosmology.energy_source"])


def _r28(world):   # 双峰光合
    st = _stars(world)
    ps = _dict(_dict(world.get("biology")).get("photosynthesis"))
    if len(st) < 2 or not ps:
        return None
    t1, t2 = _num(st[0].get("temp_k")), _num(st[1].get("temp_k"))
    if not (t1 and t2 and abs(t1 - t2) > 1500):
        return None
    return _mk(
        "E28", "两面的叶子",
        "叶片正面与背面颜色不同：一套色素对准主星，另一套对准伴星。",
        f"两颗恒星色温相差 {int(abs(t1 - t2))} K，峰值波长不同，单套色素无法同时高效。",
        "风一吹，整片森林翻出另一种颜色；叶背是他们审美里的「影子色」。",
        ["biology.photosynthesis", "cosmology.stars[].temp_k"])


def _r29(world):   # 一年有几天几夜
    cal = _cal(world)
    y = _num(cal.get("year_days"), 0)
    d = _num(cal.get("day_hours"), 0) / 24.0
    if not (y > 0 and d > 0):
        return None
    n = y / d
    if n < 30:
        return _mk(
            "E29", "一年只有几十个昼夜",
            f"一年只有约 {n:.0f} 个昼夜：季节以「天」计，没人会说「去年的这个时候」。",
            f"历法年 {y:g} 天 × 一天 {d * 24:g} 小时 → 一年 {n:.0f} 个昼夜；"
            "年与日的比值太小时，季节与昼夜无法分层。",
            "他们的纪年单位是「月」而不是「年」；「去年」是个含糊的词。",
            ["cosmology.calendar.year_days", "cosmology.calendar.day_hours"])
    if n > 800:
        return _mk(
            "E29", "数不清的昼夜",
            f"一年有 {n:.0f} 个昼夜：没有人能数完一年，历法必须靠天文周期校准。",
            f"历法年 {y:g} 天 ÷ 一天 {d:.2f} 天 = {n:.0f} 个昼夜，远超可计数的范围。",
            "他们有「年」的概念但没有「第几天」的说法；节日按星位触发，不按日期。",
            ["cosmology.calendar.year_days", "cosmology.calendar.day_hours"])
    return None


def _r30(world):   # 一年 = 整数个双星周期
    st = _stars(world)
    p_planet = _num(_dict(_b0(world).get("orbit")).get("period_days"), 0)
    periods = [_num(_dict(s.get("orbit")).get("period_days"), 0) for s in st]
    periods = [p for p in periods if p > 0]
    if len(st) < 2 or not p_planet or not periods:
        return None
    p_pair = min(periods)
    ratio = p_planet / p_pair
    k = round(ratio)
    if k < 2 or abs(ratio - k) / k > 0.02:
        return None
    return _mk(
        "E30", "不用闰的年",
        f"一年正好 {k} 个双星周期：历法不需要闰日，也不会漂移。",
        f"行星周期 {p_planet:g} 天 ÷ 双星互绕周期 {p_pair:g} 天 = {ratio:.2f} ≈ {k}；"
        "这是开普勒第三定律的整数巧合，不是设定者的安排。",
        "他们的「月」不是月亮的月，而是双星合的次数；每次合都是节日，也都是税期。",
        ["cosmology.stars[].orbit.period_days",
         "cosmology.bodies[0].orbit.period_days"])


def _satellites(world) -> list:
    bs = _bodies(world)
    pid = str(_b0(world).get("id") or "")
    return [b for b in bs if pid and str(_dict(b.get("orbit")).get("parent") or "") == pid]


def _r31(world):   # 多星且够亮 → 夜空不黑
    st = _stars(world)
    lum = ws.total_luminosity(world)
    if len(st) < 2 or lum < 1.0:
        return None
    return _mk(
        "E31", "没有真正的黑夜",
        f"{len(st)} 颗恒星总光度 {lum:.2f} L☉：夜空被压在约 20 mag/arcsec² 以内，"
        "极限星等不到 5 等，银河看不见。",
        f"恒星 {len(st)} 颗、合计 {lum:.2f} L☉；多光源把高层大气常年照亮，"
        "天光下不去，暗星就浮不上来。",
        "他们的夜空只有几十到几百颗星，银河是传说，不是景；"
        "「星图」是奢侈品，不是导航工具。",
        ["cosmology.stars[].luminosity_solar"])


def _r32(world):   # 无恒星 → 没有「星」
    st = _stars(world)
    if st or _dict(world.get("cosmology")).get("has_stars") is not False:
        return None
    return _mk(
        "E32", "没有星的世界",
        "天上没有「星」这个概念：只有地热、伴星反照或极光；方位靠热源与地形，不靠天。",
        "cosmology.has_stars = false 且 stars 为空——没有任何核聚变光源。",
        "他们的神话里没有「星」这个词；远行靠地标与风向，"
        "「北方」可能是「冷的那边」而不是「星的那边」。",
        ["cosmology.has_stars", "cosmology.stars"])


def _r33(world):   # 近月 → 月盘大、月相可辨
    b0 = _b0(world)
    r_km = _num(b0.get("radius_km"), 0.0) or _num(b0.get("radius_earth"), 1.0) * 6371.0
    if r_km <= 0:
        return None
    for s in _satellites(world):
        o = _dict(s.get("orbit"))
        a_km = _num(o.get("a_km"), 0.0) or _num(o.get("a_au"), 0.0) * 149597870.7
        if a_km <= 0:
            continue
        ratio = a_km / r_km
        if ratio < 20.0:
            return _mk(
                "E33", "大得吓人的月亮",
                f"{s.get('name') or s.get('id')} 在 {ratio:.0f} 个行星半径处："
                "月盘比地球的月亮大得多，月相一眼可辨，满月夜能看清影子。",
                f"卫星轨道 {a_km:.0f} km ÷ 行星半径 {r_km:.0f} km = {ratio:.1f}（< 20）。",
                "满月夜不用点灯；他们的历法按月相而不是按月数；"
                "月食是全民事件，不是天文爱好者的谈资。",
                ["cosmology.bodies[].orbit.a_au", "cosmology.bodies[0].radius_km"])
    return None


def _r34(world):   # 快自转 → 星移
    rot = _num(_b0(world).get("rotation_hours"), 0.0)
    if not (0 < rot < 12.0):
        return None
    return _mk(
        "E34", "看得见的星移",
        f"一天只有 {rot:g} 小时：星星跑得飞快，肉眼就能看出「星移」，"
        "长曝光会把星点拉成弧。",
        f"自转周期 {rot:g} h，天球每小时转过 {360.0 / rot:.1f}°。",
        "他们的谚语用「星走到哪」计时；相机与长曝光是天文工具，不是艺术。",
        ["cosmology.bodies[0].rotation_hours"])


def _r35(world):   # 大倾角 → 极昼极夜
    tilt = _num(_b0(world).get("axial_tilt_deg"), 0.0)
    if tilt <= 45.0:
        return None
    return _mk(
        "E35", "整夜的星与整日的黑",
        f"倾角 {tilt:g}°：高纬有极昼极夜——夏天整夜有星，冬天整日无星（视纬度）。",
        f"自转轴倾角 {tilt:g}° > 45°，高纬地区太阳可整日不落、也可整日不升。",
        "极圈内的人按「有星季 / 无星季」记事；星图只在那半年有用。",
        ["cosmology.bodies[0].axial_tilt_deg"])


def _r36(world):   # 高压 → 星光偏红、地平压扁
    p = _num(_atm(world).get("surface_pressure_kpa"), 0.0)
    if p <= 200.0:
        return None
    return _mk(
        "E36", "压扁的星",
        f"气压 {p:g} kPa：星光偏红，地平线附近的天体被压扁，星图边缘会畸变。",
        f"地表气压 {p:g} kPa，大气折射与消光都远强于地球。",
        "低空的星看着是椭的；「星圆」是个需要爬到高处才能验证的说法。",
        ["cosmology.bodies[0].atmosphere.surface_pressure_kpa"])


RULES = [
    _r01, _r02, _r03, _r04, _r05, _r06, _r07, _r08,
    _r09, _r10, _r11, _r12, _r13, _r14, _r15, _r16,
    _r17, _r18, _r19, _r20, _r21, _r22, _r23, _r24,
    _r25, _r26, _r27, _r28, _r29, _r30,
    _r31, _r32, _r33, _r34, _r35, _r36,
]

# 规则目录（供 `entail --list` 与 --only/--exclude 校验）。
# 与 _rNN 一一对应：改规则先改这里，再改函数，两边不允许漂移。
RULES_META = [
    ("E01", "双影", "≥2 颗恒星", "必然"),
    ("E02", "不落的灯", "≥3 颗恒星", "必然"),
    ("E03", "恒黑之天", "无恒星", "必然"),
    ("E04", "固定的晨昏线", "潮汐锁定", "必然"),
    ("E05", "碎云", "自转 < 14 h", "很可能"),
    ("E06", "昼与夜是两个气候", "自转 > 40 h", "很可能"),
    ("E07", "半年的太阳", "倾角 > 40°", "必然"),
    ("E08", "没有四季", "倾角 < 5°", "必然"),
    ("E09", "没有翅膀", "表面重力 > 1.5 g", "必然"),
    ("E10", "巨型生物", "表面重力 < 0.6 g", "很可能"),
    ("E11", "听得见的远方", "气压 > 200 kPa", "必然"),
    ("E12", "会沸腾的湖", "气压 < 40 kPa", "必然"),
    ("E13", "没有冰的颜色", "温室 > 60 K", "很可能"),
    ("E14", "吸光的土地", "反照率 < 0.15", "很可能"),
    ("E15", "长得记不住的一年", "年长 > 500 d", "很可能"),
    ("E16", "密到数不清的纪年", "年长 < 100 d", "很可能"),
    ("E17", "不是二十四小时的一天", "日长偏离 24 h > 30%", "很可能"),
    ("E18", "可走的潮间带", "有卫星", "必然"),
    ("E19", "不动的海", "无卫星", "很可能"),
    ("E20", "没有远方", "海洋 > 90%", "很可能"),
    ("E21", "盐与沙", "海洋 < 15%", "很可能"),
    ("E22", "呼吸不到的地方", "最高峰 > 12 km", "很可能"),
    ("E23", "不是水的雨", "溶剂非水", "必然"),
    ("E24", "会发光的矿", "有虚构元素", "必然"),
    ("E25", "算不平的账", "守恒律破缺", "必然"),
    ("E26", "看见的都是旧事", "光速 ≤ 1% c", "必然"),
    ("E27", "会呼吸的地面", "能量源含潮汐", "很可能"),
    ("E28", "两面的叶子", "双星色温差 > 1500 K 且有光合", "很可能"),
    ("E29", "几十个昼夜", "每年昼夜数 < 30 或 > 800", "必然"),
    ("E30", "不用闰的年", "行星周期 / 双星周期 ≈ 整数", "必然"),
    ("E31", "没有真正的黑夜", "≥2 颗恒星且总光度 ≥1.0 L☉", "必然"),
    ("E32", "没有星的世界", "无恒星", "必然"),
    ("E33", "大得吓人的月亮", "卫星轨道 < 20 个行星半径", "很可能"),
    ("E34", "看得见的星移", "自转 < 12 h", "必然"),
    ("E35", "整夜的星与整日的黑", "倾角 > 45°", "必然"),
    ("E36", "压扁的星", "气压 > 200 kPa", "很可能"),
]


def meta_rows() -> list:
    return [{"id": i, "name": n, "when": w, "strength": s} for i, n, w, s in RULES_META]


def known_ids() -> set:
    return {i for i, _, _, _ in RULES_META}


# ════════════════════════════════════════════════════════════════════
# 对外
# ════════════════════════════════════════════════════════════════════

def derive(world: dict) -> list:
    """按规则推导，返回命中的推论（顺序稳定，便于 diff 与复算）。"""
    out = []
    for fn in RULES:
        try:
            r = fn(world)
        except Exception:      # noqa: BLE001 —— 单条规则出错不该拖垮全部推论
            r = None
        if r:
            out.append(r)
    return out


def by_id(rows: list, eid: str):
    for r in rows:
        if r["id"].upper() == str(eid).strip().upper():
            return r
    return None


def existing_marks(world: dict) -> dict:
    """扫描 sky_phenomena，返回 {E01: [索引...]}。"""
    out = {}
    sky = _list(_dict(world.get("cosmology")).get("sky_phenomena"))
    for i, s in enumerate(sky):
        for m in MARK_RE.findall(str(s)):
            out.setdefault(m, []).append(i)
    return out


def stale_marks(world: dict, rows: list) -> list:
    """
    回写过但**现在不再成立**的推论（改了设定却忘了删旧天象）。

    返回 [{"id": "E07", "index": 3}]，供 `entail --check` 报修。
    """
    live = {r["id"] for r in rows}
    marks = existing_marks(world)
    return [{"id": k, "index": v[0]} for k, v in sorted(marks.items()) if k not in live]


def apply_marks(world: dict, rows: list, only: list = None) -> dict:
    """
    把推论按 `〔entail E01〕` 幂等写进 cosmology.sky_phenomena。

    返回 {added, kept, removed}（removed 只统计因重复而删掉的同号条目）。
    """
    cos = world.setdefault("cosmology", {})
    sky = cos.get("sky_phenomena")
    if not isinstance(sky, list):
        sky = []
        cos["sky_phenomena"] = sky
    want = [r for r in rows if not only or r["id"] in only]

    # 同号去重：保留第一条，其余删掉
    seen, removed = set(), []
    for i in range(len(sky) - 1, -1, -1):
        m = MARK_RE.search(str(sky[i]))
        if not m:
            continue
        if m.group(1) in seen:
            removed.append(sky.pop(i))
        else:
            seen.add(m.group(1))

    added = []
    for r in want:
        if r["id"] in seen:
            continue
        sky.append(r["phenomenon"])
        added.append(r["id"])
        seen.add(r["id"])
    return {"added": added, "kept": sorted(seen - set(added)), "removed": removed}


def format_report(rows: list, world: dict = None) -> str:
    if not rows:
        return ("没有命中任何推论。这通常意味着设定还太稀薄——"
                "先去斧 2/3 把恒星、自转、重力、气压立起来。")
    L = [f"【必然推论】命中 {len(rows)} 条（设定 → 现象，不是现象 → 设定）"]
    cur = None
    for r in rows:
        src = r["src"][0] if r["src"] else "—"
        top = src.split(".")[0]
        if top != cur:
            cur = top
            L.append(f"\n  ── 由 {top} 推出 ──")
        L.append(f"  {r['id']} [{r['strength']}] {r['name']}")
        L.append(f"      {r['claim']}")
        L.append(f"      痕迹：{r['trace']}")
        L.append(f"      出处：{src}")
    return "\n".join(L)
