# 作文因材施教（addon MVP）

第一个市场模块，复用 `harness` 的多角色辩论、验证与 `evolution` 的自进化能力。

## 当前能力

- `register(scene_config, hooks)` 已注册场景 `composition`
- 压缩版硬契约：≤400 字，必须含 结论/理由/下一步/止损
- 钩子：报告准备、压缩、反馈回写 Hebbian、进化喂料
- `review_essay(essay, students, ai_client)`：基于作文原文与学生画像，生成 学生版/家长版/老师版/专家版/成长版 五版差异化反馈
- 五版结果自动归一化，缺失版本兜底为“待补充”，不静默丢弃

## 下一步

- 作文库/范文库/错题库入库（`data_vault`）
- 五版报告与成长轨迹联动
- 成长轨迹存储与可视化
