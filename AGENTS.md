# 盘古 · 造世引擎（通用 agent 指令）

> 本文件是给「只认 `AGENTS.md` 的 harness」用的入口（Codex、Amp、Jules、以及大部分 IDE agent）。
> 它**不是**技能正文，只是指针 + 作业约定。正文在 `SKILL.md`。

## 这是什么

一套把「架空世界」当工程项目来做的工具：先立宇宙底层法则（数学/物理/化学/生物），再严格推导出星体、地形、气候、生态与文明，最后输出结构化数据、自洽性审查报告、行星地图和可交互 3D 预览。

## 何时触发

用户提出下列任一意图时，**先读 `SKILL.md` 全文**，再动手：

- 造一个世界 / 宇宙 / 星球，设计其物理法则
- "如果重力反过来会怎样""没有太阳怎么活""双恒星世界""三倍地球大"
- 给小说 / 游戏 / 剧本做底层宇宙设定
- 审查一个已有设定是否自洽
- 生成可旋转的 3D 星球预览

## 怎么用

```bash
python scripts/pangu.py doctor                     # 环境自检，先跑这个
python scripts/pangu.py init --name "世界名" --seed "一句话种子" --out out/world.json
python scripts/pangu.py validate out/world.json --fix-hint
python scripts/pangu.py preview out/world.json -o out/preview.html
python scripts/pangu.py export out/world.json --md out/世界档案.md
python scripts/pangu.py axioms --domain physics --roll 3
python scripts/pangu.py slice out/world.json      # 第一人称切片体检
python scripts/pangu.py redteam out/world.json --check
python scripts/pangu.py map out/world.json --run --write --yes   # 行星地图：板块/海平面/气候/河网/群系
python scripts/pangu.py ca out/world.json --check  # 生态演化：同 seed 复算比对
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

## 三律（灵魂）

- **逆行律**：至少一个底层维度与地球直觉明确相反
- **代价律**：每条反常识都要付出可量化的代价
- **痕迹律**：代价必须在居民抬头能看见的地方留下痕迹

没有代价的奇观是意淫，有代价的奇观才是世界。

## 更多

- 七斧流程与提问脚本：`references/七斧创世法.md`
- 60+ 条反常识积木：`references/公理库.md`
- 检索配方：`references/检索与灵感策略.md`
- 五维十六问审查：`references/自洽性审查协议.md`
- 数据结构：`references/world-schema.md`
- 完整示例：`examples/helikon/`
