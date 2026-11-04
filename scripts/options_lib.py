# -*- coding: utf-8 -*-
"""
盘古 · 选项卡
=============
1.1.3 新增：把 `references/选项卡.md` 解析成可检索的「设定菜单」。

公理库给积木，选项卡给菜单：
  · 公理库是「有哪些反常识可以捡」（横向、跨层、无编号约束）
  · 选项卡是「这一斧必须回答哪些问题、每个问题有哪几种活法」（纵向、按斧分段、互斥）

命令侧只做三件事：列（--axe / --qid）、抽（--roll）、采纳（--adopt → seed.brief.choices）。

格式约定见 `references/选项卡.md` 头部；解析失败的行进 warnings，不影响其他卡。
"""

from __future__ import annotations

import os
import random
import re
from typing import Optional

CARD_FILE = os.path.join("references", "选项卡.md")

_AXE_RE = re.compile(r"^##\s*斧\s*(\d+)\s*[·・]?\s*(.+?)\s*$")
_QID_RE = re.compile(r"^###\s*(Q(\d+)\.(\d+))\s+(.+?)\s*$")
_WHY_RE = re.compile(r"^@why\s+(.+?)\s*$")
_OPT_RE = re.compile(r"^-\s*([A-Z])\s*[｜|]\s*(.+?)\s*$")
_KEY_RE = re.compile(r"^(设定|代价|痕迹|连锁|标签)\s*[：:]\s*(.*)$")

KEYS = ("setting", "cost", "trace", "fields", "tags")
KEY_CN = {"设定": "setting", "代价": "cost", "痕迹": "trace",
          "连锁": "fields", "标签": "tags"}


# ════════════════════════════════════════════════════════════════════
# 解析
# ════════════════════════════════════════════════════════════════════

def _split_weight(text: str) -> str:
    """去掉「3 倍地球大」这类前置权重，只留正文（保留原文，供展示）。"""
    return str(text or "").strip()


def _tokens(text: str) -> list:
    """标签/连锁：按空白、顿号、逗号切，去掉反引号与井号。"""
    parts = re.split(r"[\s、,，;；]+", str(text or ""))
    return [p.strip("`# 　") for p in parts if p.strip("`# 　")]


def parse_cards(text: str) -> tuple:
    """解析选项卡 Markdown，返回 (cards, warnings)。"""
    cards, warns = [], []
    axe, axe_cn = 0, ""
    cur = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            continue

        m = _AXE_RE.match(line)
        if m:
            axe = int(m.group(1))
            axe_cn = m.group(2).strip()
            cur = None
            continue

        m = _QID_RE.match(line)
        if m:
            cur = {
                "qid": m.group(1),
                "axe": int(m.group(2)),
                "no": int(m.group(3)),
                "title": m.group(4).strip(),
                "why": "",
                "axe_cn": axe_cn,
                "options": [],
            }
            cards.append(cur)
            continue

        m = _WHY_RE.match(line)
        if m:
            if cur is None:
                warns.append(f"第 {lineno} 行：@why 出现在命题之前")
            else:
                cur["why"] = m.group(1).strip()
            continue

        m = _OPT_RE.match(line)
        if m:
            if cur is None:
                warns.append(f"第 {lineno} 行：选项出现在命题之前")
                continue
            body = m.group(2)
            fields = {"setting": "", "cost": "", "trace": "", "fields": [], "tags": []}
            unknown = []
            for seg in re.split(r"[｜|]", body):
                seg = seg.strip()
                if not seg:
                    continue
                km = _KEY_RE.match(seg)
                if not km:
                    unknown.append(seg[:16])
                    continue
                k = KEY_CN[km.group(1)]
                v = km.group(2).strip()
                if k in ("fields", "tags"):
                    fields[k] = _tokens(v)
                else:
                    fields[k] = v
            if unknown:
                warns.append(f"第 {lineno} 行 {cur['qid']}{m.group(1)}："
                             f"无法识别的字段 {unknown[:2]}")
            if not fields["setting"]:
                warns.append(f"第 {lineno} 行 {cur['qid']}{m.group(1)}：缺「设定」")
            fields.update({"id": m.group(1), "qid": cur["qid"],
                           "label": fields["setting"][:40] or f"{cur['qid']}{m.group(1)}"})
            cur["options"].append(fields)
            continue

        # 其他行（说明文字、分隔线）忽略
    return cards, warns


def load_cards(skill_root: str) -> tuple:
    path = os.path.join(skill_root, CARD_FILE)
    if not os.path.exists(path):
        return [], [f"选项卡文件不存在：{path}"]
    with open(path, "r", encoding="utf-8") as f:
        return parse_cards(f.read())


# ════════════════════════════════════════════════════════════════════
# 检索
# ════════════════════════════════════════════════════════════════════

def filter_cards(cards: list, axe: int = None, qid: str = None,
                 tag: str = None) -> list:
    out = cards
    if axe:
        out = [c for c in out if c["axe"] == axe]
    if qid:
        q = qid.strip().upper()
        out = [c for c in out if c["qid"].upper() == q
               or c["qid"].upper().startswith(q + "=")]
    if tag:
        out = [c for c in out
               if any(tag in (o.get("tags") or []) or
                      (o.get("trace") or "").find(tag) >= 0 or
                      (o.get("setting") or "").find(tag) >= 0
                      for o in c["options"])]
    return out


def find_option(cards: list, ref: str) -> tuple:
    """
    解析 'Q3.1=B' / 'Q3.1B' / 'Q3.1 B'。返回 (card, option, error)。
    """
    s = str(ref or "").strip().upper().replace(" ", "")
    m = re.match(r"^(Q\d+\.\d+)[=＝\-]?([A-Z])$", s)
    if not m:
        return None, None, f"引用格式应为 Q3.1=B，收到：{ref}"
    qid, oid = m.group(1), m.group(2)
    for c in cards:
        if c["qid"].upper() != qid:
            continue
        for o in c["options"]:
            if o["id"] == oid:
                return c, o, ""
        return c, None, f"{qid} 没有选项 {oid}（可选：{'/'.join(o['id'] for o in c['options'])}）"
    return None, None, f"没有命题 {qid}"


def roll(cards: list, n: int = 2, seed: int = None, axe: int = None) -> list:
    """抽 n 个命题，每个命题随机给一个选项。同 seed 可复算。"""
    pool = [c for c in cards if c["options"]]
    if axe:
        pool = [c for c in pool if c["axe"] == axe]
    if not pool:
        return []
    rng = random.Random(seed) if seed is not None else random.Random()
    picked = rng.sample(pool, min(int(n), len(pool)))
    out = []
    for c in picked:
        out.append({"card": c, "option": rng.choice(c["options"])})
    return out


def stats(cards: list) -> dict:
    opts = sum(len(c["options"]) for c in cards)
    by_axe = {}
    for c in cards:
        by_axe.setdefault(c["axe"], [0, 0])
        by_axe[c["axe"]][0] += 1
        by_axe[c["axe"]][1] += len(c["options"])
    return {"cards": len(cards), "options": opts,
            "axes": len(by_axe),
            "by_axe": dict(sorted(by_axe.items()))}


# ════════════════════════════════════════════════════════════════════
# 采纳（写 seed.brief.choices）
# ════════════════════════════════════════════════════════════════════

def make_choice(card: dict, opt: dict, date: str = "") -> dict:
    """把一张卡压成 world.json 里的记录（保留代价与痕迹，避免只剩一个字母）。"""
    return {
        "qid": card["qid"],
        "axe": card["axe"],
        "title": card["title"],
        "option": opt["id"],
        "label": opt.get("setting", ""),
        "cost": opt.get("cost", ""),
        "trace": opt.get("trace", ""),
        "tags": list(opt.get("tags") or []),
        "fields": list(opt.get("fields") or []),
        "date": date,
    }


def merge_choices(existing: list, new: list) -> list:
    """同一 qid 只保留一条（后采纳的覆盖先采纳的）。"""
    merged = {str(c.get("qid")): c for c in existing if isinstance(c, dict)}
    for c in new:
        merged[str(c.get("qid"))] = c
    return [merged[k] for k in sorted(merged, key=_qid_key)]


def _qid_key(qid: str):
    m = re.match(r"Q(\d+)\.(\d+)", str(qid))
    return (int(m.group(1)), int(m.group(2))) if m else (99, 99)


def uncovered(cards: list, choices: list) -> list:
    """还没回答的命题（按斧分组）。"""
    done = {str(c.get("qid")) for c in choices if isinstance(c, dict)}
    return [c for c in cards if c["qid"] not in done]


# ════════════════════════════════════════════════════════════════════
# 展示
# ════════════════════════════════════════════════════════════════════

def format_card(card: dict, with_axes: bool = True) -> str:
    L = []
    if with_axes:
        L.append(f"\n【斧 {card['axe']} · {card['axe_cn']}】")
    L.append(f"  {card['qid']}  {card['title']}")
    if card.get("why"):
        L.append(f"        ↳ {card['why']}")
    for o in card["options"]:
        L.append(f"    {o['id']}  {o.get('setting', '')}")
        if o.get("cost"):
            L.append(f"       代价：{o['cost']}")
        if o.get("trace"):
            L.append(f"       痕迹：{o['trace']}")
        if o.get("fields"):
            L.append(f"       要顺手写：{'、'.join(o['fields'])}")
        if o.get("tags"):
            L.append(f"       标签：{' '.join(o['tags'])}")
    return "\n".join(L)


def format_pick(pick: dict) -> str:
    c, o = pick["card"], pick["option"]
    return (f"  {c['qid']}{o['id']}  {o.get('setting', '')}\n"
            f"       代价：{o.get('cost') or '—'}\n"
            f"       痕迹：{o.get('trace') or '—'}\n"
            f"       要顺手写：{'、'.join(o.get('fields') or []) or '—'}")
