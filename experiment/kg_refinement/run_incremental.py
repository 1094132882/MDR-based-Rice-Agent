#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Incremental — 增量构建实验入口

从 Neo4j 导出数据 → 分批模拟 → 对比 Algorithm 1 vs Algorithm 2 → 输出结果。

实验流程:
1. 连接 Neo4j，导出指定品种的基因数据 (模拟 D = {d₁, ..., dₙ})
2. 将数据分成多个批次 (模拟不同数据文件)
3. 分别用 Algorithm 1 和 Algorithm 2 处理这些批次
4. 对比构建质量 (Entity Dup, Relation P/R, Gap Coverage, Conflict)
5. 跑消融实验 (no-resolve, no-validate, no-gap)

使用方式:
    # 完整实验
    python run_incremental.py --accession Nipponbare --max-genes 100

    # 快速测试
    python run_incremental.py --max-genes 10 --dry-run

    # 消融实验
    python run_incremental.py --max-genes 50 --ablation

@author: jingwen.wu
"""
import argparse
import json
import os
import sys
import time
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# ── 路径设置（兼容多种运行方式）──────────────────────────────
# 支持:
#   1. cd ~/xrb/rice_mdr1 && python experiment/kg_refinement/run_incremental.py
#   2. cd ~/xrb/rice_mdr1/experiment && python kg_refinement/run_incremental.py
#   3. cd ~/xrb/rice_mdr1/experiment/kg_refinement && python run_incremental.py
#
# 把 kg_refinement 目录加入 sys.path，直接导入同目录模块
# 绕开 experiment 包的初始化（避免 tools/__init__.py 的循环导入）
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph_constructor import (
    IncrementalKGConstructor,
    BaselineConstructor,
    DataRecord,
)
from quality_metrics import (
    compare_algorithms,
    format_comparison_table,
    compute_entity_metrics,
    compute_relation_metrics,
    compute_gap_metrics,
    compute_conflict_metrics,
)
from esp_derive import (
    FILE_TYPE_SCHEMAS,
    derive_esp_report,
)


# ============================================================
# 1. Neo4j 数据导出
# ============================================================

def get_neo4j_connection():
    """
    获取 Neo4j 连接

    Returns:
        Neo4jGraph 实例或 None
    """
    try:
        from methods.s_cot_raps.config import Config
        try:
            from langchain_neo4j import Neo4jGraph
        except ImportError:
            from langchain_community.graphs import Neo4jGraph

        graph = Neo4jGraph(
            url=Config.NEO4J_URI,
            username=Config.NEO4J_USERNAME,
            password=Config.NEO4J_PASSWORD,
            refresh_schema=False,
        )
        graph.query("RETURN 1 as test")
        print(f"[Neo4j] Connected to {Config.NEO4J_URI}")
        return graph
    except Exception as e:
        print(f"[Neo4j] Connection failed: {e}")
        return None


def export_gene_data(graph, accession: str = "Nipponbare",
                     max_genes: int = 100) -> List[DataRecord]:
    """
    从 Neo4j 导出基因数据，构建 DataRecord 列表
    
    模拟 BED 文件格式：每条记录包含 gene, chromosome, start, end, strand
    
    Args:
        graph: Neo4j 连接
        accession: 品种名
        max_genes: 最大基因数
    
    Returns:
        DataRecord 列表
    """
    print(f"\n[Export] Querying genes for accession='{accession}', max={max_genes}...")

    query = """
    MATCH (g:Gene)-[:type]->(a:Accession {name: $accession})
    OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
    OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
    OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
    OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
    RETURN g.name AS gene_name,
           c.name AS chromosome,
           sp.name AS start_pos,
           ep.name AS end_pos,
           st.name AS strand
    LIMIT $limit
    """

    results = graph.query(query, {"accession": accession, "limit": max_genes})
    print(f"[Export] Retrieved {len(results)} genes")

    records = []
    for r in results:
        gene_name = r.get("gene_name")
        if not gene_name:
            continue

        fields = []
        if r.get("chromosome"):
            fields.append(("chrom", r["chromosome"]))
        if r.get("start_pos"):
            fields.append(("start", r["start_pos"]))
        if r.get("end_pos"):
            fields.append(("end", r["end_pos"]))
        if r.get("strand"):
            fields.append(("strand", r["strand"]))

        records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=fields,
            file_type="bed_gene",
            file_name=f"{accession}_genes.bed",
            accession=accession,
        ))

    return records


def export_expression_data(graph, accession: str = "Nipponbare",
                           max_genes: int = 100) -> List[DataRecord]:
    """
    从 Neo4j 导出表达量数据

    模拟 FPKM 文件格式
    """
    print(f"[Export] Querying expression for accession='{accession}'...")

    query = """
    MATCH (g:Gene)-[:type]->(a:Accession {name: $accession})
    MATCH (g)-[:measures_gene_expression]->(e:Expression)
    RETURN g.name AS gene_name,
           e.leaf_value AS leaf,
           e.root_value AS root,
           e.young_ear_value AS young_ear
    LIMIT $limit
    """

    results = graph.query(query, {"accession": accession, "limit": max_genes})
    print(f"[Export] Retrieved {len(results)} expression records")

    records = []
    for r in results:
        gene_name = r.get("gene_name")
        if not gene_name:
            continue

        fields = []
        if r.get("leaf"):
            fields.append(("leaf_value", str(r["leaf"])))

        if fields:
            records.append(DataRecord(
                entity_key=gene_name,
                entity_type="Gene",
                fields=fields,
                file_type="fpkm_expression",
                file_name=f"{accession}_fpkm.csv",
                accession=accession,
            ))

    return records


def export_homolog_data(graph, accession_a: str = "Nipponbare",
                        accession_b: str = "9311",
                        max_pairs: int = 50) -> List[DataRecord]:
    """
    从 Neo4j 导出 RBH 同源关系数据

    模拟 RBH 文件格式
    """
    print(f"[Export] Querying RBH between '{accession_a}' and '{accession_b}'...")

    query = """
    MATCH (g1:Gene)-[:type]->(a1:Accession {name: $acc_a})
    MATCH (g1)-[:RBH]->(g2:Gene)-[:type]->(a2:Accession {name: $acc_b})
    RETURN g1.name AS query_gene, g2.name AS subject_gene
    LIMIT $limit
    """

    results = graph.query(query, {
        "acc_a": accession_a, "acc_b": accession_b, "limit": max_pairs
    })
    print(f"[Export] Retrieved {len(results)} RBH pairs")

    records = []
    for r in results:
        gene_a = r.get("query_gene")
        gene_b = r.get("subject_gene")
        if not gene_a or not gene_b:
            continue

        records.append(DataRecord(
            entity_key=gene_a,
            entity_type="Gene",
            fields=[("subject_gene", gene_b)],
            file_type="rbh_homolog",
            file_name=f"{accession_a}_vs_{accession_b}_RBH.txt",
        ))

    return records


def export_function_data(graph, accession: str = "Nipponbare",
                         max_genes: int = 50) -> List[DataRecord]:
    """
    从 Neo4j 导出功能注释数据
    """
    print(f"[Export] Querying functions for accession='{accession}'...")

    query = """
    MATCH (g:Gene)-[:type]->(a:Accession {name: $accession})
    MATCH (g)-[:has_a_function]->(f:Function)
    RETURN g.name AS gene_name, f.name AS function_desc
    LIMIT $limit
    """

    results = graph.query(query, {"accession": accession, "limit": max_genes})
    print(f"[Export] Retrieved {len(results)} function annotations")

    records = []
    for r in results:
        gene_name = r.get("gene_name")
        func = r.get("function_desc")
        if not gene_name or not func:
            continue

        records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=[("function", func)],
            file_type="function_annotation",
            file_name=f"{accession}_functions.tsv",
        ))

    return records


def build_gold_standard(all_records: List[DataRecord]) -> List[Tuple[str, str, str]]:
    """
    从导出数据构建 Gold Standard
    
    Gold = 从 Neo4j 导出的完整关系集合
    
    Args:
        all_records: 所有导出的记录
    
    Returns:
        [(source_value, relation, target_value), ...]
    """
    from graph_constructor import infer_relation_type
    from esp_derive import get_range_type

    gold = set()
    for rec in all_records:
        for field_name, value in rec.fields:
            inferred = infer_relation_type(field_name, rec.file_type)
            if inferred:
                relation, _ = inferred
                gold.add((rec.entity_key, relation, value))

    return list(gold)


# ============================================================
# 2. 实验运行
# ============================================================

def run_experiment(batches: List[Tuple[List[DataRecord], str, str]],
                   vd: Dict[str, list],
                   mps: Dict[str, str],
                   gold_edges: List[Tuple[str, str, str]] = None,
                   run_ablation: bool = False) -> Dict[str, Any]:
    """
    运行完整实验
    
    Args:
        batches: [(records, file_type, file_name), ...]
        vd: 值域字典
        mps: 别名映射
        gold_edges: Gold Standard
        run_ablation: 是否跑消融
    
    Returns:
        实验结果
    """
    results = {}

    # ── Algorithm 2 (Full) ─────────────────────────────────
    print("\n" + "=" * 50)
    print("Running Algorithm 2 (Graph-Centric)...")
    print("=" * 50)

    a2 = IncrementalKGConstructor(vd=vd, mps=mps)
    t0 = time.time()
    for records, ftype, fname in batches:
        stats = a2.process_batch(records, ftype, fname)
        print(f"  [{fname}] entities={stats['entities']}, "
              f"edges={stats['edges_added']}, "
              f"conflicts={stats['edges_skipped_conflict']}")
    a2_time = time.time() - t0
    print(f"  Total time: {a2_time:.2f}s")
    results["algorithm_2"] = a2

    # ── Algorithm 1 (Baseline) ─────────────────────────────
    print("\n" + "=" * 50)
    print("Running Algorithm 1 (Baseline)...")
    print("=" * 50)

    a1 = BaselineConstructor()
    t0 = time.time()
    for records, ftype, fname in batches:
        stats = a1.process_batch(records, ftype, fname)
        print(f"  [{fname}] entities={stats['entities']}, "
              f"edges={stats['edges_added']}")
    a1_time = time.time() - t0
    print(f"  Total time: {a1_time:.2f}s")
    results["algorithm_1"] = a1

    # ── 消融实验 ───────────────────────────────────────────
    if run_ablation:
        ablation_configs = {
            "no_resolve": {"enable_resolve": False,
                           "enable_validate": True,
                           "enable_gap_detection": True},
            "no_validate": {"enable_resolve": True,
                            "enable_validate": False,
                            "enable_gap_detection": True},
            "no_gap": {"enable_resolve": True,
                       "enable_validate": True,
                       "enable_gap_detection": False},
        }

        for name, config in ablation_configs.items():
            print(f"\n--- Ablation: {name} ---")
            constructor = IncrementalKGConstructor(vd=vd, mps=mps, **config)
            for records, ftype, fname in batches:
                constructor.process_batch(records, ftype, fname)
            results[f"ablation_{name}"] = constructor

    # ── 计算指标 ───────────────────────────────────────────
    print("\n" + "=" * 50)
    print("Computing quality metrics...")
    print("=" * 50)

    comparison = compare_algorithms(
        a2.kg, a1.kg, gold_edges,
        algo2_label="Algorithm 2", algo1_label="Algorithm 1"
    )

    # 打印对比表
    print("\n" + format_comparison_table(comparison))

    # 消融对比
    ablation_results = {}
    if run_ablation:
        print("\n--- Ablation Results ---")
        for name in ["no_resolve", "no_validate", "no_gap"]:
            key = f"ablation_{name}"
            if key in results:
                abl_kg = results[key].kg
                abl_comparison = compare_algorithms(
                    abl_kg, a1.kg, gold_edges,
                    algo2_label=f"Ablation:{name}",
                    algo1_label="Algorithm 1"
                )
                ablation_results[name] = abl_comparison
                print(f"\n  [{name}]")
                entity_m = compute_entity_metrics(abl_kg)
                print(f"    Nodes: {entity_m['entity_count']}, "
                      f"Dup Rate: {entity_m['duplication_rate']}")

    return {
        "comparison": comparison,
        "ablation": ablation_results,
        "timing": {
            "algorithm_1": round(a1_time, 2),
            "algorithm_2": round(a2_time, 2),
        },
        "summary": {
            "algorithm_2": a2.get_summary(),
            "algorithm_1": a1.get_summary(),
        },
    }


# ============================================================
# 3. 结果保存
# ============================================================

def save_results(results: Dict[str, Any], output_dir: str):
    """保存实验结果"""
    os.makedirs(output_dir, exist_ok=True)

    # 保存 JSON 报告
    report_path = os.path.join(output_dir, "experiment_report.json")

    # 清理不可序列化的对象
    serializable = {
        "comparison": results["comparison"],
        "ablation": results.get("ablation", {}),
        "timing": results["timing"],
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[Save] Report saved to {report_path}")

    # 保存对比表 (CSV)
    csv_path = os.path.join(output_dir, "comparison_table.csv")
    table = results["comparison"]["comparison_table"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Header
        first_row = list(table.values())[0] if table else {}
        headers = list(first_row.keys())
        writer.writerow(headers)
        # Rows
        for row in table.values():
            writer.writerow([row.get(h, "") for h in headers])
    print(f"[Save] CSV saved to {csv_path}")

    # 保存可读文本报告
    txt_path = os.path.join(output_dir, "comparison_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("Algorithm 1 vs Algorithm 2 Comparison Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(format_comparison_table(results["comparison"]))
        f.write(f"\n\nTiming: Algo1={results['timing']['algorithm_1']}s, "
                f"Algo2={results['timing']['algorithm_2']}s\n")
    print(f"[Save] Text report saved to {txt_path}")


# ============================================================
# 4. 生成模拟数据 (离线模式，不需要 Neo4j)
# ============================================================

def generate_synthetic_data(num_genes: int = 20) -> Tuple[
    List[Tuple[List[DataRecord], str, str]],
    Dict[str, list], Dict[str, str]
]:
    """
    生成模拟数据 (当 Neo4j 不可用时)
    
    Args:
        num_genes: 基因数量
    
    Returns:
        (batches, vd, mps)
    """
    import random
    random.seed(42)

    vd = {
        "Strand": ["+", "-"],
        "Chromosome": [f"Chr{i:02d}" for i in range(1, 13)],
        "Accession": ["Nipponbare", "9311", "MH63"],
    }
    mps = {"正链": "+", "负链": "-"}

    batches = []

    # Batch 1: BED 文件 (基因基本信息)
    bed_records = []
    gene_names = []
    for i in range(num_genes):
        chrom_num = random.randint(1, 12)
        chrom = f"Chr{chrom_num:02d}"
        start = random.randint(100000, 30000000)
        end = start + random.randint(500, 50000)
        strand = random.choice(["+", "-"])
        gene_name = f"LOC_Os{chrom_num:02d}g{random.randint(10000, 99999)}"
        gene_names.append(gene_name)

        bed_records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=[
                ("chrom", chrom),
                ("start", str(start)),
                ("end", str(end)),
                ("strand", strand),
            ],
            file_type="bed_gene",
            file_name="Nipponbare_genes.bed",
            accession="Nipponbare",
        ))
    batches.append((bed_records, "bed_gene", "Nipponbare_genes.bed"))

    # Batch 2: FPKM 表达量 (部分重叠)
    expr_records = []
    overlap_genes = gene_names[:num_genes // 2]
    for gene_name in overlap_genes:
        leaf_val = f"Expr_leaf_{gene_name}"
        expr_records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=[("leaf_value", leaf_val)],
            file_type="fpkm_expression",
            file_name="Nipponbare_fpkm.csv",
            accession="Nipponbare",
        ))
    batches.append((expr_records, "fpkm_expression", "Nipponbare_fpkm.csv"))

    # Batch 3: RBH 同源关系
    rbh_records = []
    for gene_name in gene_names[:num_genes // 4]:
        target_gene = f"R01C{random.randint(1,12):02d}g{random.randint(100, 999)}"
        rbh_records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=[("subject_gene", target_gene)],
            file_type="rbh_homolog",
            file_name="Nipponbare_vs_9311_RBH.txt",
        ))
    batches.append((rbh_records, "rbh_homolog", "Nipponbare_vs_9311_RBH.txt"))

    # Batch 4: 功能注释
    func_records = []
    for gene_name in gene_names[:num_genes // 3]:
        func = f"Putative protein kinase domain containing protein"
        func_records.append(DataRecord(
            entity_key=gene_name,
            entity_type="Gene",
            fields=[("function", func)],
            file_type="function_annotation",
            file_name="Nipponbare_functions.tsv",
        ))
    batches.append((func_records, "function_annotation", "Nipponbare_functions.tsv"))

    return batches, vd, mps


# ============================================================
# 5. Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run Graph-Centric Incremental KG Construction Experiment"
    )
    parser.add_argument("--accession", default="Nipponbare",
                        help="Rice accession name (default: Nipponbare)")
    parser.add_argument("--max-genes", type=int, default=100,
                        help="Max genes to export (default: 100)")
    parser.add_argument("--output", default=None,
                        help="Output directory (default: results/kg_refinement/)")
    parser.add_argument("--ablation", action="store_true",
                        help="Run ablation experiments")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use synthetic data (no Neo4j needed)")
    parser.add_argument("--esp-report", action="store_true",
                        help="Print ESP report and exit")

    args = parser.parse_args()

    # ESP 报告模式
    if args.esp_report:
        report = derive_esp_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    # 输出目录
    if args.output:
        output_dir = args.output
    else:
        output_dir = str(PROJECT_ROOT / "experiment" / "results" / "kg_refinement")

    print("=" * 60)
    print("Graph-Centric Incremental KG Construction Experiment")
    print("=" * 60)
    print(f"Accession: {args.accession}")
    print(f"Max genes: {args.max_genes}")
    print(f"Ablation: {args.ablation}")
    print(f"Dry run: {args.dry_run}")
    print(f"Output: {output_dir}")

    if args.dry_run:
        # ── 离线模式: 模拟数据 ─────────────────────────
        print("\n[Mode] Dry run — using synthetic data")
        batches, vd, mps = generate_synthetic_data(args.max_genes)
        gold_edges = build_gold_standard(
            [rec for batch, _, _ in batches for rec in batch]
        )
    else:
        # ── 在线模式: 从 Neo4j 导出 ──────────────────────
        print("\n[Mode] Online — connecting to Neo4j")
        graph = get_neo4j_connection()
        if graph is None:
            print("\n[Fallback] Neo4j unavailable, using synthetic data")
            batches, vd, mps = generate_synthetic_data(args.max_genes)
            gold_edges = build_gold_standard(
                [rec for batch, _, _ in batches for rec in batch]
            )
        else:
            # 导出数据
            gene_records = export_gene_data(
                graph, args.accession, args.max_genes)
            expr_records = export_expression_data(
                graph, args.accession, args.max_genes)
            rbh_records = export_homolog_data(
                graph, args.accession, "9311",
                args.max_genes // 2)
            func_records = export_function_data(
                graph, args.accession, args.max_genes // 2)

            batches = [
                (gene_records, "bed_gene",
                 f"{args.accession}_genes.bed"),
                (expr_records, "fpkm_expression",
                 f"{args.accession}_fpkm.csv"),
                (rbh_records, "rbh_homolog",
                 f"{args.accession}_vs_9311_RBH.txt"),
                (func_records, "function_annotation",
                 f"{args.accession}_functions.tsv"),
            ]

            # 获取 VD/MPS
            try:
                from methods.s_cot_raps.mdr_adapter import MDRSchemaAdapter
                adapter = MDRSchemaAdapter()
                schema = adapter.get_full_schema()
                vd = schema.get("VD", {})
                mps = schema.get("MPS", {})
            except Exception as e:
                print(f"[Warning] MDR adapter failed: {e}")
                vd = {
                    "Strand": ["+", "-"],
                    "Chromosome": [f"Chr{i:02d}" for i in range(1, 13)],
                }
                mps = {"正链": "+", "负链": "-"}

            # Gold Standard
            all_records = [
                rec for batch, _, _ in batches for rec in batch
            ]
            gold_edges = build_gold_standard(all_records)

    print(f"\n[Data] {len(batches)} batches, "
          f"{sum(len(b[0]) for b in batches)} total records")
    print(f"[Gold] {len(gold_edges)} gold standard edges")

    # ── 运行实验 ───────────────────────────────────────────
    results = run_experiment(
        batches, vd, mps, gold_edges,
        run_ablation=args.ablation,
    )

    # ── 保存结果 ───────────────────────────────────────────
    save_results(results, output_dir)

    print("\n" + "=" * 60)
    print("Experiment completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
