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
    axioms   [--domain <d>] [--roll N]         查公理库
"""

from __future__ import annotations

import argparse
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
    A(f"`v{meta.get('version', '1.0')}` ｜ {meta.get('created', '')} ｜ "
      f"自洽评分 **{rep.score}/100**（{rep.grade}） ｜ 生成：盘古")
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

    # 八、历史
    eras = hist.get("eras") or []
    if eras:
        A(_h(2, "八 · 历史"))
        for e in eras:
            if not isinstance(e, dict):
                continue
            A(f"- **{e.get('name')}**（{e.get('span', '—')}）{e.get('summary', '')}")
        A("")

    # 九、审查
    A(_h(2, "九 · 自洽性审查"))
    A(f"**{rep.score}/100**（{rep.grade}）｜ fatal {rep.fatal} ｜ warn {rep.warn}")
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
        A(_h(2, "十 · 灵感来源"))
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
        A(_h(2, "十一 · 图版"))
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
    pool = lib
    if args.domain:
        pool = [a for a in lib if a["domain"] == args.domain or a["domain_cn"] == args.domain]
        if not pool:
            err(f"未知领域：{args.domain}",
                "可选：" + "、".join(sorted({a['domain'] for a in lib})))
            return 2
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
        say(f"  {a['id']}  {a['name']}  [{a['scale']}]")
        say(f"       设定：{a['setting']}")
        say(f"       代价：{a['cost']}")
        say(f"       痕迹：{a['trace']}")
    say(f"\n共 {len(pool)} 条。捡起积木时记得付账。")
    return 0


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
    say(f"    拓扑 {prog.grid['topology']} ｜ 一步 "
        f"{prog.clock['hours_per_step']:g} 小时")
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
        snaps = sorted({0, steps // 2, steps})
        stats = ca.run(prog, steps=steps, seed=seed, snapshot_steps=snaps)
        summ = ca.summarize(prog, stats)
        say(f"✓ 跑完 {steps} 步：主状态「{stats.primary}」"
            f" 稳态密度 {summ['steady_density']} ｜ 周期 {summ['cycle_steps']} 步"
            f" ｜ 塌缩概率 {summ['collapse_prob']} ｜ 能量支出 {summ['energy_spent']}")

        outdir = args.out or os.path.join("out", str(ws._get(world, "meta", "id", default="world")))
        if args.run:
            os.makedirs(outdir, exist_ok=True)
            figs = []
            for st in snaps:
                got = stats.snapshots.get(st)
                if not got:
                    continue
                cells, scale = got
                w, h, px = ca.render_snapshot(prog, cells, scale)
                fp = os.path.join(outdir, f"ca-t{st}.png")
                pw.write_rgb(fp, w, h, px)
                figs.append(fp.replace("\\", "/"))
                say(f"  图 {fp}  ({w}×{h})")
            if figs:
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
    a.add_argument("--roll", type=int, help="随机抽取 N 条")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_axioms)

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
    ca_.add_argument("--seed", type=int, help="覆盖随机种子")
    ca_.add_argument("--out", help="快照图输出目录（默认 out/<世界id>）")
    ca_.set_defaults(func=cmd_ca)

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
