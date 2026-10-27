# GEMINI.md · 盘古造世引擎入口

本项目接入了「盘古」造世引擎（技能根：`{{PANGU_ROOT}}`）。

## 触发条件

当用户请求涉及：造一个世界 / 宇宙 / 星球并设计其底层法则；"如果重力反过来""没有太阳的世界""双恒星""三倍地球大"；给小说游戏做宇宙设定；审查架空设定是否自洽；生成 3D 星球预览 —— 启用本技能。

## 加载顺序

1. 读 `{{PANGU_ROOT}}/SKILL.md`（正文，必须完整）。
2. 按正文点名读 `{{PANGU_ROOT}}/references/*.md`，一次一份，不要全量加载。
3. 执行脚本（绝对路径，避免 cwd 差异）：

```bash
python "{{PANGU_ROOT}}/scripts/pangu.py" doctor
python "{{PANGU_ROOT}}/scripts/pangu.py" validate <world.json> --json
```

## 核心纪律

| 纪律 | 含义 |
|---|---|
| 先立律，后长物 | 物理层定稿前不许谈生物与文明 |
| 三律 | 逆行律 + 代价律 + 痕迹律 |
| 单一数据源 | 只改 `world.json`，`preview.html` 与世界档案都是生成物 |
| 有 fatal 不交付 | `validate --strict` 非零退出必须先修 |

## 交付物

`world.json`（数据）、`preview.html`（3D）、`世界档案.md`（阅读）、审查结论（含评分与修补记录）。

仅依赖 Python ≥3.9 标准库，无需安装第三方包。
