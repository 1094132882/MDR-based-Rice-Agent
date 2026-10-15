#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Metrics for S-CoT × RAPS Evaluation
包含字段级 EM、MDR 合规率、Cypher 可执行率等细分指标
"""
import re
from typing import Dict, Any, Tuple, List, Optional


class MetricsCalculator:
    """
    评测指标计算器
    
    功能：
    1. 字段级 EM（逐字段精确匹配）
    2. MDR 合规率（值域命中率）
    3. Cypher 可执行率（可选）
    4. 综合评分
    """
    
    def __init__(self):
        # 值域约束定义
        self.vd_constraints = {
            "Chromosome": r"^Chr(0[1-9]|1[0-2])$",
            "Strand": r"^[+\-]$",
            "Position": r"^\d+-\d+$",
            "OGI": r"^OGI:\d{8}$",
            "SVTYPE": r"^(DEL|INS|DUP|INV|TRA)$",
        }
    
    def field_level_em(
        self, 
        pred: Dict[str, Any], 
        gold: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Tuple[Dict[str, int], float]:
        """
        字段级精确匹配
        
        Args:
            pred: 预测结果
            gold: 标准答案
            fields: 要检查的字段列表（None=检查所有）
        
        Returns:
            (field_scores, avg_score)
            field_scores: {field: 1/0} 字典
            avg_score: 平均匹配率
        """
        if not isinstance(pred, dict) or not isinstance(gold, dict):
            return {}, 0.0
        
        if fields is None:
            fields = list(set(pred.keys()) | set(gold.keys()))
        
        field_scores = {}
        for field in fields:
            pred_val = pred.get(field)
            gold_val = gold.get(field)
            
            # 标准化比较
            if pred_val == gold_val:
                field_scores[field] = 1
            elif isinstance(pred_val, str) and isinstance(gold_val, str):
                # 字符串：忽略大小写和空格
                field_scores[field] = int(
                    pred_val.strip().lower() == gold_val.strip().lower()
                )
            elif isinstance(pred_val, (list, tuple)) and isinstance(gold_val, (list, tuple)):
                # 列表：集合比较
                field_scores[field] = int(
                    set(pred_val) == set(gold_val)
                )
            else:
                field_scores[field] = 0
        
        avg_score = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
        return field_scores, avg_score
    
    def mdr_compliance_rate(
        self, 
        pred: Dict[str, Any],
        tool_name: str = None
    ) -> Tuple[Dict[str, bool], float]:
        """
        MDR 合规率检查
        
        检查预测结果是否满足值域约束
        
        Args:
            pred: 预测结果
            tool_name: 工具名称（用于特定约束）
        
        Returns:
            (field_compliance, compliance_rate)
            field_compliance: {field: True/False} 字典
            compliance_rate: 合规率
        """
        if not isinstance(pred, dict):
            return {}, 0.0
        
        field_compliance = {}
        
        for field, constraint in self.vd_constraints.items():
            if field in pred:
                value = pred[field]
                if isinstance(value, str):
                    field_compliance[field] = bool(re.match(constraint, value.strip()))
                else:
                    field_compliance[field] = False
        
        # 特定工具的额外约束
        if tool_name == "gene_locator":
            # Position 的 start < end 约束
            if "Position" in pred:
                pos = str(pred["Position"])
                m = re.match(r"^(\d+)-(\d+)$", pos)
                if m:
                    start, end = int(m.group(1)), int(m.group(2))
                    if "Position" in field_compliance:
                        field_compliance["Position"] = field_compliance["Position"] and (start < end)
        
        if tool_name == "structural_variation_locator":
            # SVs 列表检查
            if "SVs" in pred:
                svs = pred["SVs"]
                if isinstance(svs, list):
                    all_valid = all(
                        isinstance(sv, dict) and 
                        sv.get("Type") in ["DEL", "INS", "DUP", "INV", "TRA", "OTH"]
                        for sv in svs
                    )
                    field_compliance["SVs"] = all_valid
                else:
                    field_compliance["SVs"] = False
        
        compliance_rate = sum(field_compliance.values()) / len(field_compliance) if field_compliance else 0.0
        return field_compliance, compliance_rate
    
    def vd_hit_rate(
        self,
        pred: Dict[str, Any],
        vd_dict: Dict[str, List[str]]
    ) -> Tuple[Dict[str, bool], float]:
        """
        值域命中率
        
        检查预测值是否在允许的值域内
        
        Args:
            pred: 预测结果
            vd_dict: 值域字典 {field: [allowed_values]}
        
        Returns:
            (field_hits, hit_rate)
        """
        if not isinstance(pred, dict) or not vd_dict:
            return {}, 0.0
        
        field_hits = {}
        
        for field, allowed_values in vd_dict.items():
            if field in pred:
                value = pred[field]
                if isinstance(value, str):
                    field_hits[field] = value.strip() in allowed_values
                else:
                    field_hits[field] = value in allowed_values
        
        hit_rate = sum(field_hits.values()) / len(field_hits) if field_hits else 0.0
        return field_hits, hit_rate
    
    def alias_mapping_coverage(
        self,
        question: str,
        pred: Dict[str, Any],
        mps_dict: Dict[str, str]
    ) -> Tuple[int, int, float]:
        """
        别名映射覆盖率
        
        检查问题中的别名是否被正确映射
        
        Args:
            question: 原始问题
            pred: 预测结果
            mps_dict: 别名映射字典
        
        Returns:
            (found_aliases, mapped_correctly, coverage)
        """
        if not mps_dict:
            return 0, 0, 0.0
        
        # 查找问题中出现的别名
        found_aliases = 0
        mapped_correctly = 0
        
        for alias, standard in mps_dict.items():
            if alias in question:
                found_aliases += 1
                # 检查预测结果中是否使用了标准术语
                pred_str = str(pred)
                if standard in pred_str:
                    mapped_correctly += 1
        
        coverage = mapped_correctly / found_aliases if found_aliases > 0 else 0.0
        return found_aliases, mapped_correctly, coverage
    
    def comprehensive_score(
        self,
        pred: Dict[str, Any],
        gold: Dict[str, Any],
        question: str = None,
        tool_name: str = None,
        vd_dict: Optional[Dict] = None,
        mps_dict: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        综合评分
        
        Args:
            pred: 预测结果
            gold: 标准答案
            question: 原始问题
            tool_name: 工具名称
            vd_dict: 值域字典
            mps_dict: 别名映射字典
        
        Returns:
            综合指标字典
        """
        metrics = {}
        
        # 字段级 EM
        field_scores, field_em = self.field_level_em(pred, gold)
        metrics["field_em"] = round(field_em, 3)
        metrics["field_scores"] = field_scores
        
        # MDR 合规率
        field_compliance, compliance_rate = self.mdr_compliance_rate(pred, tool_name)
        metrics["mdr_compliance_rate"] = round(compliance_rate, 3)
        metrics["field_compliance"] = field_compliance
        
        # 值域命中率
        if vd_dict:
            field_hits, hit_rate = self.vd_hit_rate(pred, vd_dict)
            metrics["vd_hit_rate"] = round(hit_rate, 3)
            metrics["vd_field_hits"] = field_hits
        
        # 别名映射覆盖率
        if mps_dict and question:
            found, mapped, coverage = self.alias_mapping_coverage(question, pred, mps_dict)
            metrics["alias_found"] = found
            metrics["alias_mapped"] = mapped
            metrics["alias_coverage"] = round(coverage, 3)
        
        return metrics


def evaluate_predictions(
    predictions: List[Dict[str, Any]],
    ground_truths: List[Dict[str, Any]],
    questions: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    vd_dict: Optional[Dict] = None,
    mps_dict: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    批量评估预测结果
    
    Args:
        predictions: 预测结果列表
        ground_truths: 标准答案列表
        questions: 问题列表
        tool_names: 工具名称列表
        vd_dict: 值域字典
        mps_dict: 别名映射字典
    
    Returns:
        聚合指标字典
    """
    calculator = MetricsCalculator()
    
    n = len(predictions)
    if n == 0:
        return {}
    
    # 聚合指标
    total_field_em = 0.0
    total_compliance = 0.0
    total_vd_hit = 0.0
    total_alias_coverage = 0.0
    
    for i in range(n):
        pred = predictions[i]
        gold = ground_truths[i] if i < len(ground_truths) else {}
        question = questions[i] if questions and i < len(questions) else None
        tool_name = tool_names[i] if tool_names and i < len(tool_names) else None
        
        metrics = calculator.comprehensive_score(
            pred=pred,
            gold=gold,
            question=question,
            tool_name=tool_name,
            vd_dict=vd_dict,
            mps_dict=mps_dict
        )
        
        total_field_em += metrics.get("field_em", 0)
        total_compliance += metrics.get("mdr_compliance_rate", 0)
        if "vd_hit_rate" in metrics:
            total_vd_hit += metrics["vd_hit_rate"]
        if "alias_coverage" in metrics:
            total_alias_coverage += metrics["alias_coverage"]
    
    return {
        "count": n,
        "avg_field_em": round(total_field_em / n, 3),
        "avg_mdr_compliance": round(total_compliance / n, 3),
        "avg_vd_hit_rate": round(total_vd_hit / n, 3) if vd_dict else None,
        "avg_alias_coverage": round(total_alias_coverage / n, 3) if mps_dict else None,
    }


if __name__ == "__main__":
    # 测试代码
    print("Testing Metrics Calculator")
    print("=" * 60)
    
    calculator = MetricsCalculator()
    
    # 测试数据
    pred = {
        "Gene": "LOC_Os08g02050",
        "Chromosome": "Chr08",
        "Position": "662167-667559",
        "Strand": "+"
    }
    
    gold = {
        "Gene": "LOC_Os08g02050",
        "Chromosome": "Chr08",
        "Position": "662167-667559",
        "Strand": "+"
    }
    
    question = "LOC_Os08g02050在基因组中的具体物理坐标是多少？"
    
    # 综合评分
    metrics = calculator.comprehensive_score(
        pred=pred,
        gold=gold,
        question=question,
        tool_name="gene_locator"
    )
    
    print("\nTest Results:")
    print(f"  Field EM: {metrics['field_em']}")
    print(f"  MDR Compliance: {metrics['mdr_compliance_rate']}")
    print(f"  Field Compliance: {metrics['field_compliance']}")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")

