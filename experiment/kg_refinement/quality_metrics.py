#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quality Metrics — KG 构建质量评估

评估 Algorithm 1 (Baseline) 和 Algorithm 2 (Graph-Centric) 的构建质量差异。

指标设计原则:
- Entity Duplication Rate: 客观可数 (同一实体被创建为多个节点的比例)
- Relation Precision: 外部判断 (随机抽样写入的关系，对照 Gold Standard)
- Relation Recall: MDR 定义分母 (硬约束要求的关系中被补齐的比例)
- Gap Coverage: 客观可数 (required_missing 中后续被补上的比例)
- Conflict Detected: Algorithm 1 为 0 (它没有检测机制)
- Validation Pass Rate: 衡量数据源质量，不作为算法质量指标

@author: jingwen.wu
"""
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass

# 路径设置：直接导入同目录模块，绕开 experiment 包初始化
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from graph_constructor import (
    InMemoryKG, IncrementalKGConstructor, BaselineConstructor,
    KGNode, KGEdge,
)
from esp_derive import (
    get_required_relations, get_optional_relations,
    Cardinality, ONTOLOGY_SCHEMA,
)


# ============================================================
# 1. 指标数据结构
# ============================================================

@dataclass
class QualityReport:
    """
    质量评估报告
    
    Attributes:
        method: 方法名 ("algorithm_1" / "algorithm_2" / ablation 变体)
        entity_metrics: 实体级指标
        relation_metrics: 关系级指标
        gap_metrics: 缺口级指标
        conflict_metrics: 冲突级指标
        summary: 汇总对比
    """
    method: str
    entity_metrics: Dict[str, Any]
    relation_metrics: Dict[str, Any]
    gap_metrics: Dict[str, Any]
    conflict_metrics: Dict[str, Any]
    summary: Dict[str, Any]


# ============================================================
# 2. 实体质量指标
# ============================================================

def compute_entity_metrics(kg: InMemoryKG) -> Dict[str, Any]:
    """
    计算实体质量指标
    
    核心指标:
    - entity_count: 总节点数
    - unique_entities: 去重后的唯一实体数 (按 (type, value) 去重)
    - duplication_rate: 重复率 = 1 - unique / total
    - entities_by_type: 按类型分布
    - multi_source_entities: 在多个文件中出现的实体数 (Algorithm 2 的 Resolve 效果)
    
    Args:
        kg: InMemoryKG 实例
    
    Returns:
        指标字典
    """
    total = kg.node_count()
    if total == 0:
        return {
            "entity_count": 0,
            "unique_entities": 0,
            "duplication_rate": 0.0,
            "entities_by_type": {},
            "multi_source_entities": 0,
        }

    # 按 (type, value) 去重
    unique_set: Set[Tuple[str, str]] = set()
    type_counter = Counter()
    multi_source = 0

    for node in kg.nodes.values():
        unique_set.add((node.entity_type, node.value))
        type_counter[node.entity_type] += 1
        if len(node.source_files) > 1:
            multi_source += 1

    unique_count = len(unique_set)
    dup_rate = 1.0 - (unique_count / total) if total > 0 else 0.0

    return {
        "entity_count": total,
        "unique_entities": unique_count,
        "duplication_rate": round(dup_rate, 4),
        "entities_by_type": dict(type_counter.most_common()),
        "multi_source_entities": multi_source,
    }


# ============================================================
# 3. 关系质量指标
# ============================================================

def compute_relation_metrics(kg: InMemoryKG,
                             gold_edges: List[Tuple[str, str, str]] = None
                             ) -> Dict[str, Any]:
    """
    计算关系质量指标
    
    核心指标:
    - edge_count: 总边数
    - edges_by_relation: 按关系类型分布
    - gold_precision: 对照 Gold Standard 的准确率 (如果提供)
    - gold_recall: 对照 Gold Standard 的召回率 (如果提供)
    
    注意: 没有 Gold Standard 时，precision 基于 ValidateMDR 通过率，
    但这是"自证"指标，仅供参考。论文中应使用人工抽样。
    
    Args:
        kg: InMemoryKG 实例
        gold_edges: Gold Standard 边列表 [(source_value, relation, target_value), ...]
    
    Returns:
        指标字典
    """
    total_edges = kg.edge_count()
    rel_counter = Counter()

    for edge in kg.edges:
        rel_counter[edge.relation] += 1

    result = {
        "edge_count": total_edges,
        "edges_by_relation": dict(rel_counter.most_common()),
    }

    # 如果有 Gold Standard，计算 P/R
    if gold_edges is not None:
        gold_set = set(gold_edges)

        # 构建 KG 边集合 (使用 value 而非 node_id 进行比对)
        kg_edge_set: Set[Tuple[str, str, str]] = set()
        for edge in kg.edges:
            src_node = kg.nodes.get(edge.source_id)
            tgt_node = kg.nodes.get(edge.target_id)
            if src_node and tgt_node:
                kg_edge_set.add((src_node.value, edge.relation, tgt_node.value))

        # Precision: KG 中多少边是正确的
        if kg_edge_set:
            correct = len(kg_edge_set & gold_set)
            precision = correct / len(kg_edge_set)
        else:
            correct = 0
            precision = 0.0

        # Recall: Gold 中多少边被 KG 覆盖
        if gold_set:
            recall = correct / len(gold_set)
        else:
            recall = 0.0

        # F1
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        result.update({
            "gold_edges_count": len(gold_set),
            "correct_edges": correct,
            "gold_precision": round(precision, 4),
            "gold_recall": round(recall, 4),
            "gold_f1": round(f1, 4),
        })

    return result


# ============================================================
# 4. 缺口覆盖指标
# ============================================================

def compute_gap_metrics(kg: InMemoryKG) -> Dict[str, Any]:
    """
    计算缺口覆盖指标
    
    核心指标:
    - total_required: 所有实体的必需关系总数
    - fulfilled: 已满足的必需关系数
    - gap_coverage: 覆盖率 = fulfilled / total_required
    - gaps_by_type: 按实体类型的缺口分布
    
    定义:
    - required_missing 来自 MDR 硬约束 (κ=EXACTLY_ONE / AT_LEAST_ONE)
    - 已满足 = 该关系至少有一条边
    
    Args:
        kg: InMemoryKG 实例
    
    Returns:
        指标字典
    """
    total_required = 0
    fulfilled = 0
    gaps_by_type = defaultdict(lambda: {"required": 0, "fulfilled": 0, "missing": []})

    # 对每个节点检查必需关系
    for node in kg.nodes.values():
        required = get_required_relations(node.entity_type)
        if not required:
            continue

        # 获取该节点已有的关系类型
        existing_rels = set()
        for edge in kg.edges:
            if edge.source_id == node.node_id:
                existing_rels.add(edge.relation)

        for rel in required:
            total_required += 1
            gaps_by_type[node.entity_type]["required"] += 1

            if rel.relation in existing_rels:
                fulfilled += 1
                gaps_by_type[node.entity_type]["fulfilled"] += 1
            else:
                gaps_by_type[node.entity_type]["missing"].append(rel.relation)

    coverage = fulfilled / total_required if total_required > 0 else 0.0

    # 简化 gaps_by_type 输出
    gaps_summary = {}
    for etype, data in gaps_by_type.items():
        missing_counter = Counter(data["missing"])
        gaps_summary[etype] = {
            "required": data["required"],
            "fulfilled": data["fulfilled"],
            "coverage": round(data["fulfilled"] / data["required"], 4)
            if data["required"] > 0 else 0.0,
            "top_missing": missing_counter.most_common(5),
        }

    return {
        "total_required": total_required,
        "fulfilled": fulfilled,
        "gap_coverage": round(coverage, 4),
        "gaps_by_type": gaps_summary,
    }


# ============================================================
# 5. 冲突指标
# ============================================================

def compute_conflict_metrics(kg: InMemoryKG) -> Dict[str, Any]:
    """
    计算冲突指标
    
    核心指标:
    - conflict_detected: 检测到的冲突数 (衡量检测能力)
    - conflicts_by_relation: 按关系类型分布
    - conflicts_by_entity_type: 按实体类型分布
    
    注意:
    - Algorithm 1 的 conflict_detected = 0 (它没有检测机制)
    - 这不代表 Algorithm 1 没有冲突，而是它无法检测
    - conflict_detected 越高说明检测能力越强
    
    Args:
        kg: InMemoryKG 实例
    
    Returns:
        指标字典
    """
    total = len(kg.conflicts)
    rel_counter = Counter()
    type_counter = Counter()

    for c in kg.conflicts:
        rel_counter[c.relation] += 1
        # 从 entity_id 提取类型
        entity_type = c.entity_id.split("::")[0] if "::" in c.entity_id else "unknown"
        type_counter[entity_type] += 1

    return {
        "conflict_detected": total,
        "conflicts_by_relation": dict(rel_counter.most_common()),
        "conflicts_by_entity_type": dict(type_counter.most_common()),
    }


# ============================================================
# 6. 综合对比
# ============================================================

def compare_algorithms(algo2_kg: InMemoryKG,
                       algo1_kg: InMemoryKG,
                       gold_edges: List[Tuple[str, str, str]] = None,
                       algo2_label: str = "Algorithm 2",
                       algo1_label: str = "Algorithm 1") -> Dict[str, Any]:
    """
    综合对比两个算法的质量
    
    Args:
        algo2_kg: Algorithm 2 构建的 KG
        algo1_kg: Algorithm 1 构建的 KG
        gold_edges: Gold Standard (可选)
        algo2_label: Algorithm 2 的标签
        algo1_label: Algorithm 1 的标签
    
    Returns:
        对比报告
    """
    # 分别计算各项指标
    a2_entity = compute_entity_metrics(algo2_kg)
    a1_entity = compute_entity_metrics(algo1_kg)

    a2_relation = compute_relation_metrics(algo2_kg, gold_edges)
    a1_relation = compute_relation_metrics(algo1_kg, gold_edges)

    a2_gap = compute_gap_metrics(algo2_kg)
    a1_gap = compute_gap_metrics(algo1_kg)

    a2_conflict = compute_conflict_metrics(algo2_kg)
    a1_conflict = compute_conflict_metrics(algo1_kg)

    # 构建对比表
    comparison = {
        "entity": {
            "metric": "Entity Duplication Rate",
            algo1_label: a1_entity["duplication_rate"],
            algo2_label: a2_entity["duplication_rate"],
            "delta": round(a2_entity["duplication_rate"]
                           - a1_entity["duplication_rate"], 4),
            "note": "lower is better",
        },
        "node_count": {
            "metric": "Node Count",
            algo1_label: a1_entity["entity_count"],
            algo2_label: a2_entity["entity_count"],
            "delta": a2_entity["entity_count"] - a1_entity["entity_count"],
            "note": "lower is better (fewer duplicates)",
        },
        "edge_count": {
            "metric": "Edge Count",
            algo1_label: a1_relation["edge_count"],
            algo2_label: a2_relation["edge_count"],
            "delta": a2_relation["edge_count"] - a1_relation["edge_count"],
        },
        "gap_coverage": {
            "metric": "Gap Coverage (Hard Constraints)",
            algo1_label: a1_gap["gap_coverage"],
            algo2_label: a2_gap["gap_coverage"],
            "delta": round(a2_gap["gap_coverage"]
                           - a1_gap["gap_coverage"], 4),
            "note": "higher is better",
        },
        "conflict_detected": {
            "metric": "Conflicts Detected",
            algo1_label: a1_conflict["conflict_detected"],
            algo2_label: a2_conflict["conflict_detected"],
            "delta": a2_conflict["conflict_detected"]
                     - a1_conflict["conflict_detected"],
            "note": "detection capability (Algorithm 1 = 0 by design)",
        },
        "multi_source": {
            "metric": "Multi-source Entities (Cross-file Links)",
            algo1_label: a1_entity["multi_source_entities"],
            algo2_label: a2_entity["multi_source_entities"],
            "delta": a2_entity["multi_source_entities"]
                     - a1_entity["multi_source_entities"],
            "note": "higher is better (shows Resolve effectiveness)",
        },
    }

    # 添加 Gold Standard 指标 (如果有)
    if gold_edges is not None:
        comparison["gold_precision"] = {
            "metric": "Relation Precision (vs Gold)",
            algo1_label: a1_relation.get("gold_precision", "N/A"),
            algo2_label: a2_relation.get("gold_precision", "N/A"),
            "delta": round(
                a2_relation.get("gold_precision", 0)
                - a1_relation.get("gold_precision", 0), 4
            ) if isinstance(a2_relation.get("gold_precision"), float) else "N/A",
        }
        comparison["gold_recall"] = {
            "metric": "Relation Recall (vs Gold)",
            algo1_label: a1_relation.get("gold_recall", "N/A"),
            algo2_label: a2_relation.get("gold_recall", "N/A"),
            "delta": round(
                a2_relation.get("gold_recall", 0)
                - a1_relation.get("gold_recall", 0), 4
            ) if isinstance(a2_relation.get("gold_recall"), float) else "N/A",
        }
        comparison["gold_f1"] = {
            "metric": "Relation F1 (vs Gold)",
            algo1_label: a1_relation.get("gold_f1", "N/A"),
            algo2_label: a2_relation.get("gold_f1", "N/A"),
            "delta": round(
                a2_relation.get("gold_f1", 0)
                - a1_relation.get("gold_f1", 0), 4
            ) if isinstance(a2_relation.get("gold_f1"), float) else "N/A",
        }

    return {
        "comparison_table": comparison,
        "details": {
            algo2_label: {
                "entity": a2_entity,
                "relation": a2_relation,
                "gap": a2_gap,
                "conflict": a2_conflict,
            },
            algo1_label: {
                "entity": a1_entity,
                "relation": a1_relation,
                "gap": a1_gap,
                "conflict": a1_conflict,
            },
        },
    }


def format_comparison_table(report: Dict[str, Any]) -> str:
    """
    将对比报告格式化为可读表格
    
    Args:
        report: compare_algorithms() 的返回值
    
    Returns:
        格式化的表格字符串
    """
    lines = []
    table = report["comparison_table"]

    # 确定列名
    keys = list(table.keys())
    if not keys:
        return "No comparison data"

    first = table[keys[0]]
    col_names = [k for k in first.keys() if k not in ("metric", "note")]

    # Header
    header = f"{'Metric':<40}"
    for col in col_names:
        header += f"{col:>15}"
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for key, row in table.items():
        line = f"{row['metric']:<40}"
        for col in col_names:
            val = row.get(col, "")
            if isinstance(val, float):
                line += f"{val:>15.4f}"
            else:
                line += f"{str(val):>15}"
        if row.get("note"):
            line += f"  ({row['note']})"
        lines.append(line)

    return "\n".join(lines)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    from graph_constructor import (
        IncrementalKGConstructor, BaselineConstructor, DataRecord,
    )

    print("=" * 60)
    print("Quality Metrics — Unit Test")
    print("=" * 60)

    # 构造测试数据
    test_vd = {
        "Strand": ["+", "-"],
        "Chromosome": [f"Chr{i:02d}" for i in range(1, 13)],
    }

    records = [
        DataRecord("LOC_Os01g12345", "Gene",
                    [("chrom", "Chr01"), ("start", "1000"),
                     ("end", "5000"), ("strand", "+")],
                    "bed_gene", "file1.bed", "Nipponbare"),
        DataRecord("LOC_Os01g12345", "Gene",  # 重复
                    [("leaf_value", "Expr_leaf_01")],
                    "fpkm_expression", "file2.csv", "Nipponbare"),
        DataRecord("LOC_Os03g67890", "Gene",
                    [("chrom", "Chr03"), ("start", "20000"),
                     ("end", "25000"), ("strand", "-")],
                    "bed_gene", "file1.bed", "Nipponbare"),
    ]

    # Algorithm 2
    a2 = IncrementalKGConstructor(vd=test_vd)
    a2.process_batch(records[:2], "bed_gene", "file1.bed")
    a2.process_batch(records[1:2], "fpkm_expression", "file2.csv")
    a2.process_batch(records[2:], "bed_gene", "file1.bed")

    # Algorithm 1
    a1 = BaselineConstructor()
    a1.process_batch(records[:2], "bed_gene", "file1.bed")
    a1.process_batch(records[1:2], "fpkm_expression", "file2.csv")
    a1.process_batch(records[2:], "bed_gene", "file1.bed")

    # 对比
    report = compare_algorithms(a2.kg, a1.kg)
    print("\n" + format_comparison_table(report))

    # 详细指标
    print("\n--- Algorithm 2 Gap Details ---")
    gap = compute_gap_metrics(a2.kg)
    for etype, data in gap["gaps_by_type"].items():
        print(f"  {etype}: coverage={data['coverage']}, "
              f"missing={data['top_missing']}")
