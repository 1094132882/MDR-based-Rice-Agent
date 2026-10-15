#!/usr/bin/env python3
"""
-*- coding: utf-8 -*-
S-COT方法评估脚本

对比实验设计：
1. Baseline（无MDR）: 纯LLM，不使用工具
2. MDR-Static（学长方法）: 手工编写的MDR约束提示词
3. S-COT（你的方法）: 自动化生成的MDR约束提示词
4. 消融实验: no_vd, no_mps

@author: jingwen.wu
@Time: 2025/12
"""
import os
import sys
import uuid
import time
import json
import argparse
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from pathlib import Path
import glob
import re

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

# 导入兼容性补丁
import tools._langchain_patch

from llm import llm
try:
    from response_templates import calculate_strict_em
except Exception:
    calculate_strict_em = None


def _compute_is_correct(ground_truth: str, answer: str, question: str, metric: str) -> bool:
    """统一的正确性判断（支持 strict/simple）。"""
    if not ground_truth or not answer:
        return False
    if metric == "strict" and calculate_strict_em is not None:
        try:
            return bool(calculate_strict_em(ground_truth, answer, question))
        except Exception:
            pass
    gt_str = str(ground_truth).strip()
    ans_str = str(answer).strip()
    return (gt_str in ans_str) or (ans_str in gt_str) or (gt_str == ans_str)


def get_next_run_number(output_dir: str, prefix: str = "") -> int:
    """获取下一个运行编号"""
    os.makedirs(output_dir, exist_ok=True)
    
    # 查找已有的运行编号
    pattern = os.path.join(output_dir, f"{prefix}*_run*.csv" if prefix else "*_run*.csv")
    existing_files = glob.glob(pattern)
    
    if not existing_files:
        return 1
    
    # 提取最大编号
    max_run = 0
    for f in existing_files:
        match = re.search(r'_run(\d+)', f)
        if match:
            run_num = int(match.group(1))
            max_run = max(max_run, run_num)
    
    return max_run + 1


def run_baseline(question: str):
    """Baseline: 纯LLM，不调用工具"""
    try:
        response = llm.invoke(question)
        content = response.content if hasattr(response, 'content') else str(response)
        return content, len(content.split())
    except Exception as e:
        return f"Error: {str(e)}", 0


def run_mdr_static(question: str, session_id: str):
    """MDR-Static: 学长的方法"""
    from agent import generate_response
    return generate_response(question, session_id)


def run_scot(question: str, session_id: str, method: str = "s_cot_raps", debug_log: bool = False, debug_log_file: str = None, trace_info: dict = None, use_got_ci: bool = True):
    """S-COT: 你的方法（支持全链路追踪）"""
    from agent_scot import generate_response_scot
    return generate_response_scot(question, session_id, method, debug_log=debug_log, debug_log_file=debug_log_file, trace_info=trace_info, use_got_ci=use_got_ci)


def evaluate_single(predict_fn, df: pd.DataFrame, output_path: str, method_name: str, metric: str = "strict"):
    """评估单个方法"""
    results = []
    total_tokens = 0
    total_latency = 0
    errors = 0
    
    print(f"\n{'='*60}")
    print(f"Running: {method_name}")
    print(f"{'='*60}")
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc=method_name):
        question = row['question']
        ground_truth = row.get('ground_truth', '')
        
        session_id = f"{method_name}_{idx}_{uuid.uuid4().hex[:8]}"
        
        start_time = time.time()
        try:
            answer, tokens = predict_fn(question, session_id)
            error = ""
        except Exception as e:
            answer = f"Error: {str(e)}"
            tokens = 0
            error = str(e)
            errors += 1
        
        latency = time.time() - start_time
        total_tokens += tokens
        total_latency += latency

        is_correct = _compute_is_correct(ground_truth, answer, question, metric)
        
        results.append({
            'id': row.get('id', idx),
            'question': question,
            'ground_truth': ground_truth,
            'answer': answer,
            'is_correct': is_correct,
            'tokens': tokens,
            'latency_s': round(latency, 2),
            'error': error
        })
    
    # 保存结果
    pd.DataFrame(results).to_csv(output_path, index=False, encoding='utf-8-sig')
    
    # 打印摘要
    avg_latency = total_latency / len(df) if len(df) > 0 else 0
    correct_count = sum(1 for r in results if r.get('is_correct'))
    accuracy = correct_count / len(df) * 100 if len(df) > 0 else 0
    print(f"\n{method_name} Results:")
    print(f"  - Total samples: {len(df)}")
    print(f"  - Correct: {correct_count} ({accuracy:.1f}%)")
    print(f"  - Errors: {errors}")
    print(f"  - Total tokens: {total_tokens}")
    print(f"  - Avg latency: {avg_latency:.2f}s")
    print(f"  - Results saved to: {output_path}")
    
    return {
        'samples': len(df),
        'correct': correct_count,
        'accuracy': round(accuracy, 2),
        'errors': errors,
        'tokens': total_tokens,
        'avg_latency': round(avg_latency, 2),
        'output_file': output_path
    }


def run_all_experiments(input_file: str, output_dir: str, max_samples: int = 0, run_number: int = None, metric: str = "strict"):
    """运行所有对比实验"""
    # 加载数据
    if input_file.endswith('.xlsx'):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)
    
    if max_samples > 0:
        df = df.head(max_samples)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 确定运行编号
    if run_number is None:
        run_number = get_next_run_number(output_dir)
    
    run_suffix = f"_run{run_number}"
    
    print(f"\n{'='*60}")
    print(f"S-COT Comparative Experiment - Run #{run_number}")
    print(f"Dataset: {input_file}")
    print(f"Samples: {len(df)}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")
    
    # 实验列表
    experiments = [
        ('baseline', lambda q, s: run_baseline(q)),
        ('mdr_static', run_mdr_static),
        ('s_cot_raps', lambda q, s: run_scot(q, s, 's_cot_raps')),
        ('no_vd', lambda q, s: run_scot(q, s, 'no_vd')),
        ('no_mps', lambda q, s: run_scot(q, s, 'no_mps')),
    ]
    
    results_summary = {}
    
    for exp_name, predict_fn in experiments:
        output_file = os.path.join(output_dir, f"{exp_name}{run_suffix}.csv")
        
        try:
            info = evaluate_single(predict_fn, df, output_file, exp_name, metric=metric)
            results_summary[exp_name] = info
        except Exception as e:
            print(f"Error in {exp_name}: {e}")
            results_summary[exp_name] = {'error': str(e)}
    
    # 保存汇总
    summary_path = os.path.join(output_dir, f"summary{run_suffix}.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("S-COT Experiment Summary\n")
        f.write(f"Run: #{run_number}\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Dataset: {input_file}\n")
        f.write(f"Samples: {len(df)}\n")
        f.write("=" * 60 + "\n\n")
        
        for exp_name, info in results_summary.items():
            f.write(f"{exp_name}:\n")
            for k, v in info.items():
                f.write(f"  {k}: {v}\n")
            f.write("\n")
    
    print(f"\n{'='*60}")
    print("All experiments completed!")
    print(f"Summary saved to: {summary_path}")
    print(f"{'='*60}")
    
    return results_summary, run_number


def run_single_experiment(method: str, input_file: str, output_path: str, max_samples: int = 0, run_number: int = None, debug: bool = False, full_trace: bool = False, metric: str = "strict"):
    """
    运行单个实验
    
    Args:
        method: 实验方法
        input_file: 输入数据集
        output_path: 输出路径
        max_samples: 最大样本数（0=全部）
        run_number: 运行编号
        debug: 是否开启调试日志
        full_trace: 是否开启全链路追踪（飞行记录仪模式）
    """
    # 加载数据
    if input_file.endswith('.xlsx'):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)
    
    if max_samples > 0:
        df = df.head(max_samples)
    
    # 处理输出路径
    if os.path.isdir(output_path) or output_path.endswith('/'):
        os.makedirs(output_path, exist_ok=True)
        
        # 确定运行编号
        if run_number is None:
            run_number = get_next_run_number(output_path, method)
        
        output_file = os.path.join(output_path, f"{method}_run{run_number}.csv")
    else:
        output_file = output_path
        run_number = 1
    
    # 调试日志文件路径
    debug_log_file = os.path.join(os.path.dirname(output_file), f"debug_log_run{run_number}.jsonl") if debug else None
    
    # 🎯【飞行记录仪】全链路追踪日志路径
    trace_log_path = output_file.replace(".csv", "_full_trace.jsonl") if full_trace else None
    
    if full_trace:
        print(f"📝 【飞行记录仪】全链路追踪日志: {trace_log_path}")
    
    # 选择预测函数（根据是否启用全链路追踪）
    if method == 'baseline':
        predict_fn = lambda q, s=None, trace=None: run_baseline(q)
    elif method == 'mdr_static':
        predict_fn = lambda q, s, trace=None: run_mdr_static(q, s)
    elif method in ['s_cot_raps', 'no_vd', 'no_mps', 'zero', 'few', 'ont_full', 'ont_simple', 'simple', 'no_gotci']:
        if method == 'no_gotci':
            predict_fn = lambda q, s, trace=None: run_scot(q, s, 's_cot_raps', debug_log=debug, debug_log_file=debug_log_file, trace_info=trace, use_got_ci=False)
        else:
            predict_fn = lambda q, s, trace=None: run_scot(q, s, method, debug_log=debug, debug_log_file=debug_log_file, trace_info=trace)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    if debug and debug_log_file:
        print(f"📝 调试日志: {debug_log_file}")
    
    # 使用新的评估函数（支持全链路追踪）
    if full_trace:
        evaluate_single_with_trace(predict_fn, df, output_file, method, trace_log_path, metric=metric)
    else:
        evaluate_single(predict_fn, df, output_file, method, metric=metric)
    
    return run_number


def evaluate_single_with_trace(predict_fn, df: pd.DataFrame, output_path: str, method_name: str, trace_log_path: str, metric: str = "strict"):
    """
    评估单个方法（带全链路追踪 - 飞行记录仪模式）
    
    🎯 核心功能：
    - 每跑完一条数据，立即将追踪信息写入 JSONL 文件
    - 包含：MDR 约束、合成示例、GoT-CI 历史、工具结果、最终答案
    - 支持断点续传（追加模式）
    """
    results = []
    total_tokens = 0
    total_latency = 0
    errors = 0
    intercept_count = 0  # GoT-CI 拦截计数
    
    print(f"\n{'='*60}")
    print(f"🎯 Running: {method_name} (全链路追踪模式)")
    print(f"{'='*60}")
    
    # 打开追踪日志文件（追加模式，防止中断丢失）
    with open(trace_log_path, "w", encoding="utf-8") as trace_file:
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"{method_name} [TRACE]"):
            question = row['question']
            ground_truth = row.get('ground_truth', '')
            
            session_id = f"{method_name}_{idx}_{uuid.uuid4().hex[:8]}"
            
            # 初始化追踪字典
            trace_info = {}
            
            start_time = time.time()
            try:
                # ⚡️ 调用 Agent，传入 trace_info
                answer, tokens = predict_fn(question, session_id, trace_info)
                error = ""
            except Exception as e:
                answer = f"Error: {str(e)}"
                tokens = 0
                error = str(e)
                errors += 1
            
            latency = time.time() - start_time
            total_tokens += tokens
            total_latency += latency
            
            # 🔍【埋点 D】判断正确性
            is_correct = _compute_is_correct(ground_truth, answer, question, metric)
            
            # 检查是否触发了 GoT-CI 拦截
            got_ci_triggered = False
            if trace_info.get("got_ci_attempts"):
                for att in trace_info["got_ci_attempts"]:
                    if att.get("status") == "intercepted":
                        got_ci_triggered = True
                        intercept_count += 1
                        break
            
            # 组装最终日志条目
            log_entry = {
                "id": row.get('id', idx),
                "question": question,
                "ground_truth": ground_truth,
                "final_answer": answer,
                "is_correct": is_correct,
                "latency_s": round(latency, 2),
                "tokens": tokens,
                "error": error if error else None,
                "trace": {
                    "tool_name": trace_info.get("tool_name"),
                    "method": trace_info.get("method"),
                    "mdr_constraints": trace_info.get("mdr_constraints"),
                    "synthetic_examples": trace_info.get("synthetic_examples"),
                    "got_ci_attempts": trace_info.get("got_ci_attempts", []),
                    "tool_output": trace_info.get("tool_output"),
                    "got_ci_triggered": got_ci_triggered
                }
            }
            
            # 立即写入一行（实时持久化）
            trace_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            trace_file.flush()  # 强制刷新缓冲区，确保断电也不丢
            
            # 同时保存到 CSV 结果
            results.append({
                'id': row.get('id', idx),
                'question': question,
                'ground_truth': ground_truth,
                'answer': answer,
                'is_correct': is_correct,
                'tokens': tokens,
                'latency_s': round(latency, 2),
                'error': error,
                'got_ci_triggered': got_ci_triggered
            })
    
    # 保存 CSV 结果
    pd.DataFrame(results).to_csv(output_path, index=False, encoding='utf-8-sig')
    
    # 打印摘要
    avg_latency = total_latency / len(df) if len(df) > 0 else 0
    correct_count = sum(1 for r in results if r.get('is_correct'))
    accuracy = correct_count / len(df) * 100 if len(df) > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"🎯 {method_name} Results (全链路追踪)")
    print(f"{'='*60}")
    print(f"  - Total samples: {len(df)}")
    print(f"  - Correct: {correct_count} ({accuracy:.1f}%)")
    print(f"  - Errors: {errors}")
    print(f"  - GoT-CI Intercepts: {intercept_count}")
    print(f"  - Total tokens: {total_tokens}")
    print(f"  - Avg latency: {avg_latency:.2f}s")
    print(f"  - CSV saved to: {output_path}")
    print(f"  - Trace saved to: {trace_log_path}")
    print(f"{'='*60}")
    
    return {
        'samples': len(df),
        'correct': correct_count,
        'accuracy': accuracy,
        'errors': errors,
        'intercepts': intercept_count,
        'tokens': total_tokens,
        'avg_latency': round(avg_latency, 2),
        'output_file': output_path,
        'trace_file': trace_log_path
    }


def main():
    parser = argparse.ArgumentParser(description="S-COT方法评估脚本")
    parser.add_argument('--method', type=str, default='all',
                       choices=['all', 'baseline', 'mdr_static', 's_cot_raps', 'no_vd', 'no_mps', 'zero', 'few', 'ont_full', 'ont_simple', 'simple', 'no_gotci', 'ground_truth'],
                       help='评估方法: all=全部, 其他=单个方法')
    parser.add_argument('--ablation', type=str, default='none',
                       choices=['none', 'no_vd', 'no_mps', 'simple'],
                       help='兼容参数: 指定消融模式(将覆盖 method)')
    parser.add_argument('--no_gotci', action='store_true',
                       help='兼容参数: 关闭 GoT-CI 校验 (等价于 method=no_gotci)')
    parser.add_argument('--input', type=str, default='dataset.csv',
                       help='输入数据集路径')
    parser.add_argument('--output', type=str, default='results',
                       help='输出目录')
    parser.add_argument('--max', type=int, default=0,
                       help='最大样本数（0=全部）')
    parser.add_argument('--run', type=int, default=None,
                       help='指定运行编号（默认自动递增）')
    parser.add_argument('--debug', action='store_true',
                       help='开启调试日志（记录工具原始 JSON）')
    parser.add_argument('--trace', action='store_true',
                       help='【飞行记录仪】开启全链路追踪（记录 MDR约束/合成示例/GoT-CI/工具结果）')
    parser.add_argument('--metric', type=str, default='strict',
                       choices=['strict', 'simple'],
                       help='评估指标: strict=必需字段+集合重叠, simple=字符串包含')
    
    args = parser.parse_args()
    
    # 兼容旧参数：--ablation / --no_gotci
    if args.no_gotci:
        args.method = 'no_gotci'
    if args.ablation and args.ablation != 'none':
        args.method = args.ablation

    if args.method == 'all':
        run_all_experiments(args.input, args.output, args.max, args.run, metric=args.metric)
    else:
        run_single_experiment(args.method, args.input, args.output, args.max, args.run, debug=args.debug, full_trace=args.trace, metric=args.metric)


if __name__ == "__main__":
    main()
