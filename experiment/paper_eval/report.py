"""Readable tables; undefined Accuracy is never displayed as an exact score."""
import csv,json
from pathlib import Path

def generate_report(output):
    output=Path(output)
    def read(name):
        with (output/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    def pct(value):return f'{float(value)*100:.2f}%' if value not in ['',None] else '待复核'
    def accuracy(row):
        if row['accuracy_mean'] not in ['',None]:return pct(row['accuracy_mean'])
        return f"{pct(row['accuracy_lower_bound_mean'])}–{pct(row['accuracy_upper_bound_mean'])}（范围）"
    lines=['# Accuracy / BERTScore F1 重评结果','',
           'S=85，C=65，全部=150（每个 run）。使用全部可用 run，不选择最高分。',
           'Accuracy 是完整参考事实匹配；语义不明确的功能描述保留待复核。存在待复核项时只显示完整分母下的上下界，不冒充最终正确率。',
           '两项指标统一使用 final_answer，原始 answer 保留。BERTScore F1 按每题算术平均，表中显示百分制；默认长文本采用窗口编码与全局匹配变体，详见 manifest。', '',
           '## 四个模型完整方法', '',
           '| 模型 | 子集 | run | 每次题数 | Accuracy | BERTScore F1 | 待复核数 | 截断数 |',
           '|---|---|---|---:|---|---|---:|---:|']
    for r in read('model_comparison.csv'):
        lines.append(f"| {r['model']} | {r['subset']} | {r['runs']} | {r['n_per_run']} | {accuracy(r)} | {pct(r['bertscore_f1_mean'])} | {r['accuracy_review_pending']} | {r['bertscore_truncated']} |")
    lines+=['','## 四个模型消融（全部题）','','| 模型 | 方法 | run | 每次题数 | Accuracy | BERTScore F1 | 待复核数 | 截断数 |','|---|---|---|---:|---|---|---:|---:|']
    for r in read('ablation.csv'):
        lines.append(f"| {r['model']} | {r['method']} | {r['runs']} | {r['n_per_run']} | {accuracy(r)} | {pct(r['bertscore_f1_mean'])} | {r['accuracy_review_pending']} | {r['bertscore_truncated']} |")
    lines+=['','标准差和各 run 的结果详见 CSV。单次 run 的标准差不可估计。',
            '这些是规则复算与固定 BERT 模型的评分；使用论文最终 Accuracy 前，应抽查规则判定并处理待复核记录。',
            '本次没有重新生成答案、调用 RAGAs 或付费 API，也没有重算 Faithfulness。','']
    (output/'summary.md').write_text('\n'.join(lines))
    return output/'summary.md'
