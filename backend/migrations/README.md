# 数据表初始化

本版通过 `src.models.base.ensure_schema()` 创建首次运行所需的七张表，并为既有库的 `analysis_runs` 补齐 `method`、`assignment_ids`、`last_assignment_id` 三列；既有分析回填为 `v1`，仍按原完全随机方法查看和运行。模型在 `src/models/workflow.py`。`python -m scripts.seed_demo` 按观测内容键补全演示样本，并为尚无分派记录的班组补登首轮分派，不覆盖已录入数据、分析及签核。数据库端口只发布到本机。
