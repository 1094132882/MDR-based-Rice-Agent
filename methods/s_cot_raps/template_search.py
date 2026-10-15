#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板搜索框架
用于自动搜索最优提示模板配置
"""
import json
import argparse
import itertools
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pandas as pd
import subprocess
import time


class TemplateSearchSpace:
    """
    提示模板搜索空间
    
    定义可搜索的提示模板参数维度
    """
    
    def __init__(self):
        # 角色设定变体
        self.role_variants = [
            "strict_executor",  # 严格执行器（当前默认）
            "helpful_assistant",  # 友好助手
            "expert_system",  # 专家系统
        ]
        
        # 约束顺序变体
        self.constraint_orders = [
            "format_first",  # 格式约束优先
            "domain_first",  # 领域约束优先
            "mixed",  # 混合
        ]
        
        # Few-shot 数量
        self.few_shot_counts = [0, 1, 2, 3]
        
        # 自检语句变体
        self.self_check_variants = [
            "none",  # 无自检
            "simple",  # 简单自检
            "detailed",  # 详细自检
        ]
        
        # 输出格式说明
        self.output_format_variants = [
            "json_only",  # 仅 JSON
            "json_with_explanation",  # JSON + 解释
        ]
    
    def generate_all_combinations(self) -> List[Dict[str, Any]]:
        """生成所有参数组合"""
        combinations = []
        
        for role, order, few_shot, self_check, output_fmt in itertools.product(
            self.role_variants,
            self.constraint_orders,
            self.few_shot_counts,
            self.self_check_variants,
            self.output_format_variants
        ):
            config = {
                "role": role,
                "constraint_order": order,
                "few_shot_count": few_shot,
                "self_check": self_check,
                "output_format": output_fmt
            }
            combinations.append(config)
        
        return combinations
    
    def generate_greedy_path(self, base_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成贪婪搜索路径"""
        path = [base_config.copy()]
        
        # 逐维度尝试改进
        dimensions = [
            ("role", self.role_variants),
            ("constraint_order", self.constraint_orders),
            ("few_shot_count", self.few_shot_counts),
            ("self_check", self.self_check_variants),
            ("output_format", self.output_format_variants),
        ]
        
        current_config = base_config.copy()
        
        for dim_name, dim_values in dimensions:
            for value in dim_values:
                if value != current_config[dim_name]:
                    new_config = current_config.copy()
                    new_config[dim_name] = value
                    path.append(new_config)
        
        return path


class TemplateSearcher:
    """
    模板搜索器
    
    执行模板搜索并评估
    """
    
    def __init__(
        self,
        search_space: TemplateSearchSpace,
        dataset_path: str,
        output_dir: str,
        max_samples: int = 50
    ):
        self.search_space = search_space
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.max_samples = max_samples
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def evaluate_config(self, config: Dict[str, Any], config_id: int) -> Dict[str, Any]:
        """
        评估单个配置
        
        Args:
            config: 配置字典
            config_id: 配置编号
        
        Returns:
            评测结果字典
        """
        print(f"\n[Config {config_id}] Evaluating: {config}")
        
        # 这里简化处理：直接调用 run.py
        # 实际应该根据 config 动态生成提示模板
        output_file = self.output_dir / f"config_{config_id:03d}.jsonl"
        
        cmd = [
            "python", "methods/s_cot_raps/run.py",
            "--engine", "llm",
            "--method", "s_cot_raps",
            "--input", str(self.dataset_path),
            "--out", str(output_file),
            "--max", str(self.max_samples),
            "--skip-env-check"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 分钟超时
            )
            
            # 读取 summary
            summary_file = Path(str(output_file) + ".summary.json")
            if summary_file.exists():
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    summary["config"] = config
                    summary["config_id"] = config_id
                    return summary
            else:
                return {"config": config, "config_id": config_id, "error": "No summary file"}
        
        except Exception as e:
            return {"config": config, "config_id": config_id, "error": str(e)}
    
    def grid_search(self) -> List[Dict[str, Any]]:
        """网格搜索"""
        print("=" * 80)
        print("Starting Grid Search")
        print("=" * 80)
        
        combinations = self.search_space.generate_all_combinations()
        total = len(combinations)
        
        print(f"Total configurations to evaluate: {total}")
        print(f"(Using first {min(20, total)} for demo)")
        
        results = []
        
        for i, config in enumerate(combinations[:20]):  # 限制搜索数量
            result = self.evaluate_config(config, i)
            results.append(result)
            
            if i > 0 and i % 5 == 0:
                print(f"\nProgress: {i}/{min(20, total)}")
        
        return results
    
    def greedy_search(self, base_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """贪婪搜索"""
        print("=" * 80)
        print("Starting Greedy Search")
        print("=" * 80)
        print(f"Base config: {base_config}")
        
        path = self.search_space.generate_greedy_path(base_config)
        
        print(f"Total configurations to evaluate: {len(path)}")
        
        results = []
        best_score = 0.0
        best_config = base_config.copy()
        
        for i, config in enumerate(path):
            result = self.evaluate_config(config, i)
            results.append(result)
            
            # 更新最佳配置
            score = result.get("em", 0.0)
            if score > best_score:
                best_score = score
                best_config = config.copy()
                print(f"  → New best! EM: {score:.3f}")
        
        print(f"\nBest config: {best_config}")
        print(f"Best EM: {best_score:.3f}")
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], filename: str = "search_results.json"):
        """保存搜索结果"""
        output_file = self.output_dir / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    def analyze_results(self, results: List[Dict[str, Any]]):
        """分析搜索结果"""
        print("\n" + "=" * 80)
        print("Search Results Analysis")
        print("=" * 80)
        
        if not results:
            print("No results to analyze")
            return
        
        # 排序
        valid_results = [r for r in results if "em" in r]
        sorted_results = sorted(valid_results, key=lambda x: x.get("em", 0), reverse=True)
        
        print(f"\nTop 5 Configurations:")
        print("-" * 80)
        
        for i, result in enumerate(sorted_results[:5], 1):
            print(f"\n{i}. EM: {result.get('em', 0):.3f}, "
                  f"JSON OK: {result.get('json_ok_rate', 0):.3f}, "
                  f"Compliant: {result.get('compliant_rate', 0):.3f}")
            print(f"   Config: {result.get('config', {})}")
        
        # 维度影响分析
        print("\n" + "-" * 80)
        print("Dimension Impact Analysis:")
        
        dimensions = ["role", "constraint_order", "few_shot_count", "self_check", "output_format"]
        
        for dim in dimensions:
            dim_scores = {}
            for result in valid_results:
                config = result.get("config", {})
                value = config.get(dim)
                if value:
                    if value not in dim_scores:
                        dim_scores[value] = []
                    dim_scores[value].append(result.get("em", 0))
            
            if dim_scores:
                print(f"\n{dim}:")
                for value, scores in sorted(dim_scores.items()):
                    avg_score = sum(scores) / len(scores) if scores else 0
                    print(f"  {value}: {avg_score:.3f} (n={len(scores)})")


def main():
    parser = argparse.ArgumentParser(description="模板搜索框架")
    parser.add_argument("--mode", choices=["grid", "greedy"], default="greedy",
                        help="搜索模式")
    parser.add_argument("--dataset", default="methods/s_cot_raps/dataset.csv",
                        help="数据集路径")
    parser.add_argument("--output", default="methods/s_cot_raps/runs/template_search",
                        help="输出目录")
    parser.add_argument("--max-samples", type=int, default=50,
                        help="每个配置的最大样本数")
    args = parser.parse_args()
    
    # 创建搜索空间
    search_space = TemplateSearchSpace()
    
    # 创建搜索器
    searcher = TemplateSearcher(
        search_space=search_space,
        dataset_path=args.dataset,
        output_dir=args.output,
        max_samples=args.max_samples
    )
    
    # 执行搜索
    if args.mode == "grid":
        results = searcher.grid_search()
    else:  # greedy
        base_config = {
            "role": "strict_executor",
            "constraint_order": "format_first",
            "few_shot_count": 2,
            "self_check": "simple",
            "output_format": "json_only"
        }
        results = searcher.greedy_search(base_config)
    
    # 保存和分析结果
    searcher.save_results(results)
    searcher.analyze_results(results)
    
    print("\n" + "=" * 80)
    print("Template search completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()

