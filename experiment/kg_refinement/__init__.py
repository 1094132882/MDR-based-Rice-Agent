# experiment/kg_refinement — Graph-Centric Incremental KG Construction (Algorithm 2)
#
# Files:
#   esp_derive.py         - MDR hard constraints, ontology schema, cardinality rules
#   graph_constructor.py  - Core: incremental loop + Resolve + GetContext + ValidateMDR
#   quality_metrics.py    - Metrics: Entity Dup, Relation P/R, Gap Coverage, Conflict
#   run_incremental.py    - Experiment runner: Neo4j export, Algo1 vs Algo2, ablation
#
# Usage:
#   python -m experiment.kg_refinement.run_incremental --dry-run --max-genes 20
#   python -m experiment.kg_refinement.run_incremental --max-genes 100 --ablation
#
# 文件结构:
#   esp_derive.py         - MDR 硬约束、本体 Schema、基数规则、文件类型映射
#   graph_constructor.py  - 核心：增量构建主循环 + Resolve + GetContext + ValidateMDR
#   quality_metrics.py    - 质量度量：Entity Dup, Relation P/R, Gap Coverage, Conflict
#   run_incremental.py    - 实验入口：Neo4j 数据导出、Algorithm 1 vs 2 对比、消融
#
# 使用方式:
#   python -m experiment.kg_refinement.run_incremental --dry-run --max-genes 20
#   python -m experiment.kg_refinement.run_incremental --max-genes 100 --ablation
