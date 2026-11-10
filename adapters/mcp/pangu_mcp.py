#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古 · MCP 服务器（stdio / JSON-RPC 2.0 / 零依赖）
==================================================

把盘古引擎暴露成 MCP tool，供任何支持 Model Context Protocol 的宿主调用：
Claude Desktop、Cursor、Zed、Continue、Cherry Studio、以及自研 harness。

设计原则
--------
1. **不重写逻辑**：所有操作都转调 `scripts/pangu.py`，MCP 只是一层薄壳。
   这样 CLI 与 MCP 的行为永远一致，不会分叉。
2. **零依赖**：只用标准库，不需要 `pip install mcp`。协议实现是手写的最小集合
   （initialize / tools/list / tools/call / ping）。
3. **stdout 只走协议**：任何日志、异常都打到 stderr，否则会污染 JSON-RPC 流。

启动
----
    python /abs/path/to/盘古/adapters/mcp/pangu_mcp.py

客户端配置（Claude Desktop / Cursor 等）：

    {
      "mcpServers": {
        "pangu": {
          "command": "python",
          "args": ["/abs/path/to/盘古/adapters/mcp/pangu_mcp.py"]
        }
      }
    }

自检：
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python pangu_mcp.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CLI = os.path.join(ROOT, "scripts", "pangu.py")

SERVER_NAME = "pangu"
SERVER_VERSION = "1.1.6"
DEFAULT_PROTOCOL = "2024-11-05"
SUPPORTED_PROTOCOLS = ("2024-11-05", "2024-10-07", "2025-03-26", "2025-06-18")

MAX_OUTPUT = 60000  # 单次 tool 返回字符上限，超出截断（防止撑爆上下文）


# ════════════════════════════════════════════════════════════════════
# 工具定义
# ════════════════════════════════════════════════════════════════════

def _schema(props: dict, required: list | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }


_S = {"type": "string"}
_B = {"type": "boolean"}
_I = {"type": "integer"}

TOOLS = [
    {
        "name": "pangu_guide",
        "title": "读取创世方法论",
        "description": (
            "读取盘古的创世方法论。不传 section 返回主文档 SKILL.md（约 200 行，"
            "含三律、七斧流程、检索策略、审查协议、命令速查）；"
            "传 section 可单独读取某份参考文档，用于渐进披露、节省上下文。"
            "造世界前必先调用本工具。"
        ),
        "inputSchema": _schema({
            "section": {
                "type": "string",
                "enum": ["skill", "axes", "axioms", "cards", "search", "audit", "schema"],
                "description": ("skill=主文档；axes=七斧创世法；axioms=公理库；"
                                "cards=选项卡（31 个命题 / 132 个选项）；search=检索策略；"
                                "audit=自洽性审查协议；schema=world.json 字段规范"),
            }
        }),
    },
    {
        "name": "pangu_doctor",
        "title": "环境自检",
        "description": "检查 Python 版本、模板文件、示例世界、CDN 可达性。首次使用或报错时先跑这个。",
        "inputSchema": _schema({}),
    },
    {
        "name": "pangu_init",
        "title": "生成世界骨架",
        "description": (
            "从一个名字与一句话种子，生成符合规范的 world.json 骨架"
            "（含 meta/seed/cosmology/physics 等全部顶层字段的空壳）。"
            "生成后由 agent 按七斧逐步填充。"
        ),
        "inputSchema": _schema({
            "name": {"type": "string", "description": "世界名，如「赫利孔」"},
            "seed": {"type": "string", "description": "一句话种子，如「三倍地球大，天上有两个太阳」"},
            "out": {"type": "string", "description": "输出路径（绝对路径最稳）。缺省写到 ./out/<id>/world.json"},
            "id": {"type": "string", "description": "英文 slug，缺省由名字生成"},
            "star_count": {"type": "integer", "description": "恒星数量 1–4，默认 2"},
            "no_stars": {"type": "boolean", "description": "无恒星世界（靠地热或其他能源）"},
            "autonomy": {
                "type": "string",
                "enum": ["auto", "co-create", "audit"],
                "description": "自主度：auto=全自主；co-create=共创；audit=只做审查",
            },
        }, ["name"]),
    },
    {
        "name": "pangu_validate",
        "title": "自洽性校验与打分",
        "description": (
            "对 world.json 做可机检的自洽性审查：结构完整性、单位与量纲、"
            "派生量计算（密度/重力/逃逸速度/平衡温度）、双星轨道稳定性、洛希极限、"
            "能量收支数量级。返回评分（0–100）、等级、致命项与修补建议。"
            "**交付前必须调用，有 fatal 不许交付。**"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "json": {"type": "boolean", "description": "返回结构化 JSON 而非人类可读报告"},
            "brief": {"type": "boolean", "description": "只返回一行式结论：分数 + 斧位 + 下一步"},
            "fix_hint": {"type": "boolean", "description": "附带每项的修补建议（默认 true）"},
        }, ["world"]),
    },
    {
        "name": "pangu_preview",
        "title": "生成 3D 预览页",
        "description": (
            "把 world.json 渲染成单文件 3D 预览页（Three.js）：多恒星系统、程序化行星表面、"
            "大气辉光、云层、轨道线、多光源昼夜、潮汐锁定、时间控制、视角切换。"
            "输出自包含 HTML，双击即可看。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "out": {"type": "string", "description": "输出 html 路径，缺省与 world.json 同目录"},
            "title": {"type": "string", "description": "页面标题，缺省用世界名"},
        }, ["world"]),
    },
    {
        "name": "pangu_export",
        "title": "导出世界档案",
        "description": (
            "生成人类可读的世界档案 Markdown：三律、常数表与地球对照、派生量、"
            "天空与气候、生态、文明、审查结论。可同时输出审查报告 JSON。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "md": {"type": "string", "description": "输出 md 路径"},
            "json_out": {"type": "string", "description": "同时输出审查报告 JSON 的路径"},
        }, ["world"]),
    },
    {
        "name": "pangu_axioms",
        "title": "抽取反常识积木",
        "description": (
            "从 60+ 条公理积木里查询或随机抽取可复用的反常识设定，每条含："
            "设定、代价、痕迹、适用尺度、代价类型标签。卡住时用它打破地球直觉。"
            "可按代价类型过滤（时间/空间/能量/物质/感知/社会/生命/结构）。"
        ),
        "inputSchema": _schema({
            "domain": {
                "type": "string",
                "enum": ["physics", "cosmos", "math", "chemistry", "biology", "civilization"],
                "description": "领域过滤",
            },
            "cost": {"type": "string",
                     "description": "代价类型过滤，如「空间」「时间」「生命」"},
            "cost_list": {"type": "boolean", "description": "列出代价类型索引与条数"},
            "roll": {"type": "integer", "description": "随机抽 N 条"},
            "json": {"type": "boolean", "description": "返回结构化 JSON"},
        }),
    },
    {
        "name": "pangu_map",
        "title": "推演行星地图",
        "description": (
            "从 world.json 推演整颗行星的地图：板块构造 → 盆地 → 水量定海平面 → "
            "年辐照/温室定温度 → 风带与迎风坡定降水 → 洼地填充定河网 → "
            "高程带 × 湿度定群系。输出高程/群系/温度/降水/构造/宜居度/正射地球图，"
            "外加可交互 map.html。--check 同 seed 复算，--write 才写回摘要。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "run": {"type": "boolean", "description": "出图与交互页"},
            "check": {"type": "boolean", "description": "同 seed 复算体检"},
            "write": {"type": "boolean", "description": "把摘要与粗粒度场写回 world.json"},
            "yes": {"type": "boolean", "description": "确认写回（write 时必须为 true）"},
            "res": {"type": "string", "description": "推演网格，如 360x180"},
            "render": {"type": "string", "description": "出图分辨率，如 1440x720"},
            "seed": {"type": "integer", "description": "覆盖随机种子"},
            "out": {"type": "string", "description": "图输出目录"},
        }, ["world"]),
    },
    {
        "name": "pangu_ca",
        "title": "生态演化：编译 / 跑 / 复算",
        "description": (
            "把 biology.evolution 编译成元胞自动机并运行。每条规则必须带 source 指回设定；"
            "1.1.1 支持逐规则邻居半径、cos(lat) 面积加权、planet_map 宜居度耦合"
            "（初始分布 + 生长概率）、逐格 final_hash 复算。--check 同 seed 复算，"
            "--write 才回写 summary。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "run": {"type": "boolean", "description": "跑演化并出快照图"},
            "check": {"type": "boolean", "description": "复算并与 summary 比对"},
            "write": {"type": "boolean", "description": "把结果写回 summary"},
            "yes": {"type": "boolean", "description": "确认写回（write 时必须为 true）"},
            "steps": {"type": "integer", "description": "覆盖步数"},
            "frames": {"type": "integer", "description": "出 N 张等距快照"},
            "seed": {"type": "integer", "description": "覆盖随机种子"},
            "out": {"type": "string", "description": "快照图输出目录"},
        }, ["world"]),
    },
    {
        "name": "pangu_patch",
        "title": "定点改 / 增 / 查字段",
        "description": (
            "按点路径读写 world.json，替代手改 JSON。--set 改或增字段（值先按 JSON 解析，"
            "失败当字符串），--get 查值；成功写入会自动把 meta.version 补丁位 +1，"
            "并在 history.revisions[] 追加一条修订记录。改完立刻返回评分/fatal 变化。"
            "默认拒绝写不存在的字段，加 create=true 才允许新建或追加数组。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "set": {"type": "array", "items": {"type": "string"},
                    "description": "要写入的 '路径=值'，如 physics.constants[0].world_value=4.0e-11"},
            "get": {"type": "array", "items": {"type": "string"},
                    "description": "要查询的路径，如 cosmology.bodies[0].mass_earth"},
            "create": {"type": "boolean", "description": "允许新建字段 / 追加数组"},
            "note": {"type": "string", "description": "修订说明"},
            "version": {"type": "string", "description": "显式指定新版本号"},
            "no_bump": {"type": "boolean", "description": "不改版本、不记修订"},
            "dry_run": {"type": "boolean", "description": "只显示改动，不写盘"},
        }, ["world"]),
    },
    {
        "name": "pangu_sweep",
        "title": "参数敏感度扫描",
        "description": (
            "沿一个数值参数扫出连续谱，每步完整校验，标出评分/fatal 的变化，"
            "并给出安全窗与第一个崩点。recalc=true 会同时重算天体的密度/重力/半径，"
            "让扫描探索物理自洽的邻近世界（否则质量一动就撞 P01）。"
            "list=true 列出可扫描的参数路径。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "param": {"type": "string", "description": "要扫的点路径"},
            "from": {"type": "number", "description": "起始值"},
            "to": {"type": "number", "description": "终止值"},
            "percent": {"type": "number", "description": "以当前值为中心 ±N%（默认 20）"},
            "steps": {"type": "integer", "description": "采样点数 3–31，默认 7"},
            "body": {"type": "integer", "description": "看第几个天体的派生量，默认 0"},
            "recalc": {"type": "boolean", "description": "每步重算密度/重力/半径"},
            "log": {"type": "boolean", "description": "等比采样，跨数量级扫参数时用"},
            "list": {"type": "boolean", "description": "列出可扫描参数"},
        }, ["world"]),
    },
    {
        "name": "pangu_diff",
        "title": "世界版本对比",
        "description": (
            "深度对比两份 world.json：逐字段列出改动/新增/删除，给出评分、致命项、"
            "表面重力、温度、反常识度与**斧位推进**的变化，并推断必须重跑的下游产物"
            "（export / preview / map / ca / slice / redteam）。"
        ),
        "inputSchema": _schema({
            "a": {"type": "string", "description": "旧版 world.json"},
            "b": {"type": "string", "description": "新版 world.json"},
            "limit": {"type": "integer", "description": "最多记录多少处改动，默认 200"},
        }, ["a", "b"]),
    },
    {
        "name": "pangu_plan",
        "title": "七斧进度与下一步",
        "description": (
            "七斧状态机。读 world.json 判定当前在第几斧（1 混沌 … 7 演界），"
            "列出这一斧还缺哪些字段、这一斧该回答的 2–3 个问题、该做哪几次检索、"
            "以及**按顺序的下一步命令**；同时报告 6 项交付门槛（自洽 / 反常识度 / "
            "切片 / 红队 / 地图 / 选项卡一致）。造世界的每一轮都该先调它。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "axe": {"type": "integer", "description": "只看某一斧的细账 1–7"},
            "brief": {"type": "boolean", "description": "只返回一行式结论"},
            "next": {"type": "boolean", "description": "只返回下一条该跑的命令"},
        }, ["world"]),
    },
    {
        "name": "pangu_options",
        "title": "选项卡（命题与选项）",
        "description": (
            "按斧列出**必须回答的命题**与每个命题的互斥选项，每个选项都带代价、痕迹、"
            "要顺手写的字段与互斥标签。不传 world 时只做检索（axe / qid / tag / roll）；"
            "传 world 时可用 adopt 采纳（写进 seed.brief.choices，自动升版本记修订，"
            "互斥会被拒绝），或用 check 体检已采纳的卡与 world.json 是否对得上。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json（adopt / check 时必填）"},
            "axe": {"type": "integer", "description": "只看某一斧 1–7"},
            "qid": {"type": "string", "description": "只看一个命题，如 Q3.1"},
            "tag": {"type": "string", "description": "按标签过滤，如 双星"},
            "roll": {"type": "integer", "description": "随机抽 N 个命题"},
            "seed": {"type": "integer", "description": "抽卡随机种子"},
            "adopt": {"type": "array", "items": {"type": "string"},
                      "description": "采纳的选项，如 Q3.1=B，可多个"},
            "check": {"type": "boolean", "description": "体检已采纳的卡：互斥 / 未答命题"},
            "unanswered": {"type": "boolean", "description": "只列还没作答的命题"},
            "stats": {"type": "boolean", "description": "只看题库规模"},
        }),
    },
    {
        "name": "pangu_review",
        "title": "交付体检（八项，一条命令）",
        "description": (
            "交付前一键全检：自洽 / 反常识度 / 切片 / 红队 / 地图复算 / 演化复算 / "
            "推论失效 / 选项卡一致，八项各自给结论，最后给一个「能不能交」的单一判断，"
            "并把未过的硬门槛按修复顺序排好。只读，不改 world.json。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "fast": {"type": "boolean", "description": "跳过地图与演化的复算（只看结构）"},
        }, ["world"]),
    },
    {
        "name": "pangu_whatif",
        "title": "反事实推演（改一条设定会怎样）",
        "description": (
            "在内存副本上改设定，回答「世界会变成什么样」：派生量怎么动、哪些必然推论消失、"
            "哪些新推论出现、审查从哪一条开始崩、下游要重跑什么。set 指定新值，scale 按倍率"
            "缩放（保留单位后缀），recalc 先重算密度/重力以抹平 P01 这类算术冲突。"
            "不写原世界；要留下假设世界用 write 指定新文件。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "set": {"type": "array", "items": {"type": "string"},
                    "description": "假设改成这个值，如 physics.constants[0].world_value=2.4e-11"},
            "scale": {"type": "array", "items": {"type": "string"},
                      "description": "按倍率缩放，如 cosmology.bodies[0].mass_earth=1.5"},
            "recalc": {"type": "boolean", "description": "按新参数重算密度 / 重力"},
            "write": {"type": "string", "description": "把假设世界写到这个新文件"},
        }, ["world"]),
    },
    {
        "name": "pangu_sky",
        "title": "观测层（抬头看见什么）",
        "description": (
            "把 world.json 里已有的观测点、倾角、大气、恒星、卫星算成一张**今夜星图**："
            "天光亮度、极限星等、地平线上可见星数、银河可见性、每颗恒星的 alt-az 与视星等，"
            "外加一年的昼长与极昼极夜表。星表按 seed 确定性生成、可复算，不是真实星表。"
            "check=true 体检星表 hash 与摘要；write=true 回写 cosmology.sky。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "at": {"type": "string",
                   "description": '时刻，如 "22:10" / "day=12,hour=22" / "日落后 2h"'},
            "lat": {"type": "number", "description": "覆盖观测点纬度"},
            "year": {"type": "boolean", "description": "只出一年昼长与季节表"},
            "allnight": {"type": "boolean", "description": "一夜六帧"},
            "check": {"type": "boolean", "description": "星空体检 S01/S02/S03"},
            "json": {"type": "boolean", "description": "机器可读输出"},
        }, ["world"]),
    },
    {
        "name": "pangu_benchmark",
        "title": "地球基准（模型离地球多远）",
        "description": (
            "把地球参数喂进引擎，六条曲线对公开数据：纬向年均温、纬向年降水、昼长、"
            "逃逸速度、平衡温度、陆地 NPP。输出目标 / 实测 / 是否达标。"
            "这是「模型」与「美术」的分界线——对不上就如实写偏差。"
        ),
        "inputSchema": _schema({
            "target": {"type": "string", "enum": ["earth"], "description": "目前只有 earth"},
            "json": {"type": "boolean", "description": "机器可读输出"},
        }, []),
    },
    {
        "name": "pangu_capacity",
        "title": "行星承载力（养得活多少人）",
        "description": (
            "由气候场算陆地净初级生产力（Miami 模型），再按可采收比例与人均热量，"
            "给出这颗星球的人口上限。write=true 回写 biology.carrying_capacity。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "harvest": {"type": "number", "description": "可采收的 NPP 比例（默认 0.01）"},
            "write": {"type": "boolean", "description": "回写 biology.carrying_capacity"},
            "yes": {"type": "boolean", "description": "确认回写"},
            "json": {"type": "boolean", "description": "机器可读输出"},
        }, ["world"]),
    },
    {
        "name": "pangu_entail",
        "title": "必然推论（设定 → 现象）",
        "description": (
            "从已立好的律**机械推导**出这个世界的居民必然会看见什么：36 条后果规则"
            "（双影、不落的灯、永昼永夜、没有翅膀、会飞的雨滴、无需闰的年……），"
            "每条给出断言、可观测痕迹与出处字段。write=true 按 〔entail E01〕 标记"
            "幂等回写 cosmology.sky_phenomena；check=true 体检有没有因改设定而失效的旧推论。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径（list=true 时可省）"},
            "list": {"type": "boolean", "description": "列 36 条规则的编号 / 名称 / 触发条件 / 强度"},
            "only": {"type": "string", "description": "只跑指定推论，如 E01,E04"},
            "exclude": {"type": "string", "description": "排除指定推论，如 E02,E09"},
            "write": {"type": "boolean", "description": "回写 sky_phenomena（需 yes=true）"},
            "yes": {"type": "boolean", "description": "确认回写"},
            "check": {"type": "boolean", "description": "体检失效推论"},
        }),
    },
    {
        "name": "pangu_chronicle",
        "title": "编年史（承载力 → 文明时间轴）",
        "description": (
            "从承载力与历法**推**出一条文明编年史：19 条规则（第一笔 / 定历 / 立禁 / "
            "种子入土 / 城市 / 文字 / 出海 / 成国 / 争地 / 大疫 / 变法 / 国教 / 顶点 / 余波，"
            "外加双日之民 / 没有黑夜 / 两段睡眠 / 晨昏线），事件时刻由 logistic 人口曲线"
            "反解，每条带 src 出处与强度（必然 / 很可能）。同 seed 可复算。"
            "write=true 回写 history.chronicle；check=true 复算 hash、检出引用失效与人口越界。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径（list=true 时可省）"},
            "list": {"type": "boolean", "description": "列 19 条规则的编号 / 触发条件 / 强度"},
            "seed": {"type": "number", "description": "覆盖抖动种子"},
            "from_year": {"type": "number", "description": "只看这一年之后（时间轴回放）"},
            "to_year": {"type": "number", "description": "只看这一年之前"},
            "kind": {"type": "string", "description": "只看某一类事件，如 war / plague"},
            "write": {"type": "boolean", "description": "回写 history.chronicle（需 yes=true）"},
            "yes": {"type": "boolean", "description": "确认回写"},
            "check": {"type": "boolean", "description": "hash 复算 / 引用失效 / 人口越界"},
            "json": {"type": "boolean", "description": "机器可读输出"},
        }, ["world"]),
    },
]

GUIDE_FILES = {
    "skill": ("SKILL.md", None),
    "axes": ("references/七斧创世法.md", None),
    "axioms": ("references/公理库.md", None),
    "cards": ("references/选项卡.md", None),
    "search": ("references/检索与灵感策略.md", None),
    "audit": ("references/自洽性审查协议.md", None),
    "schema": ("references/world-schema.md", None),
}


# ════════════════════════════════════════════════════════════════════
# 执行
# ════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    """日志只能走 stderr，否则会污染 JSON-RPC 流。"""
    try:
        sys.stderr.write(f"[pangu-mcp] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _run_cli(args: list) -> tuple:
    """转调 CLI，返回 (退出码, stdout, stderr)。"""
    if not os.path.exists(CLI):
        return 3, "", f"找不到 CLI：{CLI}"
    try:
        r = subprocess.run(
            [sys.executable, CLI, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 3, "", "命令超时（300s）"
    except Exception as e:  # noqa: BLE001
        return 3, "", f"{type(e).__name__}: {e}"


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n\n…（已截断，原文 {len(text)} 字符）"


def _result(text: str, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": _clip(text)}],
        "isError": bool(is_error),
    }


def _call_tool(name: str, a: dict) -> dict:
    # ── 读方法论 ──────────────────────────────────────────────
    if name == "pangu_guide":
        key = a.get("section") or "skill"
        rel = GUIDE_FILES.get(key)
        if not rel:
            return _result(f"未知 section：{key}。可选：{'/'.join(GUIDE_FILES)}", True)
        path = os.path.join(ROOT, rel[0])
        if not os.path.exists(path):
            return _result(f"文档缺失：{path}", True)
        with open(path, "r", encoding="utf-8") as f:
            return _result(f.read())

    # ── 环境自检 ──────────────────────────────────────────────
    if name == "pangu_doctor":
        code, out, err = _run_cli(["doctor"])
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 生成骨架 ──────────────────────────────────────────────
    if name == "pangu_init":
        world = a.get("name") or ""
        if not world:
            return _result("缺少参数 name", True)
        args = ["init", "--name", world]
        if a.get("seed"):
            args += ["--seed", str(a["seed"])]
        if a.get("id"):
            args += ["--id", str(a["id"])]
        if a.get("out"):
            args += ["--out", str(a["out"])]
        if a.get("star_count"):
            args += ["--star-count", str(int(a["star_count"]))]
        if a.get("no_stars"):
            args += ["--no-stars"]
        if a.get("autonomy"):
            args += ["--autonomy", str(a["autonomy"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 校验 ──────────────────────────────────────────────────
    if name == "pangu_validate":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["validate", str(w)]
        if a.get("json"):
            args.append("--json")
        if a.get("brief"):
            args.append("--brief")
        if a.get("fix_hint", True):
            args.append("--fix-hint")
        code, out, err = _run_cli(args)
        body = out + (f"\n[stderr]\n{err}" if err.strip() else "")
        return _result(body, code not in (0, 1))   # 1 = 有 fatal，仍是有效结果

    # ── 预览 ──────────────────────────────────────────────────
    if name == "pangu_preview":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["preview", str(w)]
        if a.get("out"):
            args += ["-o", str(a["out"])]
        if a.get("title"):
            args += ["--title", str(a["title"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 导出 ──────────────────────────────────────────────────
    if name == "pangu_export":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["export", str(w)]
        if a.get("md"):
            args += ["--md", str(a["md"])]
        if a.get("json_out"):
            args += ["--json-out", str(a["json_out"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 公理库 ────────────────────────────────────────────────
    if name == "pangu_axioms":
        args = ["axioms"]
        if a.get("domain"):
            args += ["--domain", str(a["domain"])]
        if a.get("cost"):
            args += ["--cost", str(a["cost"])]
        if a.get("cost_list"):
            args.append("--cost-list")
        if a.get("axe"):
            args += ["--axe", str(int(a["axe"]))]
        if a.get("roll"):
            args += ["--roll", str(int(a["roll"]))]
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 行星地图 ──────────────────────────────────────────────
    if name == "pangu_map":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["map", str(w)]
        for k in ("run", "check", "write"):
            if a.get(k):
                args.append("--" + k)
        if a.get("write") and a.get("yes"):
            args.append("--yes")
        for k in ("res", "render", "out"):
            if a.get(k):
                args += ["--" + k, str(a[k])]
        if a.get("seed") is not None:
            args += ["--seed", str(int(a["seed"]))]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 生态演化 ──────────────────────────────────────────────
    if name == "pangu_ca":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["ca", str(w)]
        for k in ("run", "check", "write"):
            if a.get(k):
                args.append("--" + k)
        if a.get("write") and a.get("yes"):
            args.append("--yes")
        for k in ("steps", "frames", "seed"):
            if a.get(k) is not None:
                args += ["--" + k, str(int(a[k]))]
        if a.get("out"):
            args += ["--out", str(a["out"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 定点改字段 ────────────────────────────────────────────
    if name == "pangu_patch":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["patch", str(w)]
        for s in (a.get("set") or []):
            args += ["--set", str(s)]
        for g in (a.get("get") or []):
            args += ["--get", str(g)]
        if a.get("create"):
            args.append("--create")
        if a.get("note"):
            args += ["--note", str(a["note"])]
        if a.get("version"):
            args += ["--version", str(a["version"])]
        if a.get("no_bump"):
            args.append("--no-bump")
        if a.get("dry_run"):
            args.append("--dry-run")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 参数扫描 ──────────────────────────────────────────────
    if name == "pangu_sweep":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["sweep", str(w)]
        if a.get("log"):
            args.append("--log")
        if a.get("list"):
            args.append("--list")
        if a.get("param"):
            args += ["--param", str(a["param"])]
        if a.get("from") is not None:
            args += ["--from", str(a["from"])]
        if a.get("to") is not None:
            args += ["--to", str(a["to"])]
        if a.get("percent") is not None:
            args += ["--percent", str(a["percent"])]
        if a.get("steps") is not None:
            args += ["--steps", str(int(a["steps"]))]
        if a.get("body") is not None:
            args += ["--body", str(int(a["body"]))]
        if a.get("recalc"):
            args.append("--recalc")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 版本对比 ──────────────────────────────────────────────
    if name == "pangu_diff":
        if not a.get("a") or not a.get("b"):
            return _result("缺少参数 a / b", True)
        args = ["diff", str(a["a"]), str(a["b"])]
        if a.get("limit") is not None:
            args += ["--limit", str(int(a["limit"]))]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code not in (0, 1))

    # ── 七斧进度 ──────────────────────────────────────────────
    if name == "pangu_plan":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["plan", str(w)]
        if a.get("axe"):
            args += ["--axe", str(int(a["axe"]))]
        if a.get("brief"):
            args.append("--brief")
        if a.get("next"):
            args.append("--next")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 选项卡 ────────────────────────────────────────────────
    if name == "pangu_options":
        args = ["options"]
        if a.get("world"):
            args.append(str(a["world"]))
        if a.get("axe"):
            args += ["--axe", str(int(a["axe"]))]
        if a.get("qid"):
            args += ["--qid", str(a["qid"])]
        if a.get("tag"):
            args += ["--tag", str(a["tag"])]
        if a.get("roll"):
            args += ["--roll", str(int(a["roll"]))]
        if a.get("seed") is not None:
            args += ["--seed", str(int(a["seed"]))]
        for s in (a.get("adopt") or []):
            args += ["--adopt", str(s)]
        if a.get("check"):
            args.append("--check")
        if a.get("unanswered"):
            args.append("--unanswered")
        if a.get("stats"):
            args.append("--stats")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code not in (0, 1))

    # ── 交付体检 ──────────────────────────────────────────────
    if name == "pangu_review":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["review", str(w), "--json"]
        if a.get("fast"):
            args.append("--fast")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code not in (0, 1))

    # ── 反事实推演 ────────────────────────────────────────────
    if name == "pangu_whatif":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["whatif", str(w), "--json"]
        for s in (a.get("set") or []):
            args += ["--set", str(s)]
        for s in (a.get("scale") or []):
            args += ["--scale", str(s)]
        if a.get("recalc"):
            args.append("--recalc")
        if a.get("write"):
            args += ["--write", str(a["write"]), "--yes"]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 观测层 ────────────────────────────────────────────────
    if name == "pangu_sky":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["sky", str(w)]
        if a.get("at"):
            args += ["--at", str(a["at"])]
        if a.get("lat") is not None:
            args += ["--lat", str(a["lat"])]
        if a.get("year"):
            args.append("--year")
        if a.get("allnight"):
            args.append("--allnight")
        if a.get("check"):
            args.append("--check")
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 基准 / 承载力 ──────────────────────────────────────────
    if name == "pangu_benchmark":
        args = ["benchmark", str(a.get("target") or "earth")]
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    if name == "pangu_capacity":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["capacity", str(w)]
        if a.get("harvest") is not None:
            args += ["--harvest", str(a["harvest"])]
        if a.get("write"):
            args.append("--write")
        if a.get("yes"):
            args.append("--yes")
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 必然推论 ──────────────────────────────────────────────
    if name == "pangu_entail":
        if a.get("list"):
            code, out, err = _run_cli(["entail", "--list"])
            return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["entail", str(w)]
        if a.get("only"):
            args += ["--only", str(a["only"])]
        if a.get("exclude"):
            args += ["--exclude", str(a["exclude"])]
        if a.get("write"):
            args.append("--write")
        if a.get("write") and a.get("yes"):
            args.append("--yes")
        if a.get("check"):
            args.append("--check")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code not in (0, 1))

    # ── 编年史 ──────────────────────────────────────────────
    if name == "pangu_chronicle":
        if a.get("list"):
            code, out, err = _run_cli(["chronicle", "--list"])
            return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["chronicle", str(w)]
        if a.get("seed") is not None:
            args += ["--seed", str(int(a["seed"]))]
        if a.get("from_year") is not None:
            args += ["--from-year", str(int(a["from_year"]))]
        if a.get("to_year") is not None:
            args += ["--to-year", str(int(a["to_year"]))]
        if a.get("kind"):
            args += ["--kind", str(a["kind"])]
        if a.get("write"):
            args.append("--write")
        if a.get("write") and a.get("yes"):
            args.append("--yes")
        if a.get("check"):
            args.append("--check")
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code not in (0, 1))

    return _result(f"未知工具：{name}", True)


# ════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 over stdio
# ════════════════════════════════════════════════════════════════════

def _send(obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def _ok(mid, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": mid, "result": result})


def _err(mid, code: int, message: str, data=None) -> None:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    _send({"jsonrpc": "2.0", "id": mid, "error": e})


def _handle(msg: dict) -> None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    is_notification = "id" not in msg

    # ── 握手 ─────────────────────────────────────────────────
    if method == "initialize":
        want = params.get("protocolVersion")
        ver = want if want in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        _ok(mid, {
            "protocolVersion": ver,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "盘古造世引擎。造世界前先调用 pangu_guide 读方法论；"
                "**每一轮先调 pangu_plan** 看自己在第几斧、缺什么、下一步跑什么；"
                "想不出设定时用 pangu_options 抽选项卡（每个选项都带代价与痕迹），"
                "立完律后用 pangu_entail 把设定推成居民看得见的现象。"
                "然后用 pangu_init 建骨架、逐步填充 world.json、pangu_validate --brief 复检、"
                "pangu_map 推演行星地图、pangu_ca 跑生态演化、pangu_preview 出 3D、"
                "pangu_export 出档案。改设定用 pangu_patch（自动升版本记修订），"
                "扫参数用 pangu_sweep，比版本用 pangu_diff。"
            ),
        })
        return

    if method in ("notifications/initialized", "initialized"):
        return                      # 通知，无需响应

    if method in ("notifications/cancelled", "notifications/roots/list_changed",
                  "notifications/progress", "$/cancelRequest"):
        return

    if method == "ping":
        _ok(mid, {})
        return

    if method == "tools/list":
        _ok(mid, {"tools": TOOLS})
        return

    if method == "tools/call":
        if is_notification:
            return
        tname = params.get("name")
        targs = params.get("arguments") or {}
        if not isinstance(targs, dict):
            _err(mid, -32602, "arguments 必须是对象")
            return
        try:
            _ok(mid, _call_tool(tname, targs))
        except Exception as e:  # noqa: BLE001
            _log(f"tool {tname} 异常：{e}")
            _ok(mid, _result(f"工具执行失败：{type(e).__name__}: {e}", True))
        return

    if method in ("resources/list", "prompts/list"):
        _ok(mid, {"resources": []} if method == "resources/list" else {"prompts": []})
        return

    if method == "logging/setLevel":
        return

    if is_notification:
        return
    _err(mid, -32601, f"Method not found: {method}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    _log(f"启动 · root={ROOT} · python={sys.version.split()[0]}")
    if not os.path.exists(CLI):
        _log(f"警告：找不到 CLI {CLI}")

    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _err(None, -32700, "Parse error")
            continue

        if isinstance(msg, list):
            for m in msg:
                if isinstance(m, dict):
                    _handle(m)
            continue
        if isinstance(msg, dict):
            _handle(msg)
        else:
            _err(None, -32600, "Invalid Request")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except BrokenPipeError:
        sys.exit(0)
