#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析字段级 EM 结果的脚本
用法：python analyze_field_em.py runs/test_py_ground_truth.jsonl
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

def analyze_field_em(jsonl_path: str):
    """分析字段级EM结果"""
    
    # 统计数据
    stats = {
        'total': 0,
        'field_em_count': 0,
        'em_contains_count': 0,
        'by_tool': defaultdict(lambda: {
            'total': 0,
            'field_em': 0,
            'matched_fields': 0,
            'total_fields': 0,
            'samples': []
        })
    }
    
    # 读取结果
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            record = json.loads(line)
            tool = record.get('tool', 'unknown')
            
            stats['total'] += 1
            
            # 字段级EM
            field_em = record.get('field_em')
            if field_em == 1:
                stats['field_em_count'] += 1
                stats['by_tool'][tool]['field_em'] += 1
            
            # 旧的contains EM
            em_contains = record.get('em_contains')
            if em_contains == 1:
                stats['em_contains_count'] += 1
            
            # 按工具统计
            stats['by_tool'][tool]['total'] += 1
            stats['by_tool'][tool]['matched_fields'] += record.get('matched_fields', 0)
            stats['by_tool'][tool]['total_fields'] += record.get('total_fields', 0)
            
            # 保存样本（用于错误分析）
            if field_em != 1 and record.get('total_fields', 0) > 0:
                stats['by_tool'][tool]['samples'].append({
                    'id': record.get('id'),
                    'matched': record.get('matched_fields'),
                    'total': record.get('total_fields'),
                    'preview': record.get('response_preview', '')[:100]
                })
    
    # 输出结果
    print("=" * 80)
    print("字段级 EM 分析结果")
    print("=" * 80)
    print(f"\n总样本数: {stats['total']}")
    print(f"字段级 EM: {stats['field_em_count']}/{stats['total']} = {stats['field_em_count']/stats['total']:.2%}")
    print(f"Contains EM (旧): {stats['em_contains_count']}/{stats['total']} = {stats['em_contains_count']/stats['total']:.2%}")
    print(f"提升: {(stats['field_em_count'] - stats['em_contains_count'])} 个样本")
    
    print("\n" + "=" * 80)
    print("按工具分类统计")
    print("=" * 80)
    print(f"{'工具':<30} {'总数':>6} {'Field EM':>10} {'字段匹配率':>12}")
    print("-" * 80)
    
    for tool, data in sorted(stats['by_tool'].items(), 
                             key=lambda x: x[1]['field_em']/max(x[1]['total'], 1), 
                             reverse=True):
        if data['total'] == 0:
            continue
        
        field_em_rate = data['field_em'] / data['total']
        field_match_rate = data['matched_fields'] / max(data['total_fields'], 1)
        
        print(f"{tool:<30} {data['total']:>6} {field_em_rate:>9.1%} {field_match_rate:>11.1%}")
    
    print("\n" + "=" * 80)
    print("表现较差的工具（失败样本分析）")
    print("=" * 80)
    
    for tool, data in sorted(stats['by_tool'].items(), 
                             key=lambda x: len(x[1]['samples']), 
                             reverse=True):
        if not data['samples']:
            continue
        
        print(f"\n工具: {tool}")
        print(f"失败样本数: {len(data['samples'])}/{data['total']}")
        print("典型失败案例：")
        
        for i, sample in enumerate(data['samples'][:3], 1):  # 只显示前3个
            print(f"  {i}. ID={sample['id']}: 匹配 {sample['matched']}/{sample['total']} 字段")
            print(f"     响应预览: {sample['preview']}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze_field_em.py <jsonl文件路径>")
        print("示例: python analyze_field_em.py runs/test_py_ground_truth.jsonl")
        sys.exit(1)
    
    jsonl_path = sys.argv[1]
    if not Path(jsonl_path).exists():
        print(f"错误: 文件不存在: {jsonl_path}")
        sys.exit(1)
    
    analyze_field_em(jsonl_path)

