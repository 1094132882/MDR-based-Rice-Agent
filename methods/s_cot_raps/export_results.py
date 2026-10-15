#!/usr/bin/env python3
"""
将 JSONL 结果导出为 CSV/Excel，方便查看每条问题的答案
支持详细模式和失败分析模式
"""
import json
import csv
import sys
import os

def load_dataset(csv_path: str) -> dict:
    """加载 dataset.csv 获取原始问题和答案"""
    data = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            data[i] = {
                'question': row['question'],
                'ground_truth': row['ground_truth'],
                'split': row['split']
            }
    return data

def export_to_csv(jsonl_path: str, output_path: str, dataset_path: str = 'dataset.csv', full_mode: bool = False):
    """导出结果为 CSV
    
    Args:
        full_mode: 如果 True，输出完整内容不截断
    """
    # 加载数据集
    dataset = load_dataset(dataset_path)
    
    # 读取 JSONL 结果
    results = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if 'id' in obj:  # 跳过 summary 行
                    results.append(obj)
            except:
                continue
    
    # 准备 CSV 数据
    rows = []
    failed_rows = []
    
    for r in results:
        idx = r.get('id', -1)
        ds = dataset.get(idx, {})
        
        ai_resp = r.get('response_preview', '')
        
        row = {
            'id': idx,
            'tool': r.get('tool', ''),
            'type': ds.get('split', ''),
            'question': ds.get('question', '') if full_mode else ds.get('question', '')[:100],
            'ground_truth': ds.get('ground_truth', '') if full_mode else ds.get('ground_truth', '')[:150],
            'ai_response': ai_resp if full_mode else ai_resp[:200],
            'json_ok': r.get('json_ok', 0),
            'compliant': r.get('compliant', 0),
            'field_em': r.get('field_em', ''),
            'field_match_rate': r.get('field_match_rate', ''),
            'matched_fields': r.get('matched_fields', 0),
            'total_fields': r.get('total_fields', 0),
            'latency_ms': r.get('latency_ms', 0),
            'error': r.get('error', '') if full_mode else r.get('error', '')[:100],
        }
        rows.append(row)
        
        # 检查是否失败
        is_failed = False
        fail_reason = []
        
        if r.get('field_em') == 0:
            is_failed = True
            fail_reason.append('field_em=0')
        if ai_resp == '{}' or ai_resp == '':
            is_failed = True
            fail_reason.append('空返回')
        if r.get('error'):
            is_failed = True
            fail_reason.append('报错')
        if r.get('json_ok') == 0:
            is_failed = True
            fail_reason.append('非JSON')
            
        if is_failed:
            row['fail_reason'] = '; '.join(fail_reason)
            failed_rows.append(row)
    
    # 写入完整 CSV（移除 fail_reason 字段）
    fieldnames = ['id', 'tool', 'type', 'question', 'ground_truth', 'ai_response', 
                  'json_ok', 'compliant', 'field_em', 'field_match_rate', 
                  'matched_fields', 'total_fields', 'latency_ms', 'error']
    
    # 清理 rows 中的 fail_reason（只保留在 failed_rows 中）
    clean_rows = []
    for r in rows:
        clean_row = {k: v for k, v in r.items() if k in fieldnames}
        clean_rows.append(clean_row)
    
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)
    
    print(f"✅ 已导出 {len(rows)} 条结果到 {output_path}")
    
    # 写入失败 CSV
    failed_output = output_path.replace('.csv', '_failed.csv')
    failed_fieldnames = fieldnames + ['fail_reason']
    
    with open(failed_output, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=failed_fieldnames)
        writer.writeheader()
        writer.writerows(failed_rows)
    
    print(f"❌ 已导出 {len(failed_rows)} 条失败结果到 {failed_output}")
    
    # 统计
    print("\n" + "="*70)
    print("按工具统计:")
    print("="*70)
    tool_stats = {}
    for r in rows:
        tool = r['tool']
        if tool not in tool_stats:
            tool_stats[tool] = {'total': 0, 'em_1': 0, 'has_data': 0}
        tool_stats[tool]['total'] += 1
        if r['field_em'] == 1:
            tool_stats[tool]['em_1'] += 1
        if r['ai_response'] and r['ai_response'] != '{}':
            tool_stats[tool]['has_data'] += 1
    
    for tool, stats in sorted(tool_stats.items()):
        rate = stats['em_1'] / stats['total'] * 100 if stats['total'] > 0 else 0
        data_rate = stats['has_data'] / stats['total'] * 100 if stats['total'] > 0 else 0
        status = "✅" if rate >= 90 else "⚠️" if rate >= 50 else "❌"
        print(f"  {status} {tool:35s}: EM={stats['em_1']:2d}/{stats['total']:2d} ({rate:5.1f}%), 有数据={stats['has_data']:2d} ({data_rate:5.1f}%)")
    
    # 失败问题详情
    print("\n" + "="*70)
    print("失败问题详情 (按工具分组):")
    print("="*70)
    
    # 按工具分组失败问题
    failed_by_tool = {}
    for r in failed_rows:
        tool = r['tool']
        if tool not in failed_by_tool:
            failed_by_tool[tool] = []
        failed_by_tool[tool].append(r)
    
    for tool, fails in sorted(failed_by_tool.items()):
        print(f"\n【{tool}】({len(fails)} 条失败)")
        for f in fails:
            gt_short = f['ground_truth'][:60] + '...' if len(f['ground_truth']) > 60 else f['ground_truth']
            ai_short = f['ai_response'][:60] + '...' if len(str(f['ai_response'])) > 60 else f['ai_response']
            print(f"  id={f['id']:3d} | {f['type']:6s} | 原因: {f.get('fail_reason', '?')}")
            print(f"       期望: {gt_short}")
            print(f"       实际: {ai_short}")

def main():
    if len(sys.argv) < 2:
        jsonl_path = 'runs/full_150.json'
        output_path = 'runs/full_150_results.csv'
    else:
        jsonl_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else jsonl_path.replace('.json', '_results.csv').replace('.jsonl', '_results.csv')
    
    # 检查是否有 --full 参数
    full_mode = '--full' in sys.argv
    
    dataset_path = 'dataset.csv'
    
    if not os.path.exists(jsonl_path):
        print(f"文件不存在: {jsonl_path}")
        sys.exit(1)
    
    export_to_csv(jsonl_path, output_path, dataset_path, full_mode)

if __name__ == "__main__":
    main()
