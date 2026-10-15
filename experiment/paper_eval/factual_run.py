"""Add Factual F1 to saved Accuracy/BERTScore records without neural inference."""
import argparse,collections,csv,json,statistics,hashlib
from pathlib import Path
from .accuracy import make_reference
from .factual_f1 import score_factual_f1,VERSION
from .run import read_rows,write_rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 if (a.output/'per_question.csv').exists():raise SystemExit('Choose a new output directory')
 rows=read_rows(a.input)
 for r in rows:r.update(score_factual_f1(make_reference(r),r.get('final_answer',r['answer']),r.get('generation_error','')))
 write_rows(a.output/'per_question.csv',rows)
 groups=collections.defaultdict(list)
 for r in rows:
  for sub in ['all',r['difficulty']]:groups[(r['model'],r['method'],r['run'],sub)].append(r)
 summaries=[]
 for (model,method,run,sub),rs in groups.items():
  pending=sum(r['factual_f1'] is None for r in rs);known=sum(r['factual_f1'] or 0 for r in rs);n=len(rs)
  acc=[float(r['accuracy']) for r in rs if r['accuracy']!=''];correct=sum(acc);ap=n-len(acc)
  tp=sum(r.get('factual_tp',0) for r in rs);fp=sum(r.get('factual_fp',0) for r in rs);fn=sum(r.get('factual_fn',0) for r in rs)
  s={'model':model,'method':method,'run':run,'subset':sub,'n':n,'accuracy':correct/n if not ap else None,'accuracy_lower_bound':correct/n,'accuracy_upper_bound':(correct+ap)/n,'accuracy_pending':ap,'bertscore_f1':statistics.mean(float(r['bertscore_f1']) for r in rs),'factual_f1':known/n if not pending else None,'factual_f1_lower_bound':known/n,'factual_f1_upper_bound':(known+pending)/n,'factual_pending':pending,'factual_micro_f1':2*tp/(2*tp+fp+fn) if not pending and 2*tp+fp+fn else None}
  summaries.append(s)
 write_rows(a.output/'per_run.csv',summaries)
 full=[r for r in summaries if r['method']=='s_cot_raps'];abl=[r for r in summaries if r['subset']=='all']
 write_rows(a.output/'model_comparison.csv',full);write_rows(a.output/'ablation.csv',abl)
 write_rows(a.output/'factual_review.csv',[r for r in rows if r['factual_f1'] is None])
 lines=['# Accuracy、Factual F1、BERTScore F1 单次结果','','沿用先前按 Accuracy 选出的单次 run，未按新增 Factual F1 重新择优。S=85，C=65，全部=150。','Factual F1 为逐题 F1 的宏平均；范围表示语义待复核项的上下界，不是置信区间。','仅 Factual F1 移除闭合 <think> 内部内容，Accuracy/BERTScore 沿用已有评分；三个指标当前输入预处理并不完全一致。','']
 def fmt(r,m):
  if r[m] is not None:return f'{100*r[m]:.2f}%'
  return f"{100*r[m+'_lower_bound']:.2f}%–{100*r[m+'_upper_bound']:.2f}%"
 for title,rs in [('完整方法 S/C/全部',full),('消融全部题',abl)]:
  lines+=['## '+title,'','| 模型 | 方法 | 子集 | run | Accuracy | Factual F1 | BERTScore F1 | Factual 待复核 |','|---|---|---|---:|---:|---:|---:|---:|']
  for r in rs:lines.append(f"| {r['model']} | {r['method']} | {r['subset']} | {r['run']} | {fmt(r,'accuracy')} | {fmt(r,'factual_f1')} | {fmt(r,'bertscore_f1')} | {r['factual_pending']} |")
  lines.append('')
 lines+=['规则只评价对应题型能提取的参考事实，不能检测所有自然语言中的额外断言；抽取失败也可能导致低分。功能改写保留人工复核。最终论文使用前须抽查错误及提取规则。']
 if all('final_answer' in r for r in rows):
  lines=[line.replace('仅 Factual F1 移除闭合 <think> 内部内容，Accuracy/BERTScore 沿用已有评分；三个指标当前输入预处理并不完全一致。','三项指标统一使用 final_answer；原始 answer 保留。长答案采用窗口编码＋全局匹配的 BERTScore 变体，不丢弃尾部 token；短答案使用标准 BERTScore。') for line in lines]
 (a.output/'summary.md').write_text('\n'.join(lines)+'\n')
 (a.output/'manifest.json').write_text(json.dumps({'version':VERSION,'input':str(a.input),'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).with_name('factual_f1.py').read_bytes()).hexdigest(),'records':len(rows),'aggregation':'macro average of per-question F1; micro also in CSV','preprocessing':'strip closed think blocks for factual F1 only'},indent=2))
 print('records',len(rows),'pending',sum(r['factual_f1'] is None for r in rows))
if __name__=='__main__':main()
