---
trigger: model_decision
description: 盘古造世引擎。造世界/宇宙/星球法则、设计非地球物理、审查设定自洽性、生成 3D 星球预览时使用。
---

# 盘古 · 造世引擎（Windsurf 入口）

用户提出**世界构建 / 宇宙设定 / 星球物理 / 自洽性审查 / 3D 星球预览**类需求时：

1. 读取 `{{PANGU_ROOT}}/SKILL.md` 全文。
2. 按其指引按需加载 `{{PANGU_ROOT}}/references/` 下的文档（不要全量读）。
3. 调用脚本：

```bash
python "{{PANGU_ROOT}}/scripts/pangu.py" doctor
python "{{PANGU_ROOT}}/scripts/pangu.py" init --name "世界名" --seed "种子" --out ./out/world.json
python "{{PANGU_ROOT}}/scripts/pangu.py" validate ./out/world.json --fix-hint
python "{{PANGU_ROOT}}/scripts/pangu.py" preview ./out/world.json -o ./out/preview.html
python "{{PANGU_ROOT}}/scripts/pangu.py" export ./out/world.json --md ./out/世界档案.md
```

## 硬约束

- 先立律后长物：物理层未定稿，不谈生物与文明。
- 三律：逆行、代价、痕迹，缺一不可。
- `world.json` 是唯一数据源，生成物禁止手改。
- 产物写 `./out/<世界id>/`，不写进技能目录。

`{{PANGU_ROOT}}` 未被替换时，先向用户确认盘古目录位置。
