#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比消融实验结果
"""
import json
import argparse
from pathlib import Path
from typing import Dict, List
import pandas as pd


def load_summary(path: Path) -> Dict:
    """加载 summary.json 文件"""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def compare_results(results_dir: str):
    """对比多个实验结果"""
    results_dir = Path(results_dir)
    
    # 查找所有 summary.json 文件
    summary_files = list(results_dir.glob("*.summary.json"))
    
    if not summary_files:
        print(f"No summary files found in {results_dir}")
        return
    
    print("=" * 80)
    print("S-CoT × RAPS Ablation Study - Results Comparison")
    print("=" * 80)
    print()
    
    # 加载所有结果
    results = []
    for summary_file in sorted(summary_files):
        method_name = summary_file.stem.replace(".jsonl", "")
        summary = load_summary(summary_file)
        summary["method_name"] = method_name
        results.append(summary)
    
    # 构造对比表
    if not results:
        print("No valid summaries found")
        return
    
    # 表头
    headers = ["Method", "Count", "JSON OK", "Compliant", "EM", "Avg Latency (ms)"]
    rows = []
    
    for res in results:
        row = [
            res.get("method_name", "unknown"),
            res.get("count", 0),
            f"{res.get('json_ok_rate', 0):.3f}",
            f"{res.get('compliant_rate', 0):.3f}",
            f"{res.get('em', 0):.3f}",
            res.get("avg_latency_ms", 0)
        ]
        rows.append(row)
    
    # 打印表格
    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    
    # 打印表头
    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("-" * len(header_line))
    
    # 打印数据行
    for row in rows:
        print(" | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths)))
    
    print()
    print("=" * 80)
    
    # 计算改进率（相对于 baseline）
    baseline = next((r for r in results if "baseline" in r.get("method_name", "")), None)
    full = next((r for r in results if "full" in r.get("method_name", "")), None)
    
    if baseline and full:
        print("\nImprovement vs. Baseline:")
        print(f"  JSON OK:    {baseline.get('json_ok_rate', 0):.3f} → {full.get('json_ok_rate', 0):.3f} "
              f"({(full.get('json_ok_rate', 0) - baseline.get('json_ok_rate', 0)) * 100:+.1f}%)")
        print(f"  Compliant:  {baseline.get('compliant_rate', 0):.3f} → {full.get('compliant_rate', 0):.3f} "
              f"({(full.get('compliant_rate', 0) - baseline.get('compliant_rate', 0)) * 100:+.1f}%)")
        print(f"  EM:         {baseline.get('em', 0):.3f} → {full.get('em', 0):.3f} "
              f"({(full.get('em', 0) - baseline.get('em', 0)) * 100:+.1f}%)")
    
    # 消融分析
    no_vd = next((r for r in results if "no_vd" in r.get("method_name", "")), None)
    no_mps = next((r for r in results if "no_mps" in r.get("method_name", "")), None)
    
    if full and (no_vd or no_mps):
        print("\nAblation Analysis:")
        if no_vd:
            print(f"  Without VD:  EM {full.get('em', 0):.3f} → {no_vd.get('em', 0):.3f} "
                  f"({(no_vd.get('em', 0) - full.get('em', 0)) * 100:+.1f}%)")
        if no_mps:
            print(f"  Without MPS: EM {full.get('em', 0):.3f} → {no_mps.get('em', 0):.3f} "
                  f"({(no_mps.get('em', 0) - full.get('em', 0)) * 100:+.1f}%)")
    
    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="对比消融实验结果")
    parser.add_argument("--dir", required=True, help="结果目录路径")
    args = parser.parse_args()
    
    compare_results(args.dir)


if __name__ == "__main__":
    main()

