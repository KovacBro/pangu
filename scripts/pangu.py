#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古 Pangu · CLI
================
开天辟地式造世引擎的命令行入口。

    doctor                                     环境自检
    init --name <n> [--seed <s>]               生成骨架 world.json
    validate <world.json> [--strict] [--json]  校验 + 自洽打分
    preview  <world.json> [-o <html>]          生成 3D 预览页
    export   <world.json> [--md <md>]          生成世界档案
    axioms   [--domain <d>] [--cost <t>]        查公理库
    patch    <world.json> --set p=v [--get p]  定点改 / 增 / 查字段（自动升版本）
    sweep    <world.json> --param <p>           参数敏感度扫描，找崩点
    diff     <a.json> <b.json>                  版本对比 + 下游重跑清单
    map      <world.json> [--run|--check]      行星地图：板块/海平面/气候/河网/群系
    ca       <world.json> [--run|--check]      生态演化：编译/跑/复算比对
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import random
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import world_schema as ws  # noqa: E402
import world_tuning as wt  # noqa: E402

TEMPLATE = os.path.join(HERE, "preview_template.html")


# ── 编码与输出 ──────────────────────────────────────────────────────
def _init_io():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def err(msg: str, fix: str = "") -> None:
    sys.stderr.write(f"[ERROR] {msg}" + (f"\n   → {fix}" if fix else "") + "\n")


def say(msg: str = "") -> None:
    sys.stdout.write(msg + "\n")


def warn(msg: str) -> None:
    sys.stdout.write(f"  ! {msg}\n")


# ════════════════════════════════════════════════════════════════════
# doctor
# ════════════════════════════════════════════════════════════════════

def cmd_doctor(args) -> int:
    say("盘古 · 环境自检")
    say("-" * 46)

    ok = True

    v = sys.version_info
    good = v >= (3, 9)
    say(f"  {'✓' if good else '✗'} Python {v.major}.{v.minor}.{v.micro}"
        + ("" if good else "  （需 ≥ 3.9）"))
    ok &= good

    say(f"  {'✓' if os.path.isdir(ROOT) else '✗'} 技能根目录 {ROOT}")

    for rel, label in [
        ("SKILL.md", "技能入口"),
        ("references/公理库.md", "公理库"),
        ("references/七斧创世法.md", "七斧流程"),
        ("references/world-schema.md", "字段规范"),
        ("scripts/preview_template.html", "3D 模板"),
        ("scripts/mapgen.py", "地图引擎"),
    ]:
        p = os.path.join(ROOT, rel)
        exist = os.path.exists(p)
        size = f"{os.path.getsize(p) / 1024:.0f} KB" if exist else "-"
        say(f"  {'✓' if exist else '✗'} {label:<8} {size:>8}  {rel}")
        ok &= exist

    lib = ws.axiom_library(ROOT)
    say(f"  {'✓' if lib else '✗'} 公理库解析：{len(lib)} 条积木")
    if lib:
        from collections import Counter
        c = Counter(a["domain_cn"] for a in lib)
        say("      " + " ｜ ".join(f"{k}{v}" for k, v in c.items()))

    try:
        with open(os.path.join(ROOT, "scripts", "world_schema.py"), encoding="utf-8") as f:
            compile(f.read(), "world_schema.py", "exec")
        say("  ✓ 校验内核语法通过")
    except Exception as e:
        say(f"  ✗ 校验内核语法错误：{e}")
        ok = False

    say("-" * 46)
    say("  结论：一切就绪，可以开天辟地。" if ok else "  结论：有缺件，请补齐后再开工。")
    return 0 if ok else 3


# ════════════════════════════════════════════════════════════════════
# init
# ════════════════════════════════════════════════════════════════════

def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name.strip().lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or "world"


def cmd_init(args) -> int:
    today = _dt.date.today().isoformat()
    wid = args.id or _slug(args.name)
    if not re.match(r"^[a-z0-9][a-z0-9_\-]*$", wid):
        pid = _slug(wid)
        warn(f"id 「{wid}」含非法字符，已改为「{pid}」")
        wid = pid

    stars = []
    has_stars = not args.no_stars
    if has_stars:
        n = max(1, min(4, args.star_count))
        presets = [
            dict(id="A", name="主星", cls="G2V", m=1.00, r=1.00, l=1.00, t=5780, c="#FFF6E2"),
            dict(id="B", name="伴星", cls="K1V", m=0.82, r=0.79, l=0.46, t=5100, c="#FFD5A0"),
            dict(id="C", name="远星", cls="M4V", m=0.28, r=0.30, l=0.008, t=3300, c="#FF9C6B"),
            dict(id="D", name="暗星", cls="M8V", m=0.10, r=0.14, l=0.0004, t=2600, c="#E06A4A"),
        ]
        for i in range(n):
            p = presets[i]
            orbit = None
            if n >= 2:
                a = 0.15 if i < 2 else 8.0 * i
                orbit = {"parent": "AB" if i < 2 else "AB", "a_au": a,
                         "period_days": round((a * 2) ** 1.5 / max(0.1, 1.0) * 365.25, 1)
                         if i < 2 else round(365.25 * (a ** 1.5 / 1.8), 1),
                         "eccentricity": 0.02}
            stars.append({
                "id": p["id"], "name": p["name"], "class": p["cls"],
                "mass_solar": p["m"], "radius_solar": p["r"],
                "luminosity_solar": p["l"], "temp_k": p["t"],
                "color": p["c"], "orbit": orbit,
                "note": "待填写",
            })

    world = {
        "meta": {
            "id": wid,
            "name": args.name,
            "subtitle": "",
            "version": "1.0",
            "created": today,
            "author": "盘古",
            "tagline": "",
            "aesthetic": [],
            "tags": [],
            "autonomy": args.autonomy,
        },
        "seed": {
            "prompt": args.seed or "",
            "core_paradox": "",
            "resolution": "",
            "references": [],
            "forbidden": [],
        },
        "cosmology": {
            "frame": "",
            "topology": "",
            "has_stars": has_stars,
            "stars": stars,
            "bodies": [],
            "sky_phenomena": [],
            "calendar": {"day_hours": None, "year_days": None,
                         "months": None, "month_days": None, "epoch": ""},
        },
        "physics": {"constants": [], "laws": [], "broken_symmetries": [],
                    "new_interactions": [], "conservation_notes": ""},
        "mathematics": None,
        "chemistry": None,
        "biology": None,
        "civilization": None,
        "history": {"eras": [], "revisions": [
            {"version": "1.0", "date": today, "change": "骨架生成"}
        ]},
        "consistency": {"score": 0, "checks": [], "open_issues": []},
        "narrative": {"three_seconds": "", "setpiece": "", "hook": ""},
    }

    out = args.out or os.path.join(os.getcwd(), f"{wid}.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(world, f, ensure_ascii=False, indent=2)

    say(f"✓ 骨架已生成：{out}")
    say("")
    say("  下一步（七斧）：")
    say("   斧2 分判 → 补 cosmology.bodies / calendar")
    say("   斧3 立律 → 补 physics.constants / new_interactions")
    say("   斧4 炼质 → 补 chemistry")
    say("   斧5 化生 → 补 biology")
    say("   斧6 启智 → 补 civilization")
    say("   斧7 演界 → 补 history / narrative，然后 validate")
    say("")
    say(f"  python {os.path.join('scripts', 'pangu.py')} validate \"{out}\"")
    return 0


# ════════════════════════════════════════════════════════════════════
# validate
# ════════════════════════════════════════════════════════════════════

FIX_HINTS = {
    "L01": "在 seed.core_paradox 写一句可证伪的悖论陈述，如「半径三倍地球，却仍有固体地表」。",
    "L02": "给每条 new_interactions 填 cost 字段；或在 constants 每条填 why。",
    "L03": "在 cosmology.sky_phenomena 写 3–6 条居民抬头能看到的异常。",
    "P01": "用 ρ=M×5.514/R³、g=M/R²×(G'/G) 重算，或下调半径/上调 G 的改动幅度。",
    "P03": "把行星 a_au 提到双星间距的 2.5 倍以上，或缩小双星间距。",
    "P04": "把卫星轨道拉远到洛希极限之外，或降低卫星密度。",
    "E01": "调整轨道半长轴、反照率或恒星总光度，使平衡温度落在 150–400 K。",
    "E02": "调整 trophic_levels 的 share，使其按 10% 定律递减并合计为 1。",
    "X02": "先写 physics：至少 1 条常数改动（含 why）和 1 条定律。",
    "N02": "补 seed.references，至少 4 条，每条都要有 use 字段说明怎么用的。",
}


def cmd_validate(args) -> int:
    path = args.world
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "检查路径，或先用 init 生成骨架")
        return 2
    try:
        world = ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查第 " + str(e.lineno) + " 行附近，常见于多余逗号或中文引号")
        return 2

    rep = ws.validate(world, strict=bool(args.strict))

    if args.json:
        say(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))
    else:
        say(ws.format_report(rep))
        if args.fix_hint:
            hints = [(c.id, FIX_HINTS[c.id]) for c in rep.checks
                     if c.verdict in ("fatal", "warn") and c.id in FIX_HINTS]
            if hints:
                say("\n【怎么修】")
                for cid, h in hints:
                    say(f"  {cid}  {h}")

    if args.strict and rep.fatal:
        return 1
    return 0


# ════════════════════════════════════════════════════════════════════
# preview
# ════════════════════════════════════════════════════════════════════

def _escape_json_for_html(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def cmd_preview(args) -> int:
    path = args.world
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "先用 init 生成，或检查路径")
        return 2
    if not os.path.exists(TEMPLATE):
        err(f"模板缺失：{TEMPLATE}", "确认 scripts/preview_template.html 存在")
        return 3

    try:
        world = ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查 JSON 语法")
        return 2

    rep = ws.validate(world)
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()

    title = args.title or ws._get(world, "meta", "name", default="盘古世界") or "盘古世界"
    payload = _escape_json_for_html(world)

    # 用 split/join 而非 str.replace，避免 payload 中出现占位符导致二次替换
    html = html.replace("__PANGU_TITLE__", str(title))
    html = html.replace("__PANGU_WORLD_JSON__", payload)
    html = html.replace("__PANGU_SCORE__", str(rep.score))
    html = html.replace("__PANGU_GRADE__", rep.grade)

    out = args.out or os.path.splitext(path)[0] + "_preview.html"
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(out) / 1024
    say(f"✓ 3D 预览已生成：{out}  ({size:.0f} KB)")
    if rep.fatal:
        warn(f"该世界有 {rep.fatal} 项 fatal，预览仅供观感参考")
    say(f"  双击打开即可。自洽评分 {rep.score}/100 [{rep.grade}]")
    return 0


# ════════════════════════════════════════════════════════════════════
# export
# ════════════════════════════════════════════════════════════════════

def _h(level: int, text: str) -> str:
    return f"{'#' * level} {text}\n"


def _kv_table(rows, headers=("项", "值")) -> str:
    if not rows:
        return "_（暂无）_\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) if str(x) != "" else "—" for x in r) + " |")
    return "\n".join(out) + "\n"


def cmd_export(args) -> int:
    path = args.world
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "检查路径")
        return 2
    try:
        world = ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查 JSON 语法")
        return 2

    rep = ws.validate(world)
    d = rep.derived
    meta = world.get("meta") or {}
    seed = world.get("seed") or {}
    cos = world.get("cosmology") or {}
    phys = world.get("physics") or {}
    math_ = world.get("mathematics") or {}
    chem = world.get("chemistry") or {}
    bio = world.get("biology") or {}
    civ = world.get("civilization") or {}
    hist = world.get("history") or {}
    nar = world.get("narrative") or {}

    base_dir = os.path.dirname(os.path.abspath(path))
    out = args.md or os.path.join(base_dir, "世界档案.md")
    md_dir = os.path.dirname(os.path.abspath(out))

    L = []
    A = L.append
    name = meta.get("name") or "未命名世界"
    sub = meta.get("subtitle") or ""
    A(f"# {name}" + (f" · {sub}" if sub else ""))
    A("")
    if meta.get("tagline"):
        A(f"> {meta['tagline']}")
        A("")
    wd = d.get("weirdness") or {}
    A(f"`v{meta.get('version', '1.0')}` ｜ {meta.get('created', '')} ｜ "
      f"自洽评分 **{rep.score}/100**（{rep.grade}）"
      + (f" ｜ 反常识度 **{wd.get('score')}/100**" if wd else "")
      + " ｜ 生成：盘古")
    A("")
    if meta.get("aesthetic"):
        A("美学基调：" + " · ".join(f"`{x}`" for x in meta["aesthetic"]))
        A("")

    # 三秒印象
    if nar.get("three_seconds") or nar.get("hook"):
        A("---")
        A("")
        if nar.get("hook"):
            A(f"**{nar['hook']}**")
            A("")
        if nar.get("three_seconds"):
            A(nar["three_seconds"])
            A("")

    # 一、核心悖论
    A(_h(2, "一 · 核心悖论"))
    A(_kv_table([
        ("一句话悖论", seed.get("core_paradox", "—")),
        ("凭什么可能", seed.get("resolution", "—")),
        ("原始意图", seed.get("prompt", "—")),
    ], ("项", "内容")))
    if seed.get("forbidden"):
        A("**禁忌**：" + "、".join(seed["forbidden"]))
        A("")

    # 二、三律
    A(_h(2, "二 · 三律自检"))
    sky = cos.get("sky_phenomena") or []
    A(_kv_table([
        ("逆行律", "✓ " + (seed.get("core_paradox") or "—")),
        ("代价律", "✓ " + "；".join(
            f"{i.get('name')}：{i.get('cost')}" for i in (phys.get("new_interactions") or [])
            if isinstance(i, dict) and i.get("cost")) or "见常数表 why"),
        ("痕迹律", "✓ " + ("；".join(sky) if sky else "—")),
    ], ("律", "内容")))

    # 三、宇宙
    A(_h(2, "三 · 宇宙"))
    A(f"**框架**：{cos.get('frame', '—')} ｜ **拓扑**：{cos.get('topology', '—')} ｜ "
      f"**有恒星**：{'是' if cos.get('has_stars') else '否'}")
    A("")
    stars = cos.get("stars") or []
    if stars:
        A(_h(3, "恒星"))
        rows = []
        for s in stars:
            if not isinstance(s, dict):
                continue
            o = s.get("orbit") or {}
            rows.append((s.get("name", "?"), s.get("class", "—"),
                         f"{s.get('mass_solar', '—')} M☉",
                         f"{s.get('luminosity_solar', '—')} L☉",
                         f"{s.get('temp_k', '—')} K",
                         f"{o.get('a_au', '—')} AU / {o.get('period_days', '—')} d"))
        A(_kv_table(rows, ("名", "光谱型", "质量", "光度", "表面温度", "轨道")))

    bodies = cos.get("bodies") or []
    if bodies:
        A(_h(3, "天体"))
        rows = []
        for b in bodies:
            if not isinstance(b, dict):
                continue
            rows.append((b.get("name", "?"), b.get("kind", "—"),
                         f"{b.get('radius_km', '—')} km",
                         f"{b.get('mass_earth', '—')} M⊕",
                         f"{b.get('gravity_g', '—')} g",
                         b.get("note", "—")))
        A(_kv_table(rows, ("名", "类型", "半径", "质量", "表面重力", "特征")))

        A(_h(3, "地形与生物群系"))
        for b in bodies:
            if not isinstance(b, dict) or not b.get("biomes"):
                continue
            A(f"**{b.get('name')}**：" + " → ".join(
                f"{x.get('name')}（{x.get('color')}）" for x in b["biomes"] if isinstance(x, dict)))
            A("")

        atms = [(b.get("name"), b.get("atmosphere")) for b in bodies
                if isinstance(b, dict) and isinstance(b.get("atmosphere"), dict)]
        if atms:
            A(_h(3, "大气"))
            for nm, atm in atms:
                comp = atm.get("composition") or {}
                cs = "、".join(f"{k} {v * 100:.1f}%" if isinstance(v, (int, float)) else f"{k} {v}"
                               for k, v in comp.items())
                A(f"- **{nm}**：{atm.get('surface_pressure_kpa', '—')} kPa，"
                  f"标高 {atm.get('height_km', '—')} km；成分 {cs or '—'}")
            A("")

    if sky:
        A(_h(3, "抬头能看见什么"))
        for s in sky:
            A(f"- {s}")
        A("")

    cal = cos.get("calendar") or {}
    if cal:
        A(_h(3, "历法"))
        A(_kv_table([
            ("一天", f"{cal.get('day_hours', '—')} 小时"),
            ("一年", f"{cal.get('year_days', '—')} 天"),
            ("分月", f"{cal.get('months', '—')} 个月 × {cal.get('month_days', '—')} 天"),
            ("纪元", cal.get("epoch", "—")),
        ]))

    # 四、物理
    A(_h(2, "四 · 物理与数学"))
    consts = phys.get("constants") or []
    if consts:
        rows = [(c.get("symbol"), c.get("earth_value"), c.get("world_value"),
                 c.get("delta"), c.get("why")) for c in consts if isinstance(c, dict)]
        A(_kv_table(rows, ("常数", "地球", "本站", "倍率", "为什么改")))
    laws = phys.get("laws") or []
    if laws:
        A(_h(3, "定律"))
        for x in laws:
            if not isinstance(x, dict):
                continue
            A(f"- **{x.get('name')}**（{x.get('deviation', '—')}）：{x.get('statement', '')}")
            if x.get("consequence"):
                A(f"  - 后果：{x['consequence']}")
        A("")
    nis = phys.get("new_interactions") or []
    if nis:
        A(_h(3, "新相互作用"))
        for x in nis:
            if not isinstance(x, dict):
                continue
            A(f"- **{x.get('name')}**｜作用域 {x.get('range', '—')}")
            A(f"  - 效果：{x.get('effect', '')}")
            A(f"  - 代价：{x.get('cost', '')}")
        A("")
    if phys.get("broken_symmetries"):
        A("**对称性破缺**：" + "、".join(phys["broken_symmetries"]) + "\n")
    if phys.get("conservation_notes"):
        A(f"**守恒律**：{phys['conservation_notes']}\n")

    if math_:
        A(_h(3, "数学"))
        A(_kv_table([
            ("几何", math_.get("geometry", "—")),
            ("数系", math_.get("number_system", "—")),
            ("异常", math_.get("peculiarity", "—")),
            ("后果", math_.get("consequence", "—")),
        ]))

    # 五、化学
    if chem:
        A(_h(2, "五 · 物质"))
        A(_kv_table([
            ("元素表", chem.get("periodic_status", "—")),
            ("溶剂", (chem.get("solvent") or {}).get("name", "—")),
            ("键合", chem.get("key_bonds", "—")),
        ]))
        mats = chem.get("signature_materials") or []
        if mats:
            A(_h(3, "标志性材料"))
            for m in mats:
                if not isinstance(m, dict):
                    continue
                A(f"- **{m.get('name')}**（{m.get('formula', '—')}）：{m.get('property', '')}"
                  + (f"｜用途：{m['use']}" if m.get("use") else ""))
            A("")

        comp = chem.get("composition") if isinstance(chem.get("composition"), dict) else {}
        for key, label in (("planet", "行星本体"), ("atmosphere", "大气"), ("ocean", "海洋")):
            mix = comp.get(key)
            if not isinstance(mix, dict) or not mix:
                continue
            rows = []
            for name, share in sorted(mix.items(), key=lambda kv: -float(kv[1] or 0)):
                try:
                    rows.append((name, f"{float(share) * 100:.2f}%"))
                except (TypeError, ValueError):
                    rows.append((name, str(share)))
            A(_h(3, f"元素配比 · {label}"))
            A(_kv_table(rows))
            A("")

        els = [e for e in (chem.get("fictional_elements") or []) if isinstance(e, dict)]
        if els:
            A(_h(3, "虚构元素"))
            A("命名文法：`⿸气⿰钅X` —— 半包围的「气」包住「钅」与一个自选单字。"
              "这些元素既不是气体也不是金属，而是两者之间的夹缝。\n")
            A("| 元素字 | 符号 | Z | 相态 | 丰度 | 在生态里做什么 |")
            A("|---|---|---|---|---|---|")
            for e in els:
                A(f"| {e.get('glyph', '—')} {e.get('name', '')} | {e.get('symbol', '—')} | "
                  f"{e.get('atomic_number', '—')} | {e.get('phase_at_surface', '—')} | "
                  f"{e.get('abundance_ppm', '—')} ppm | {e.get('role', '—')} |")
            A("")
            for e in els:
                A(f"- **{e.get('name', '')}**（{e.get('symbol', '—')}）：{e.get('reactivity', '')}"
                  + (f"｜**代价**：{e['hazard']}" if e.get("hazard") else "")
                  + (f"｜**痕迹**：{e['trace']}" if e.get("trace") else ""))
            A("")

    # 六、生物
    if bio:
        A(_h(2, "六 · 生命"))
        ec = bio.get("energy_currency") or {}
        gc = bio.get("genetic_carrier") or {}
        A(_kv_table([
            ("能量货币", ec.get("name", "—")),
            ("代谢", bio.get("metabolism_summary", "—")),
            ("遗传载体", gc.get("name", "—")),
        ]))

        bic = bio.get("biochemistry") if isinstance(bio.get("biochemistry"), dict) else {}
        if bic:
            A(_h(3, "生命基座"))
            A(_kv_table([
                ("基座", bic.get("base", "—")),
                ("主元素", bic.get("primary_element", "—")),
                ("结构元素", bic.get("structural_element", "—")),
                ("溶剂", bic.get("solvent", "—")),
                ("限制", bic.get("limits", "—")),
            ]))
            if bic.get("note"):
                A(bic["note"] + "\n")
            mix = bic.get("composition")
            if isinstance(mix, dict) and mix:
                rows = []
                for name, share in sorted(mix.items(), key=lambda kv: -float(kv[1] or 0))[:8]:
                    try:
                        rows.append((name, f"{float(share) * 100:.1f}%"))
                    except (TypeError, ValueError):
                        rows.append((name, str(share)))
                A(_kv_table(rows))
                A("")

        orgs = [o for o in (bio.get("organisms") or []) if isinstance(o, dict)]
        if orgs:
            A(_h(3, "物种与可操控性"))
            A("| 物种 | 营养级 | 体高 / 体长 | 质量 | 速度 | 第一人称 |")
            A("|---|---|---|---|---|---|")
            for o in orgs:
                loco = o.get("locomotion") or {}
                eye = ""
                if o.get("playable"):
                    eye = f"可操控（眼高 {float(o.get('height_m', 0)) * 0.92:.2f} m）"
                else:
                    eye = "不可操控"
                A(f"| {o.get('name', '—')} | {o.get('role', '—')} | "
                  f"{o.get('height_m', '—')} / {o.get('length_m', '—')} m | "
                  f"{o.get('mass_kg', '—')} kg | {loco.get('speed_ms', '—')} m/s | {eye} |")
            A("")
            for o in orgs:
                if not o.get("playable"):
                    continue
                s = o.get("senses") or {}
                A(f"- **{o.get('name')}** 的感官：视觉 {s.get('vision', '—')}；"
                  f"听觉 {s.get('hearing', '—')}；嗅觉 {s.get('smell', '—')}")
            A("")
        ps = bio.get("photosynthesis")
        if isinstance(ps, dict):
            A(f"**光合**：色素「{ps.get('pigment', '—')}」，吸收 "
              + "、".join(ps.get("absorbs") or []) + f"；观感：{ps.get('appearance', '—')}\n")
        tls = bio.get("trophic_levels") or []
        if tls:
            A(_h(3, "生态金字塔"))
            for t in tls:
                if not isinstance(t, dict):
                    continue
                A(f"- **{t.get('name')}** {t.get('share')}："
                  + "、".join(t.get("examples") or []))
            A("")
        st = bio.get("sentient") or {}
        if st.get("exists"):
            A(f"**智慧生命**：{st.get('name', '—')} —— {st.get('note', '')}\n")
        if bio.get("mass_extinctions"):
            A("**大灭绝**：" + "；".join(bio["mass_extinctions"]) + "\n")

    # 七、文明
    if civ and civ.get("exists"):
        A(_h(2, "七 · 文明"))
        A(_kv_table([
            ("名称", civ.get("name", "—")),
            ("技术路径", civ.get("tech_path", "—")),
            ("计时", civ.get("timekeeping", "—")),
            ("能源", civ.get("energy_source", "—")),
            ("社会", civ.get("social_shape", "—")),
            ("禁忌", civ.get("taboo", "—")),
        ]))

    # 八、行星地图
    A(_h(2, "八 · 行星地图"))
    b0 = next((b for b in (cos.get("bodies") or [])
               if isinstance(b, dict) and isinstance(b.get("planet_map"), dict)), None)
    if b0:
        pm = b0.get("planet_map") or {}
        st = pm.get("summary") if isinstance(pm.get("summary"), dict) else {}
        if st:
            A(_kv_table([
                ("海洋 / 陆地", f"{st.get('ocean_fraction', 0) * 100:.1f}% / "
                              f"{st.get('land_fraction', 0) * 100:.1f}%"),
                ("海平面", f"{pm.get('sea_level_km', '—')} km ｜ 水量 "
                          f"{ws._num(pm.get('inventory_km3'), 0):.2e} km³"),
                ("最高峰 / 最深海", f"{st.get('max_elevation_km', '—')} km / "
                                  f"{st.get('max_ocean_depth_km', '—')} km"),
                ("均温 / 年降水", f"{st.get('mean_temperature_k', '—')} K / "
                                f"{st.get('mean_precip_mm', '—')} mm"),
                ("河流 / 湖泊", f"{st.get('river_cells', '—')} 格 / "
                              f"{st.get('lake_fraction', 0) * 100:.1f}% 面积"),
                ("宜居度", f"均值 {st.get('habitat_mean', '—')} ｜ "
                          f"中位 {st.get('habitat_p50', '—')}"),
                ("构造", f"{st.get('plates', '—')} 块板 ｜ 汇聚 "
                        f"{st.get('convergent_cells', '—')} ｜ 张裂 "
                        f"{st.get('divergent_cells', '—')} ｜ 热点 "
                        f"{st.get('hotspot_cells', '—')}"),
            ], ("项", "推演结果")))
            A("**推演链**：板块 → 盆地 → 水量定海平面 → 年辐照定温度 → "
              "风带与迎风坡定降水 → 洼地填充定河网 → 高程带 × 湿度定群系。"
              f" 摘要哈希 `{pm.get('hash', '—')}`（同 seed 可复算）。\n")
            checks = pm.get("checks") or []
            if checks:
                A("**地图体检**：" + "；".join(
                    f"{'✓' if c.get('ok') else '!'} {c.get('id')} {c.get('note')}"
                    for c in checks if isinstance(c, dict)) + "\n")
            figs = [f for f in (pm.get("figures") or [])
                    if isinstance(f, str) and os.path.exists(os.path.join(base_dir, f))]
            if figs:
                caps = {
                    "map-elevation.png": "高程与海平面 · 晕渲 + 海岸线 + 河网",
                    "map-biome.png": "群系 · 世界自己声明的生物群系 + 极冰 + 河网",
                    "map-temperature.png": "年平均温度 · 年辐照、温室与海拔递减",
                    "map-precipitation.png": "年降水量 · 风带、海陆分布与雨影",
                    "map-tectonics.png": "构造 · 板块、汇聚/张裂/转换边界与热点",
                    "map-habitat.png": "宜居度 · 温度、溶剂、光照、海拔的乘积",
                    "map-relief.png": "晕渲地形 · 不带群系色的纯地貌",
                    "map-globe.png": "正射球面 · 从太空看这颗行星",
                }
                for f in figs:
                    fn = os.path.basename(f)
                    cap = caps.get(fn, fn)
                    try:
                        rel = os.path.relpath(os.path.join(base_dir, f), md_dir)
                    except ValueError:
                        rel = os.path.join(base_dir, f)
                    A(f"![{cap}]({rel.replace(os.sep, '/')})")
                    A("")
                    A(f"*{cap}*")
                    A("")
        else:
            A("尚未生成行星地图。运行 "
              f"`pangu.py map \"{path}\" --run --write --yes` 后重跑 export。\n")
    else:
        A("尚未生成行星地图。运行 "
          f"`pangu.py map \"{path}\" --run --write --yes` 后重跑 export。\n")

    # 九、历史
    eras = hist.get("eras") or []
    if eras:
        A(_h(2, "九 · 历史"))
        for e in eras:
            if not isinstance(e, dict):
                continue
            A(f"- **{e.get('name')}**（{e.get('span', '—')}）{e.get('summary', '')}")
        A("")

    # 十、审查
    A(_h(2, "十 · 自洽性审查"))
    A(f"**{rep.score}/100**（{rep.grade}）｜ fatal {rep.fatal} ｜ warn {rep.warn}")
    A("")
    wd = d.get("weirdness") or {}
    if wd:
        lo, hi = wd.get("band", (40, 70))
        A(f"反常识度 **{wd.get('score')}/100**（推荐区间 {lo}–{hi}，当前判定：{wd.get('label')}）")
        if wd.get("items"):
            rows = [(i["name"], f"{i['points']:g}", i["detail"]) for i in wd["items"]]
            A(_kv_table(rows, ("偏离维度", "分值", "具体改动")))
        A("")
    rows = [(c.id, ws.DIM_CN.get(c.dim, c.dim), c.question,
             {"pass": "✓", "warn": "!", "fatal": "✗", "skip": "·"}[c.verdict], c.note)
            for c in rep.checks if c.verdict in ("warn", "fatal")]
    if rows:
        A(_kv_table(rows, ("ID", "维度", "检查项", "判定", "说明")))
    else:
        A("全部通过。\n")

    if d.get("bodies"):
        A(_h(3, "派生量核算"))
        rows = [(b["name"], f"{b['radius_earth']} R⊕", f"{b['mass_earth']} M⊕",
                 f"{b['density_gcc_calc']} g/cc", f"{b['gravity_g_calc']} g",
                 f"{b['v_escape_km_s']} km/s", f"{b['t_eq_k']} K")
                for b in d["bodies"]]
        A(_kv_table(rows, ("天体", "半径", "质量", "密度", "重力", "逃逸速度", "平衡温度")))
        A(f"G'/G = {d.get('g_ratio')} ｜ 总光度 {d.get('total_luminosity')} L☉"
          + (f" ｜ 双星间距 {d['binary_sep_au']} AU" if d.get("binary_sep_au") else ""))
        A("")

    # 十、参考
    refs = seed.get("references") or []
    if refs:
        A(_h(2, "十一 · 灵感来源"))
        for r in refs:
            if not isinstance(r, dict):
                continue
            t = r.get("title", "—")
            if r.get("url"):
                t = f"[{t}]({r['url']})"
            A(f"- {t} —— {r.get('takeaway', '')}")
            if r.get("use"):
                A(f"  - 用在哪里：{r['use']}")
        A("")

    # 十一、图版（只引用确实存在的文件，缺图不留坏链）
    plates = [
        ("surface.png", "地面视角 · 站在地表抬头，两颗太阳各走各的方位角与高度角"),
        ("evolution.png", "生态演化 · 2D 生态相、密度曲线与天文强迫场（最近 320 步滚动窗口）"),
    ]
    plates = [(fn, cap) for fn, cap in plates
              if os.path.exists(os.path.join(base_dir, fn))]
    if plates:
        A(_h(2, "十二 · 图版"))
        for fn, cap in plates:
            img = os.path.join(base_dir, fn)
            try:
                rel = os.path.relpath(img, md_dir)
            except ValueError:
                # Windows 下跨盘符取不出相对路径，退回绝对路径，别让导出整条挂掉
                rel = img
            A(f"![{cap}]({rel.replace(os.sep, '/')})")
            A("")
            A(f"*{cap}*")
            A("")

    # 名场面
    if nar.get("setpiece"):
        A(_h(2, "名场面"))
        A(nar["setpiece"])
        A("")

    A("---")
    A("*由盘古生成。设定变更请改 world.json 后重跑脚本，勿手改本文。*")

    md = "\n".join(L)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    say(f"✓ 世界档案已生成：{out}  ({len(md) / 1024:.1f} KB)")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rep.as_dict(), f, ensure_ascii=False, indent=2)
        say(f"✓ 审查报告已生成：{args.json_out}")
    return 0


# ════════════════════════════════════════════════════════════════════
# axioms
# ════════════════════════════════════════════════════════════════════

def cmd_axioms(args) -> int:
    lib = ws.axiom_library(ROOT)
    if not lib:
        err("公理库为空或未找到", "确认 references/公理库.md 存在且表格格式正确")
        return 3

    if args.cost_list:
        from collections import Counter
        c = Counter(t for a in lib for t in (a.get("cost_tags") or []))
        say("【代价类型】按「我想让世界付出什么」索引，不是按学科")
        for tag, _ in ws.COST_TAGS:
            say(f"  {tag}  {c.get(tag, 0):>2} 条")
        say("\n用法：axioms --cost 空间 --roll 3")
        return 0

    pool = lib
    if args.domain:
        pool = [a for a in lib if a["domain"] == args.domain or a["domain_cn"] == args.domain]
        if not pool:
            err(f"未知领域：{args.domain}",
                "可选：" + "、".join(sorted({a['domain'] for a in lib})))
            return 2
    if args.cost:
        hit = [a for a in pool if args.cost in (a.get("cost_tags") or [])]
        if not hit:  # 宽松回退：标签没命中就搜正文
            hit = [a for a in pool
                   if args.cost in (a["name"] + a["setting"] + a["cost"] + a["trace"])]
        if not hit:
            err(f"没有代价类型「{args.cost}」的积木",
                "可选：" + "、".join(t for t, _ in ws.COST_TAGS))
            return 2
        pool = hit
    if args.roll:
        pool = random.sample(pool, min(args.roll, len(pool)))

    if args.json:
        say(json.dumps(pool, ensure_ascii=False, indent=2))
        return 0

    cur = None
    for a in pool:
        if a["domain_cn"] != cur:
            cur = a["domain_cn"]
            say(f"\n【{cur}】")
        tags = "/".join(a.get("cost_tags") or []) or "—"
        say(f"  {a['id']}  {a['name']}  [{a['scale']}]  代价类型：{tags}")
        say(f"       设定：{a['setting']}")
        say(f"       代价：{a['cost']}")
        say(f"       痕迹：{a['trace']}")
    say(f"\n共 {len(pool)} 条。捡起积木时记得付账。")
    return 0


# ════════════════════════════════════════════════════════════════════
# patch / sweep / diff（1.1.2 调参层）
# ════════════════════════════════════════════════════════════════════

def _fmtv(v, width: int = 0) -> str:
    """CLI 展示用的紧凑值格式。"""
    if isinstance(v, bool) or v is None:
        s = json.dumps(v, ensure_ascii=False)
    elif isinstance(v, (int, float)):
        s = f"{v:.4g}" if (v and (abs(v) < 1e-4 or abs(v) >= 1e6)) else f"{v:g}"
    elif isinstance(v, (dict, list)):
        s = f"<{type(v).__name__} {len(v)}>"
    else:
        s = str(v)
        if len(s) > 60:
            s = s[:60] + "…"
    return s.rjust(width) if width else s


def cmd_patch(args) -> int:
    path = args.world
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "检查路径，或先用 init 生成骨架")
        return 2
    try:
        world = ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查第 " + str(e.lineno) + " 行附近")
        return 2

    # ── 查 ────────────────────────────────────────────────────────
    if args.get:
        bad = 0
        for p in args.get:
            ok, val, why = ws.resolve_path(world, p)
            if ok:
                say(f"{p} = {json.dumps(val, ensure_ascii=False)}")
            else:
                say(f"{p} → ✗ {why}")
                bad += 1
        return 2 if bad else 0

    if not args.set:
        err("没有改动", '用 --set "physics.constants[0].world_value=4.0e-11"；查值用 --get')
        return 2

    before = ws.validate(copy.deepcopy(world))
    res = wt.apply_patches(world, args.set, create=args.create, note=args.note or "",
                           bump=not args.no_bump, version=args.version)
    if not res["ok"]:
        err(res["error"], "路径示例：cosmology.bodies[0].mass_earth；加 --create 可新建字段")
        return 2

    after = ws.validate(copy.deepcopy(world))
    written = not args.dry_run
    if written:
        _save_world(path, world)

    if args.json:
        say(json.dumps({
            "ok": True, "written": written,
            "version": (world.get("meta") or {}).get("version"),
            "changes": res["changes"],
            "before": {"score": before.score, "fatal": before.fatal, "warn": before.warn},
            "after": {"score": after.score, "fatal": after.fatal, "warn": after.warn},
        }, ensure_ascii=False, indent=2))
        return 1 if (args.strict and after.fatal) else 0

    for c in res["changes"]:
        mark = "改" if c.get("existed") else "增"
        say(f"  [{mark}] {c['path']}: {_fmtv(c['old'])} → {_fmtv(c['new'])}")
        if (isinstance(c["old"], str) and isinstance(c["new"], (int, float))
                and re.search(r"[A-Za-z]", c["old"])):
            warn(f"{c['path']} 原是带单位的字符串，现在写成了纯数字——确认下游仍能解析")
    if res.get("revision"):
        say(f"  版本 → {res['revision']['version']}，修订记录已追加"
            f"（{len((world.get('history') or {}).get('revisions') or [])} 条）")
    say(f"  评分 {before.score} → {after.score}"
        f" ｜ fatal {before.fatal} → {after.fatal}"
        f" ｜ warn {before.warn} → {after.warn}")
    if after.fatal > before.fatal:
        warn("新增了致命项——这个世界现在还不可交付")
    if any(str(c["path"]).startswith(("cosmology", "physics")) for c in res["changes"]):
        say("  下游：preview / export 需重跑"
            + ("；地图与 CA 粗场也可能受影响"
               if any(re.search(r"radius|albedo|orbit|greenhouse|biomes", str(c["path"]))
                      for c in res["changes"]) else ""))

    say(f"✓ 已写入 {path}" if written else "  --dry-run：未写盘")
    return 1 if (args.strict and after.fatal) else 0


def cmd_sweep(args) -> int:
    path = args.world
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "检查路径")
        return 2
    try:
        world = ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查 JSON 语法")
        return 2

    if args.list:
        targets = wt.scan_targets(world)
        say("【可扫描参数】改一个值，看世界怎么变")
        for t in targets:
            say(f"  {t['path']:<42} {t['label']:<16} 当前 {_fmtv(t['value'])}")
        say(f"\n共 {len(targets)} 个。用法：sweep <world> --param <路径> --percent 20 --steps 7")
        return 0

    if not args.param:
        err("缺少 --param", '先跑 sweep <world> --list 看有哪些参数可扫')
        return 2

    ok, cur, why = ws.resolve_path(world, args.param)
    if not ok:
        err(f"路径不可解析：{args.param}（{why}）", "sweep <world> --list 列出可用路径")
        return 2
    cur_num = ws._parse_first(cur)
    if cur_num is None:
        err(f"该字段不是数值：{args.param} = {_fmtv(cur)}", "只有数值参数能扫")
        return 2

    lo = ws._parse_first(args.from_) if args.from_ else None
    hi = ws._parse_first(args.to) if args.to else None
    if lo is None and hi is None and args.percent is None:
        args.percent = 20.0
    if args.percent is not None and lo is None and hi is None:
        lo, hi = cur_num * (1 - args.percent / 100.0), cur_num * (1 + args.percent / 100.0)

    values = wt.sweep_values(cur_num, lo, hi, args.steps)
    result = wt.sweep_world(world, args.param, values, body_index=args.body,
                            recalc=bool(args.recalc))
    if not result["ok"]:
        err(result["error"], "检查路径")
        return 2

    if args.json:
        say(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    base = result["baseline"]
    say(f"【敏感度扫描】{args.param}")
    say(f"  当前值 {_fmtv(cur_num)} ｜ 基线 评分 {base['score']} ｜ fatal {base['fatal']} ｜ warn {base['warn']}"
        + (" ｜ 每步重算密度/重力" if result.get("recalc") else ""))
    say("")
    say(f"  {'值':>12}  {'g':>6}  {'T_surf':>9}  {'v_esc':>7}  {'评分':>4}  {'fatal':>5}  判定")
    for r in result["rows"]:
        mark = "✗ 崩" if r["broken"] else "✓ 可存续"
        extra = ""
        if r["broken"] and r["fatal_ids"]:
            extra = "（" + "、".join(r["fatal_ids"][:3]) + "）"
        star = " ←" if result.get("critical") and r["value"] == result["critical"]["value"] else ""
        say(f"  {_fmtv(r['value']):>12}  {_fmtv(r.get('gravity_g') or 0, 6)}  "
            f"{_fmtv(r.get('t_surface_k') or 0, 9)}  {_fmtv(r.get('v_escape_km_s') or 0, 7)}  "
            f"{r['score']:>4}  {r['fatal']:>5}  {mark}{extra}{star}")

    say("")
    if result.get("critical"):
        c = result["critical"]
        say(f"  崩点：{args.param} = {_fmtv(c['value'])}"
            f"（评分 {c['score']}，fatal {c['fatal']}）——临界点本身就是设定素材")
    else:
        say("  全区间未崩：这个参数不是这个世界的死穴，换一个扫。")
    if result.get("safe_window"):
        lo, hi = result["safe_window"]
        say(f"  安全窗：{_fmtv(lo)} … {_fmtv(hi)}")
    return 0


def cmd_diff(args) -> int:
    worlds = []
    for p in (args.a, args.b):
        if not os.path.exists(p):
            err(f"文件不存在：{p}", "检查路径")
            return 2
        try:
            worlds.append(ws.load(p))
        except json.JSONDecodeError as e:
            err(f"JSON 解析失败：{p}（{e}）", "检查 JSON 语法")
            return 2

    res = wt.diff_worlds(worlds[0], worlds[1], limit=args.limit)
    if args.json:
        say(json.dumps(res, ensure_ascii=False, indent=2))
        return 1 if (args.strict and res["new_fatal"]) else 0

    va = res["version"].get("from") or "—"
    vb = res["version"].get("to") or "—"
    say(f"【世界版本对比】{va} → {vb}")
    say(f"  改动 {len(res['changes'])} 处 ｜ 新增 {len(res['added'])} 处 ｜ 删除 {len(res['removed'])} 处"
        + ("（已达上限，用 --limit 放大）" if res["truncated"] else ""))
    say("")
    for c in res["changes"]:
        say(f"  ~ {c['path']}")
        say(f"      {_fmtv(c['old'])} → {_fmtv(c['new'])}")
    for a in res["added"]:
        say(f"  + {a['path']} = {_fmtv(a['new'])}")
    for r in res["removed"]:
        say(f"  - {r['path']}（原 {_fmtv(r['old'])}）")

    if res["derived"]:
        say("")
        say("【派生量】")
        for d in res["derived"]:
            say(f"  {d['label']}：{_fmtv(d['from'])} → {_fmtv(d['to'])}")

    if res["new_fatal"] or res["fixed"] or res["new_warn"]:
        say("")
        say("【审查变化】")
        if res["new_fatal"]:
            say("  ✗ 新增致命项：" + "、".join(res["new_fatal"]))
        if res["fixed"]:
            say("  ✓ 已解除：" + "、".join(res["fixed"]))
        if res["new_warn"]:
            say("  ! 新增告警：" + "、".join(res["new_warn"]))

    say("")
    say("【需要重跑】")
    for t in res["downstream"]:
        say(f"  {t['task']:<8} {t['cmd']}")
        say(f"           └ {t['why']}")
    return 1 if (args.strict and res["new_fatal"]) else 0


# ════════════════════════════════════════════════════════════════════
# slice
# ════════════════════════════════════════════════════════════════════

def _load_or_fail(path: str):
    if not os.path.exists(path):
        err(f"文件不存在：{path}", "检查路径，或先用 init 生成骨架")
        return None
    try:
        return ws.load(path)
    except json.JSONDecodeError as e:
        err(f"JSON 解析失败：{e}", "检查 JSON 语法（多余逗号 / 中文引号）")
        return None


def cmd_slice(args) -> int:
    world = _load_or_fail(args.world)
    if world is None:
        return 2

    rep = ws.validate(world, strict=bool(args.strict))
    by_id = {c.id: c for c in rep.checks}
    sl = ws._get(world, "narrative", "slice", default=None)

    say("切片体检（第一人称 · 两百字验尸）")
    say("-" * 52)
    if not isinstance(sl, dict) or not str(sl.get("text") or "").strip():
        say("  ✗ 未定义 narrative.slice.text")
        say("   → 按 references/七斧创世法.md 第 7 斧写一段 180–260 字的「居民的一天」，")
        say("     附 cites（引用字段）、hours（时间范围）、status: ok")
        return 1 if args.strict else 0

    text = str(sl.get("text") or "")
    n = ws._count_cjk(text)
    ok_n = 180 <= n <= 260
    say(f"  字数   {n} / 180–260   {'✓' if ok_n else '✗ 超出'}")
    say(f"  定稿   status={sl.get('status', 'draft')}"
        f"   {'✓' if str(sl.get('status') or '') == 'ok' else '✗ 交付需 ok'}")

    for cid, label in (("N04", "引用"), ("N05", "现象"), ("N06", "时序")):
        c = by_id.get(cid)
        if c is None:
            continue
        ok = c.verdict in ("pass", "skip")
        say(f"  {label}   {c.note}   {'✓' if ok else '✗'}")

    bad = [c for c in rep.checks if c.id in ("N03", "N04", "N05", "N06")
           and c.verdict in ("warn", "fatal")]
    say("-" * 52)
    if bad:
        say(f"  结论：不可交付（{len(bad)} 项待修）")
        if args.strict:
            return 1
    else:
        say("  结论：可交付")
    return 0


# ════════════════════════════════════════════════════════════════════
# redteam
# ════════════════════════════════════════════════════════════════════

def _rt_candidates(world: dict) -> list:
    """
    按模板库轮询出质疑。每条必须挂到 world.json 里真实存在的字段——
    这是红队与「空口挑刺」的分界线。
    """
    d = ws.compute_derived(world)
    cos = world.get("cosmology") or {}
    bio = world.get("biology") or {}
    phys = world.get("physics") or {}
    chem = world.get("chemistry") or {}
    math_ = world.get("mathematics") or {}
    cal = cos.get("calendar") or {}
    sky = cos.get("sky_phenomena") or []
    bodies = d.get("bodies") or []
    main = bodies[0] if bodies else None
    tls = bio.get("trophic_levels") or []
    m = world.get("meta") or {}

    out = []

    def push(template: str, q: str, target: str) -> None:
        if ws.resolve_path(world, target)[0]:
            out.append({"template": template, "q": q, "target": target})

    if main:
        push("数量级",
             f"表面重力 {main['gravity_g_calc']} g、半径 {main['radius_earth']} R⊕、"
             f"密度 {main['density_gcc_calc']} g/cc，地壳屈服强度撑得住这个密度差吗？给一个数量级。",
             "cosmology.bodies[0].gravity_g")
        push("边界条件",
             f"逃逸速度 {main['v_escape_km_s']} km/s，表面温度 {main['t_surface_k']} K——"
             f"这个组合下，大气在亿年尺度上留得住吗？光致逃逸通量是多少？",
             "cosmology.bodies[0].mass_earth")
        push("能量收支",
             f"系统总光度 {d.get('total_luminosity')} L☉ 摊到 {main['mass_earth']} M⊕，"
             f"初级生产者份额 {tls[0].get('share') if tls else '—'}，"
             f"这条能量预算能撑住 {len(tls)} 层消费者吗？",
             "biology.trophic_levels[0].share" if tls else "biology.trophic_levels")

    if sky:
        push("观测一致性",
             f"「{str(sky[0])[:40]}…」从地面怎么观测？观测时刻表能不能提前预报？"
             f"历法月长 {cal.get('month_days', '—')} 天，对得上吗？",
             "cosmology.calendar.month_days")
        if len(sky) > 1:
            push("观测一致性",
                 f"「{str(sky[1])[:40]}…」在 {cal.get('day_hours', '—')} 小时的一天里，"
                 f"居民什么时候能看到它？看不到的那部分时间，设定靠什么成立？",
                 "cosmology.sky_phenomena")

    if cal and cal.get("year_days"):
        push("边界条件",
             f"一年 {cal.get('year_days')} 天、一天 {cal.get('day_hours')} 小时，"
             f"这个组合下季节长度是多少？你的生态周期跟得上吗？",
             "cosmology.calendar.year_days")

    consts = phys.get("constants") or []
    if consts:
        c0 = consts[0] if isinstance(consts[0], dict) else {}
        push("反例",
             f"你把「{c0.get('symbol', '某常数')}」改成了 {c0.get('world_value', '—')}"
             f"（{c0.get('delta', '—')}），但推导里用的是地球数值——"
             f"这个改动不影响后面的天体结构结论吗？",
             "physics.constants[0].world_value")

    if chem:
        mats = chem.get("signature_materials") or []
        if mats and isinstance(mats[0], dict):
            push("反例",
                 f"「{mats[0].get('name')}」的成因是 {mats[0].get('property', '')[:40]}——"
                 f"这条机制在你的物理常数下还有足够的驱动力吗？",
                 "chemistry.signature_materials[0].property")
        if chem.get("abiotic_notes"):
            push("能量收支",
                 f"你说 {str(chem.get('abiotic_notes'))[:40]}…，"
                 f"这股能量的通量有多大？够养活一整条食物链吗？",
                 "chemistry.abiotic_notes")

    if math_ and math_.get("peculiarity"):
        push("反例",
             f"「{str(math_['peculiarity'])[:40]}」——这个数学异常是你设定的，"
             f"但它在你的物理常数下还成立吗？给出推导。",
             "mathematics.peculiarity")

    if bio.get("energy_currency"):
        push("能量收支",
             f"能量货币是「{(bio.get('energy_currency') or {}).get('name', '—')}」，"
             f"转换效率有限——每层营养级的实际可用功率是多少？够维持智慧生命的脑吗？",
             "biology.energy_currency.name")

    if (bio.get("sentient") or {}).get("exists"):
        push("边界条件",
             f"智慧种族「{(bio.get('sentient') or {}).get('name', '—')}」在 "
             f"{main['gravity_g_calc'] if main else '—'} g 下生存，"
             f"神经传导与骨骼强度的代价写在哪里了？",
             "biology.sentient.note")

    return out


def cmd_redteam(args) -> int:
    world = _load_or_fail(args.world)
    if world is None:
        return 2
    con = world.get("consistency")
    if not isinstance(con, dict):
        con = {}
        world["consistency"] = con
    existing = con.get("redteam")
    if not isinstance(existing, list):
        existing = []

    # ── 模式 1：体检 ────────────────────────────────────────────────
    if args.check:
        rep = ws.validate(world, strict=False)
        n07 = next((c for c in rep.checks if c.id == "N07"), None)
        n08 = next((c for c in rep.checks if c.id == "N08"), None)
        opens = [r for r in existing
                 if isinstance(r, dict) and str(r.get("verdict") or "open") == "open"]
        resolvable = 0
        for r in existing:
            if isinstance(r, dict) and ws.resolve_path(world, r.get("target"))[0]:
                resolvable += 1
        say("红队体检")
        say("-" * 52)
        say(f"  质疑条数   {len(existing)}" + ("" if len(existing) >= 5 else "  ！建议 ≥5"))
        say(f"  靶点可解析 {resolvable} / {len(existing)}")
        say(f"  未结案     {len(opens)}" + ("" if not opens else
                                            "  ✗ " + "、".join(str(r.get("id")) for r in opens[:4])))
        say("-" * 52)
        if n07:
            say(f"  N07  {n07.verdict}  {n07.note}")
        if n08:
            say(f"  N08  {n08.verdict}  {n08.note}")
        if opens:
            say("  结论：不可交付（仍有 open）")
            return 1 if args.strict else 0
        if len(existing) < 5 or resolvable < len(existing):
            say("  结论：待加强")
            return 0
        say("  结论：可交付")
        return 0

    # ── 模式 2：回写回应 ────────────────────────────────────────────
    if args.answer:
        rid, _, verdict = args.answer.partition("=")
        rid = rid.strip()
        verdict = (verdict or "answered").strip()
        if verdict not in ("open", "answered", "accepted", "rejected"):
            err(f"未知结论「{verdict}」", "可选：open / answered / accepted / rejected")
            return 2
        text = args.text or ""
        if args.text_file:
            with open(args.text_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
        hit = None
        for r in existing:
            if isinstance(r, dict) and r.get("id") == rid:
                hit = r
                break
        if hit is None:
            err(f"没有 id={rid} 的质疑", "先跑 --count 生成，或检查 id")
            return 2
        hit["verdict"] = verdict
        if text:
            hit["answer"] = text
        if args.fix:
            fpath, _, fval = args.fix.partition("=")
            if ws.resolve_path(world, fpath.strip())[0]:
                hit["fix"] = args.fix.strip()
            else:
                warn(f"fix 目标「{fpath}」在 world.json 里不存在，已忽略")
        _save_world(args.world, world)
        say(f"✓ {rid} → {verdict}，已写回 {args.world}")
        return 0

    # ── 模式 3：生成质疑 ────────────────────────────────────────────
    cands = _rt_candidates(world)
    if not cands:
        err("这个世界没有可攻击的具体字段", "先补齐 cosmology / physics / biology，红队才有靶子")
        return 2
    have = {r.get("target") for r in existing if isinstance(r, dict)}
    pool = [c for c in cands if c["target"] not in have] or cands
    want = max(1, int(args.count or 5))
    picked = []
    i = 0
    while len(picked) < want:
        picked.append(pool[i % len(pool)])
        i += 1
        if i > want * 3:
            break

    base = len(existing)
    made = []
    for k, c in enumerate(picked):
        made.append({
            "id": f"RT{base + k + 1:02d}",
            "q": c["q"],
            "target": c["target"],
            "template": c["template"],
            "verdict": "open",
            "answer": "",
        })

    if args.write:
        con["redteam"] = existing + made
        _save_world(args.world, world)
        say(f"✓ 已生成 {len(made)} 条质疑并写入 {args.world}")
    if args.format == "json":
        say(json.dumps(made, ensure_ascii=False, indent=2))
    else:
        say(f"红队 · {len(made)} 条质疑（只攻击，不给方案）")
        say("-" * 52)
        for m in made:
            say(f"  [{m['id']}] {m['q']}")
            say(f"        打：{m['target']}  （模板：{m['template']}）")
        say("-" * 52)
        say("  回应方法：")
        say(f"    pangu.py redteam {args.world} --answer RT01=answered --text-file reply.txt --fix \"字段=新值\"")
    return 0


def _save_world(path: str, world: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(world, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════════
# map
# ════════════════════════════════════════════════════════════════════

def _parse_wh(s, default):
    if not s:
        return default
    m = re.match(r"^\s*(\d+)\s*[x×]\s*(\d+)\s*$", str(s))
    if not m:
        return default
    return int(m.group(1)), int(m.group(2))


def cmd_map(args) -> int:
    world = _load_or_fail(args.world)
    if world is None:
        return 2
    try:
        import mapgen
    except Exception as e:  # noqa: BLE001
        err(f"地图引擎加载失败：{e}")
        return 3

    res = _parse_wh(args.res, mapgen.DEFAULT_RES)
    render = _parse_wh(args.render, mapgen.RENDER_RES)

    if args.check:
        say("盘古 · 行星地图复算体检")
        say("-" * 56)
        got = mapgen.check(world, res=res, seed=args.seed)
        say(f"  同 seed 复算：{got['hash_a']} / {got['hash_b']}")
        for c in got["checks"]:
            say(f"  {'✓' if c['ok'] else '✗'} {c['id']} {c['note']}")
        if got["diffs"]:
            for d in got["diffs"]:
                say(f"  ✗ {d}")
        say("-" * 56)
        say("  结论：地图可复算。" if got["ok"] else "  结论：复算不一致，必须重跑后再交付。")
        return 0 if got["ok"] else 1

    r = mapgen.build(world, res=res, seed=args.seed)
    st = r.stats
    say("盘古 · 行星地图推演")
    say("-" * 56)
    say(f"  网格 {r.nx}×{r.ny} ｜ 半径 {r.radius_km:.0f} km ｜ "
        f"{'潮汐锁定' if r.meta['tidal_locked'] else '自转'} ｜ 板块 {r.meta['plates']}")
    say(f"  海平面 {r.sea_level:.2f} km（水量 {r.meta['inventory_km3']:.2e} km³）")
    say(f"  海洋 {st['ocean_fraction']:.1%} ｜ 陆地 {st['land_fraction']:.1%} ｜ "
        f"冰 {st['ice_fraction']:.1%}")
    say(f"  最高峰 {st['max_elevation_km']:.2f} km ｜ 最深海 {st['max_ocean_depth_km']:.2f} km ｜ "
        f"陆均温 {st['mean_land_temperature_k']:.0f} K")
    say(f"  年降水 {st['mean_precip_mm']:.0f} mm ｜ 河流格 {st['river_cells']} ｜ "
        f"宜居度 {st['habitat_mean']:.2f}")
    say(f"  构造：汇聚 {st['convergent_cells']} ｜ 张裂 {st['divergent_cells']} ｜ "
        f"转换 {st['transform_cells']} ｜ 热点 {st['hotspot_cells']}")
    for c in r.checks:
        if not c["ok"]:
            warn(f"{c['id']} {c['note']}")
    say("-" * 56)

    if not (args.run or args.write):
        say("  只做了推演。加 --run 出图与交互页，--write 回写摘要，--check 复算。")
        return 0

    wid = str(ws._get(world, "meta", "id", default="world"))
    world_dir = os.path.dirname(os.path.abspath(args.world))
    outdir = args.out or os.path.join(world_dir, "map")
    info = None
    if args.run:
        info = mapgen.write_outputs(r, outdir, render=render)
        say(f"✓ 图已出到 {outdir}")
        for fn in info["figures"]:
            say(f"    {fn}")
        if info.get("html"):
            say(f"    map.html（双击打开，可切图层、悬停读数）")

    if args.write:
        if not args.yes:
            err("回写地图摘要需要显式确认", "加 --yes")
            return 2
        body = mapgen.main_body(world)
        pm = body.get("planet_map") if isinstance(body.get("planet_map"), dict) else {}
        pm["seed"] = r.meta["seed"]
        pm["summary"] = st
        pm["checks"] = r.checks
        pm["hash"] = r.hash
        pm["generated"] = _dt.date.today().isoformat()
        pm["generator"] = f"mapgen/{mapgen.MAP_VERSION}"
        for k in ("res", "sea_level_km", "relief_total_km", "inventory_km3",
                  "mean_depth_target_km", "mean_precip_target_mm", "t_mean_k",
                  "tidal_locked", "plates", "hotspots"):
            if k in r.meta:
                pm[k] = r.meta[k]
        try:
            rel_dir = os.path.relpath(outdir, world_dir).replace(os.sep, "/")
        except ValueError:
            rel_dir = outdir.replace(os.sep, "/")
        figs = []
        for fn in (info["figures"] if info else ["map-" + k + ".png" for k, _ in mapgen.LAYERS]):
            figs.append(fn if rel_dir in ("", ".") else f"{rel_dir}/{fn}")
        pm["figures"] = figs
        pm["coarse"] = mapgen.coarse_fields(r)
        body["planet_map"] = pm
        _save_world(args.world, world)
        say(f"✓ 地图摘要与粗粒度场已写回 {args.world}")
        say("  （summary 是真跑出来的；换 seed / 换水量后必须重跑 --write）")
    return 0


# ════════════════════════════════════════════════════════════════════
# ca
# ════════════════════════════════════════════════════════════════════

def cmd_ca(args) -> int:
    world = _load_or_fail(args.world)
    if world is None:
        return 2
    evo = ws._get(world, "biology", "evolution", default=None)
    if not isinstance(evo, dict):
        err("world.json 里没有 biology.evolution",
            "先按该世界的设定声明 states / rules / forcing，再编译")
        return 2

    try:
        import ca_engine as ca
        import png_writer as pw
    except Exception as e:  # noqa: BLE001
        err(f"CA 引擎加载失败：{e}")
        return 3

    prog = ca.compile_evolution(evo, world)

    # ── 编译诊断 ────────────────────────────────────────────────────
    say("盘古 · 生态演化模型编译")
    say("-" * 56)
    if prog.errors:
        say(f"  ✗ 编译失败：{len(prog.errors)} 处规则不自洽")
        for e in prog.errors:
            say(f"    · {e}")
        if prog.warnings:
            say(f"  ！另有 {len(prog.warnings)} 条提示")
        say("-" * 56)
        say("  结论：规则互相矛盾，必须重新设计后再跑。")
        say("  （编译不降级、不兜底——配置错误不该被静默吞掉）")
        return 1

    nx, ny = prog.grid["nx"], prog.grid["ny"]
    say(f"  ✓ 编译通过：{len(prog.states)} 态 × {nx}×{ny} 格 "
        f"× {len(prog.rules)} 规则 × {len(prog.forcing)} 强迫项")
    say(f"    拓扑 {prog.grid['topology']}"
        + (" ｜ 面积加权 cos(lat)" if prog.grid.get("area_weighted") else "")
        + f" ｜ 一步 {prog.clock['hours_per_step']:g} 小时"
        + (f" ｜ 地图耦合 {prog.map.get('field')}" if prog.map else ""))
    for s in prog.states:
        say(f"    · {s.id:<10} {s.name:<8} [{s.kind}] 初始 {prog.initial.get(s.index, 0):.0%}"
            + (f"  ← {s.source}" if s.source else ""))
    for f in prog.forcing:
        say(f"    ~ {f.id} {f.name} 周期 {f.period_days:g} 天"
            + (f"  ← {f.source}" if f.source else ""))
    for r in prog.rules:
        tag = " [逆行]" if r.retrograde else ""
        say(f"    → {r.id} {ca._sid(prog, r.src)} → {ca._sid(prog, r.dst)} "
            f"p={r.prob:g}{tag}" + (f"  代价 {r.cost:g}" if r.cost else ""))
    for w in prog.warnings:
        warn(w)
    say("-" * 56)

    if not (args.run or args.check or args.write):
        say("  只做了编译。加 --run 跑演化，--check 复算比对，--write 回写摘要。")
        return 0

    steps = int(args.steps or ws._num(evo.get("steps"), 400))
    seed = int(args.seed if args.seed is not None else ws._num(evo.get("seed"), 7))

    # ── 复算比对 ────────────────────────────────────────────────────
    if args.check:
        res = ca.check_evolution(evo, world, steps=args.steps, seed=args.seed)
        say("复算比对（同 seed 同结果——抄来的数字会被打回）")
        say("-" * 56)
        say(f"  seed={seed}  steps={steps}")
        for k, v in res["actual"].items():
            if isinstance(v, dict):
                continue
            dv = (res["declared"] or {}).get(k, "—")
            say(f"  {k:<18} 声明 {dv} ｜ 复算 {v}")
        if res["diffs"]:
            for d in res["diffs"]:
                say(f"  ✗ {d}")
            say("-" * 56)
            say("  结论：summary 与复算不一致。改参数就重跑 --write，不许手填。")
            return 1
        say("-" * 56)
        say("  结论：一致，summary 是真跑出来的。")
        return 0

    # ── 跑演化 + 出图 ───────────────────────────────────────────────
    if args.run or args.write:
        if args.frames and args.frames >= 2:
            n = min(120, int(args.frames))
            snaps = sorted({int(round(k * steps / (n - 1))) for k in range(n)})
        else:
            snaps = sorted({0, steps // 2, steps})
        stats = ca.run(prog, steps=steps, seed=seed, snapshot_steps=snaps)
        summ = ca.summarize(prog, stats)
        say(f"✓ 跑完 {steps} 步：主状态「{stats.primary}」"
            f" 稳态密度 {summ['steady_density']} ｜ 周期 {summ['cycle_steps']} 步"
            f" ｜ 塌缩概率 {summ['collapse_prob']} ｜ 能量支出 {summ['energy_spent']}")
        say(f"  逐格哈希 {summ['final_hash']} ｜ 最大回撤 {summ['max_drawdown']:.1%}"
            f" ｜ 韧性 {summ['resilience']:.0%}")

        outdir = args.out or os.path.join("out", str(ws._get(world, "meta", "id", default="world")))
        if args.run:
            os.makedirs(outdir, exist_ok=True)
            figs = []
            for k, st in enumerate(snaps):
                got = stats.snapshots.get(st)
                if not got:
                    continue
                cells, scale = got
                w, h, px = ca.render_snapshot(prog, cells, scale)
                fn = f"ca-frame-{k:02d}.png" if args.frames else f"ca-t{st}.png"
                fp = os.path.join(outdir, fn)
                pw.write_rgb(fp, w, h, px)
                figs.append(fp.replace("\\", "/"))
                if not args.frames:
                    say(f"  图 {fp}  ({w}×{h})")
            if figs and (not args.frames or len(figs) <= 12):
                if not isinstance(evo.get("figures"), list):
                    evo["figures"] = []
                for f in figs:
                    if f not in evo["figures"]:
                        evo["figures"].append(f)

        if args.write:
            if not args.yes:
                err("回写 summary 需要显式确认", "加 --yes")
                return 2
            evo["summary"] = {k: v for k, v in summ.items() if k != "state_density"}
            evo["summary"]["state_density"] = summ["state_density"]
            _save_world(args.world, world)
            say(f"✓ summary 已写回 {args.world}（status 仍由你标 ok）")
        return 0
    return 0


# ════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pangu",
        description="盘古 · 开天辟地式造世引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="先立律，后长物。地球不是模板，是一个样本。")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("doctor", help="环境自检")
    d.set_defaults(func=cmd_doctor)

    i = sub.add_parser("init", help="生成骨架 world.json")
    i.add_argument("--name", required=True, help="世界名")
    i.add_argument("--id", help="slug（缺省由名字生成）")
    i.add_argument("--seed", default="", help="一句话种子")
    i.add_argument("--out", help="输出路径")
    i.add_argument("--autonomy", default="auto",
                   choices=["auto", "co-create", "audit"], help="共创模式")
    i.add_argument("--star-count", type=int, default=2, help="恒星数量 1–4")
    i.add_argument("--no-stars", action="store_true", help="无恒星世界")
    i.set_defaults(func=cmd_init)

    v = sub.add_parser("validate", help="校验 + 自洽打分")
    v.add_argument("world")
    v.add_argument("--strict", action="store_true", help="有 fatal 时退出码 1")
    v.add_argument("--json", action="store_true", help="机器可读输出")
    v.add_argument("--fix-hint", action="store_true", help="附修补建议")
    v.set_defaults(func=cmd_validate)

    pr = sub.add_parser("preview", help="生成 3D 预览页")
    pr.add_argument("world")
    pr.add_argument("-o", "--out", help="输出 html 路径")
    pr.add_argument("--title", help="页面标题")
    pr.set_defaults(func=cmd_preview)

    e = sub.add_parser("export", help="生成世界档案 Markdown")
    e.add_argument("world")
    e.add_argument("--md", help="输出 md 路径")
    e.add_argument("--json-out", help="同时输出审查报告 JSON")
    e.set_defaults(func=cmd_export)

    a = sub.add_parser("axioms", help="查公理库")
    a.add_argument("--domain", help="physics|cosmos|math|chemistry|biology|civilization")
    a.add_argument("--cost", help="按代价类型过滤：时间/空间/能量/物质/感知/社会/生命/结构")
    a.add_argument("--cost-list", action="store_true", help="列出代价类型二次索引")
    a.add_argument("--roll", type=int, help="随机抽取 N 条")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_axioms)

    pt = sub.add_parser("patch", help="定点改 / 增 / 查字段（自动升版本与记修订）")
    pt.add_argument("world")
    pt.add_argument("--set", action="append", default=[], metavar="PATH=VALUE",
                    help="写入一个字段，可重复；值先按 JSON 解析，失败当字符串")
    pt.add_argument("--get", action="append", default=[], metavar="PATH",
                    help="查询一个字段，可重复")
    pt.add_argument("--create", action="store_true", help="允许新建不存在的字段 / 追加数组")
    pt.add_argument("--note", help="修订说明，写进 history.revisions[].change")
    pt.add_argument("--version", help="显式指定新版本号（默认补丁位 +1）")
    pt.add_argument("--no-bump", action="store_true", help="不改版本、不记修订")
    pt.add_argument("--dry-run", action="store_true", help="只显示改动，不写盘")
    pt.add_argument("--json", action="store_true", help="机器可读输出")
    pt.add_argument("--strict", action="store_true", help="改完有 fatal 时退出码 1")
    pt.set_defaults(func=cmd_patch)

    sw = sub.add_parser("sweep", help="参数敏感度扫描：沿一个数值找崩点")
    sw.add_argument("world")
    sw.add_argument("--param", help="要扫的点路径，如 physics.constants[0].world_value")
    sw.add_argument("--from", dest="from_", help="起始值（缺省按 --percent）")
    sw.add_argument("--to", help="终止值（缺省按 --percent）")
    sw.add_argument("--percent", type=float, help="以当前值为中心 ±N%%（默认 20）")
    sw.add_argument("--steps", type=int, default=7, help="采样点数 3–31，默认 7")
    sw.add_argument("--body", type=int, default=0, help="看第几个天体的派生量，默认 0")
    sw.add_argument("--recalc", action="store_true",
                    help="每步重算该天体的密度/重力/半径，扫出物理自洽的邻近世界")
    sw.add_argument("--list", action="store_true", help="列出可扫描的数值参数")
    sw.add_argument("--json", action="store_true")
    sw.set_defaults(func=cmd_sweep)

    df = sub.add_parser("diff", help="版本对比：改了什么、哪条被修好、要重跑什么")
    df.add_argument("a", help="旧版 world.json")
    df.add_argument("b", help="新版 world.json")
    df.add_argument("--limit", type=int, default=200, help="最多记录多少处改动")
    df.add_argument("--json", action="store_true")
    df.add_argument("--strict", action="store_true", help="新增 fatal 时退出码 1")
    df.set_defaults(func=cmd_diff)

    sl = sub.add_parser("slice", help="第一人称切片体检")
    sl.add_argument("world")
    sl.add_argument("--check", action="store_true", help="只做机检（默认行为）")
    sl.add_argument("--strict", action="store_true", help="不达标时退出码 1")
    sl.set_defaults(func=cmd_slice)

    rt = sub.add_parser("redteam", help="红队审查：生成质疑 / 回写回应 / 体检")
    rt.add_argument("world")
    rt.add_argument("--count", type=int, default=5, help="生成几条质疑")
    rt.add_argument("--format", choices=["text", "json"], default="text")
    rt.add_argument("--write", action="store_true", help="把新质疑写入 world.json")
    rt.add_argument("--answer", help="RT01=answered|accepted|rejected")
    rt.add_argument("--text", default="", help="回应正文")
    rt.add_argument("--text-file", help="回应正文（从文件读，避免中文参数乱码）")
    rt.add_argument("--fix", help="接受质疑后要改的字段，形如 path=value")
    rt.add_argument("--check", action="store_true", help="体检现有红队")
    rt.add_argument("--strict", action="store_true")
    rt.set_defaults(func=cmd_redteam)

    ca_ = sub.add_parser("ca", help="生态演化：编译 / 跑 / 复算比对")
    ca_.add_argument("world")
    ca_.add_argument("--run", action="store_true", help="跑演化并出快照图")
    ca_.add_argument("--check", action="store_true", help="复算并与 summary 比对")
    ca_.add_argument("--write", action="store_true", help="把复算结果写回 summary")
    ca_.add_argument("--yes", action="store_true", help="确认回写")
    ca_.add_argument("--steps", type=int, help="覆盖步数")
    ca_.add_argument("--frames", type=int, help="出 N 张等距快照（默认 3 张）")
    ca_.add_argument("--seed", type=int, help="覆盖随机种子")
    ca_.add_argument("--out", help="快照图输出目录（默认 out/<世界id>）")
    ca_.set_defaults(func=cmd_ca)

    mp = sub.add_parser("map", help="行星地图：推演 / 出图 / 复算比对")
    mp.add_argument("world")
    mp.add_argument("--run", action="store_true", help="出高程/群系/气候/构造/宜居度图与交互页")
    mp.add_argument("--check", action="store_true", help="同 seed 复算并体检")
    mp.add_argument("--write", action="store_true", help="把摘要与粗粒度场写回 world.json")
    mp.add_argument("--yes", action="store_true", help="确认回写")
    mp.add_argument("--res", help="推演网格，如 480x240（默认 360x180）")
    mp.add_argument("--render", help="出图分辨率，如 1920x960（默认 1440x720）")
    mp.add_argument("--seed", type=int, help="覆盖随机种子")
    mp.add_argument("--out", help="图输出目录（默认 world.json 同级 map/）")
    mp.set_defaults(func=cmd_map)

    return p


def main(argv=None) -> int:
    _init_io()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        err("已中断")
        return 130
    except Exception as e:  # noqa: BLE001
        err(f"内部错误：{type(e).__name__}: {e}", "用 doctor 自检，或把此信息反馈给盘古维护者")
        return 3


if __name__ == "__main__":
    sys.exit(main())
