# -*- coding: utf-8 -*-
"""
盘古 · 命名层（1.1.6）
======================
前面所有版本都在算「世界是什么样」，没有一版回答「这里的东西叫什么」。
`chronicle` 的模块注释里写得很直白：**不写人名、不写国名，名字是作者的活**。

这一版把这句话改得更精确一点：**名字的骨由引擎给，字由作者改。**

    作者 slug（meta.id）→ 音系（辅音 / 元音 / 韵尾）
    地形（land_fraction / ocean_fraction）→ 地名后缀的语义
    音系 + seed + 构词规则 → 人名 / 地名（可拆音节、可指回字段）

三条设计约束（与 chronicle / entailment 同源）：
  · **有出处**：音系从 `meta.id` 的字母长出来——作者起的世界 id 就是第一份语料；
    不够才补默认集，补了哪些写在 `origin` 里。地名后缀由地形字段决定，没有地形就标 `terrain=none`
  · **可复算**：seed + world → 同一批名字与同一个 hash，`--check` 当场对账
  · **可拆解**：每个名字带 `syllables`（怎么切成音节）、`rule`（哪条构词规则）、
    `src`（引用了哪些字段）；引用失效由 `--check` 点名

刻意没做的事：
  · **不做语法**：没有句法、没有格变化、没有语义漂移。这是给骨架，不是造一门语言
  · **不翻中文**：输出是拉丁转写。哪个 Tal 写成「塔尔」、哪个写成「塔勒」，仍归作者
  · **不猜地形**：没有 `land_fraction` 就不要假装知道沿海还是内陆，后缀池退化为通用集
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

import world_schema as ws

GENERATOR = "naming/1.1.6"

# 默认音素表：只在 meta.id 抽不出足够音素时补位，补了什么记在 phonology.origin
DEFAULT_CONSONANTS = ["k", "t", "m", "n", "s", "l", "r", "v", "h", "d", "g", "th", "sh"]
DEFAULT_VOWELS = ["a", "e", "i", "o", "u"]

# 下限：只靠 meta.id 抽出的音素往往只有四五个，名字会挤成一团。
# 不足时用默认集补到这些数字，补进来的记在 borrowed 里——不假装那是作者的语料。
MIN_CONSONANTS = 8
MIN_VOWELS = 4

VOWEL_LETTERS = set("aeiou")

# 地名后缀：语义按地形给，output 是「岸 / 垒 / 野」这类
SUFFIX_BY_TERRAIN = {
    "coast": [("-tal", "岸"), ("-mar", "渡"), ("-ren", "滩")],
    "inland": [("-gar", "地"), ("-dor", "垒"), ("-kes", "野")],
    "none": [("-tal", "岸"), ("-gar", "地"), ("-kes", "野")],
}


# ════════════════════════════════════════════════════════════════════
# 取值助手
# ════════════════════════════════════════════════════════════════════

def _num(v: Any, d: float = 0.0) -> float:
    try:
        if isinstance(v, bool):
            return d
        return float(v)
    except (TypeError, ValueError):
        return d


def _seed_of(world: dict, override=None) -> int:
    if override is not None:
        return int(override)
    for path in ("civilization.names.seed", "history.chronicle.seed",
                 "seed.number", "meta.seed"):
        ok, v, _ = ws.resolve_path(world, path)
        if ok and _num(v) > 0:
            return int(_num(v))
    # 没有数字 seed 时用 slug 的 crc 兜底：同一份 world 仍然逐位复现
    slug = str((world.get("meta") or {}).get("id") or "")
    h = hashlib.sha1(slug.encode("utf-8")).hexdigest()
    return int(h[:6], 16)


def _letters(text: Any) -> list:
    out = []
    for ch in str(text or "").lower():
        if "a" <= ch <= "z" and ch not in out:
            out.append(ch)
    return out


def _crc(text: Any) -> int:
    return int(hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()[:8], 16)


# ════════════════════════════════════════════════════════════════════
# 音系：从 meta.id 长出来
# ════════════════════════════════════════════════════════════════════

def phonology(world: dict) -> dict:
    """读音系统。优先级：作者接管 > meta.id 的字母 > 默认集补位。"""
    store = ws._get(world, "civilization", "names", default={})
    if isinstance(store, dict) and isinstance(store.get("phonology"), dict):
        ph = dict(store["phonology"])
        ph.setdefault("origin", "author")
        ph.setdefault("src", ["civilization.names.phonology"])
        return ph

    slug = str((world.get("meta") or {}).get("id") or "")
    letters = _letters(slug)
    cons = [c for c in letters if c not in VOWEL_LETTERS]
    vow = [c for c in letters if c in VOWEL_LETTERS]
    origin = "meta.id"
    borrowed = []
    if len(cons) < MIN_CONSONANTS or len(vow) < MIN_VOWELS:
        origin = "meta.id+default"
        for c in DEFAULT_CONSONANTS:
            if len(cons) >= MIN_CONSONANTS:
                break
            if c not in cons:
                cons.append(c)
                borrowed.append(c)
        for v in DEFAULT_VOWELS:
            if len(vow) >= MIN_VOWELS:
                break
            if v not in vow:
                vow.append(v)
                borrowed.append(v)
    codas = [c for c in cons if c not in ("h", "th", "sh")][:4] or cons[:2]
    return {
        "consonants": cons,
        "vowels": vow,
        "codas": codas,
        "borrowed": borrowed,
        "origin": origin,
        "src": ["meta.id"],
    }


def pool_size(ph: dict) -> dict:
    """名字池有多大——给「这些名字会不会都长一个样」一个可算的答案。"""
    nc, nv, nk = len(ph.get("consonants") or []), len(ph.get("vowels") or []), len(ph.get("codas") or [])
    return {
        "cv": nc * nv,
        "cvc": nc * nv * nk,
        "two_syllable_cv": (nc * nv) ** 2,
    }


# ════════════════════════════════════════════════════════════════════
# 构词
# ════════════════════════════════════════════════════════════════════

def _syllable(rng: random.Random, ph: dict) -> str:
    s = rng.choice(ph["consonants"]) + rng.choice(ph["vowels"])
    if rng.random() < 0.45 and ph.get("codas"):
        s += rng.choice(ph["codas"])
    return s


def _word(rng: random.Random, ph: dict, max_syl: int = 2) -> tuple:
    word, syls = "", []
    for _ in range(40):
        n = rng.randint(1, max_syl)
        syls = [_syllable(rng, ph) for _ in range(n)]
        word = "".join(syls)
        # 禁止辅音连写（Lollil 那种），最少 3 个字母
        if len(word) >= 3 and not re.search(r"([bcdfghjklmnpqrstvwxz])\1", word):
            return word, syls
    return word, syls


def _unique(rng: random.Random, ph: dict, n: int, used: set, max_syl: int = 2,
            max_try: int = 4000) -> list:
    out = []
    tries = 0
    while len(out) < n and tries < max_try:
        tries += 1
        word, syls = _word(rng, ph, max_syl)
        if word.lower() in used or len(word) < 3:
            continue
        used.add(word.lower())
        out.append((word, syls))
    return out


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:]


def _terrain(world: dict) -> tuple:
    """返回 (terrain, land_fraction, 出处路径)。没有数据就是 none，不猜。"""
    ok, land, _ = ws.resolve_path(world, "biology.carrying_capacity.land_fraction")
    src = "biology.carrying_capacity.land_fraction"
    if not ok or _num(land) <= 0:
        ok, land, _ = ws.resolve_path(world, "cosmology.bodies[0].planet_map.summary.land_fraction")
        src = "cosmology.bodies[0].planet_map.summary.land_fraction"
    if not ok or _num(land) <= 0:
        ok, ocean, _ = ws.resolve_path(world, "cosmology.bodies[0].planet_map.summary.ocean_fraction")
        src = "cosmology.bodies[0].planet_map.summary.ocean_fraction"
        if ok and 0 < _num(ocean) < 1:
            land = 1.0 - _num(ocean)
            ok = True
    if not ok or _num(land) <= 0:
        return "none", 0.0, ""
    land = _num(land)
    return ("coast" if land <= 0.40 else "inland"), land, src


# ════════════════════════════════════════════════════════════════════
# 主推演
# ════════════════════════════════════════════════════════════════════

def derive(world: dict, seed=None, count_person: int = 10, count_place: int = 10) -> dict:
    """音系 + seed → 人名 / 地名。随机量只在这里取，顺序固定 → 可复算。"""
    ph = phonology(world)
    rng = random.Random(_seed_of(world, seed))
    civ = ws._get(world, "civilization", default={}) or {}
    civ_name = str(civ.get("name") or "")
    terrain, land, terrain_src = _terrain(world)
    suffixes = SUFFIX_BY_TERRAIN[terrain]

    used = set()
    persons = []
    for given, gsyl in _unique(rng, ph, count_person, used):
        clan, csyl = _unique(rng, ph, 1, used)[0]
        persons.append({
            "name": f"{_cap(given)} {_cap(clan)}",
            "given": _cap(given),
            "clan": _cap(clan),
            "syllables": gsyl + csyl,
            "rule": "P1 名（1–2 音节）+ 氏族（1–2 音节）",
            "src": list(ph.get("src") or []) + ["civilization.name"],
        })

    places = []
    for root, rsyl in _unique(rng, ph, count_place, used):
        suf, meaning = suffixes[rng.randrange(len(suffixes))]
        for _ in range(3):
            cand = (_cap(root) + suf.lstrip("-")).lower()
            if not re.search(r"([bcdfghjklmnpqrstvwxz])\1", cand):
                break
            suf, meaning = suffixes[rng.randrange(len(suffixes))]
        places.append({
            "name": _cap(root) + suf.lstrip("-"),
            "root": _cap(root),
            "suffix": suf,
            "meaning": meaning,
            "terrain": terrain,
            "syllables": rsyl,
            "rule": "L1 词根 + 地形后缀",
            "src": (["civilization.names.phonology"] if ph.get("origin") == "author"
                    else ["meta.id"]) + ([terrain_src] if terrain_src else []),
        })

    data = {
        "generator": GENERATOR,
        "seed": _seed_of(world, seed),
        "phonology": ph,
        "pool": pool_size(ph),
        "person": persons,
        "place": places,
        "civilization": civ_name,
        "hash": "",
        "summary": {
            "n_person": len(persons),
            "n_place": len(places),
            "terrain": terrain,
            "land_fraction": round(land, 4) if land else None,
            "terrain_src": terrain_src or "（缺失，后缀退化为通用集）",
            "unique": len({p["name"].lower() for p in persons}
                          | {p["name"].lower() for p in places}) == len(persons) + len(places),
            "pool": pool_size(ph),
        },
    }
    data["hash"] = _hash(data)
    return data


def _hash(data: dict) -> str:
    blob = json.dumps({
        "seed": data.get("seed"),
        "phonology": data.get("phonology", {}).get("consonants"),
        "cons2": data.get("phonology", {}).get("vowels"),
        "codas": data.get("phonology", {}).get("codas"),
        "person": [p.get("name") for p in data.get("person") or []],
        "place": [p.get("name") for p in data.get("place") or []],
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


# ════════════════════════════════════════════════════════════════════
# 体检
# ════════════════════════════════════════════════════════════════════

def check(world: dict) -> dict:
    """复算 hash + 检查每条 src 是否还能解析。"""
    store = ws._get(world, "civilization", "names", default=None)
    if not isinstance(store, dict) or not store.get("person"):
        return {"ok": False, "hash_ok": None, "why": "civilization.names 还没有生成",
                "stale": [], "stored_hash": None, "now_hash": None}
    persons = store.get("person") or []
    places = store.get("place") or []
    again = derive(world, seed=store.get("seed"),
                   count_person=len(persons), count_place=len(places))
    stored, now = store.get("hash"), again["hash"]
    # 存档里的名字本身也要对账：手改一个字母，self_ok 就变 False
    live = _hash({**again, "person": persons, "place": places})
    self_ok = stored == live

    stale = []
    for item in list(persons) + list(places):
        bad = [s for s in (item.get("src") or []) if not ws.resolve_path(world, s)[0]]
        if bad:
            stale.append({"name": item.get("name"), "bad": bad})

    names = [str(p.get("name") or "") for p in persons] + [str(p.get("name") or "") for p in places]
    dup = sorted({n for n in names if names.count(n) > 1})

    ok = self_ok and stored == now and not stale and not dup
    why = "可复算、引用完整、无重名" if ok else (
        "名字被手改过（存档 hash 与内容不符）" if not self_ok else
        "hash 不一致（音系或 seed 变了）" if stored != now else
        f"{len(stale)} 条引用了不存在的字段" if stale else f"重名：{dup[:4]}")
    return {"ok": ok, "hash_ok": stored == now, "self_ok": self_ok, "why": why,
            "stale": stale, "dup": dup, "stored_hash": stored, "now_hash": now,
            "live_hash": live}


# ════════════════════════════════════════════════════════════════════
# 渲染
# ════════════════════════════════════════════════════════════════════

def format_report(data: dict, world: dict) -> str:
    ph = data["phonology"]
    pool = data["pool"]
    L = []
    L.append(f"命名层 · {data.get('civilization') or '（未命名文明）'}")
    L.append("-" * 62)
    L.append(f"  音系　辅音 {' '.join(ph['consonants'])}")
    L.append(f"　　　　元音 {' '.join(ph['vowels'])}　韵尾 {' '.join(ph.get('codas') or [])}")
    borrowed = ph.get("borrowed") or []
    L.append(f"　　　　出处 {'、'.join(ph.get('src') or [])}（{ph.get('origin')}）"
             + (f"　补：{' '.join(borrowed)}" if borrowed else ""))
    L.append(f"  池子　CV {pool['cv']} ｜ CVC {pool['cvc']} ｜ 双音节 CV {pool['two_syllable_cv']}")
    s = data["summary"]
    L.append(f"  地形　{s['terrain']}"
             + (f"（陆地 {s['land_fraction']:.1%}）" if s.get("land_fraction") else "")
             + f"　← {s['terrain_src']}")
    L.append("")
    L.append("◆ 人名")
    for p in data["person"]:
        L.append(f"  {p['name']:<16} {'-'.join(p['syllables'])}"
                 f"　{p['rule']}")
    L.append("")
    L.append("◆ 地名")
    for p in data["place"]:
        cut = "-".join(list(p["syllables"]) + [p["suffix"].lstrip("-")])
        L.append(f"  {p['name']:<16} {cut}"
                 f"　{p['suffix']}={p['meaning']}　（{p['terrain']}）")
    L.append("")
    L.append("-" * 62)
    L.append(f"  共 {len(data['person'])} 人名 + {len(data['place'])} 地名 ｜ seed {data['seed']} "
             f"｜ hash {data['hash']} ｜ 生成器 {data['generator']}")
    if not s.get("unique"):
        L.append("  ✗ 有重名：池子不够时先加韵尾，或把 --count 调小")
    L.append("  口径：名字的骨由音系与地形给出，字归作者——"
             "要换一套读音就 --set-phonology，要中文用字自己改写。")
    return "\n".join(L)
