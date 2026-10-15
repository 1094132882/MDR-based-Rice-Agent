"""Apply hash-bound human verdicts to saved scores without running evaluators."""
import argparse,csv,json,hashlib,shutil,collections
from pathlib import Path
from .run import read_rows,write_rows

def checksum(text):return hashlib.sha256(text.encode()).hexdigest()
def key(r):return '|'.join(r[k] for k in ['model','method','run','sample_id'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--verdicts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Choose a new output directory')
 rows=read_rows(a.input/'per_question.csv');vs=json.loads(a.verdicts.read_text());byid={v['id']:v for v in vs['records']}
 if len(byid)!=len(vs['records']):raise ValueError('Duplicate verdict')
 review=[]
 for r in rows:
  if key(r) not in byid:continue
  v=byid[key(r)]
  for field in ['question','ground_truth','answer','final_answer']:
   if checksum(r[field])!=v['sha256'][field]:raise ValueError('Verdict input changed: '+key(r))
  if r['split']!='type11' or r['accuracy']!='' or r['factual_f1']!='':raise ValueError('Only pending single-function facts supported')
  if v['accuracy']!=0 or v['factual_f1']!=0:raise ValueError('This workflow only supports explicit incorrect verdicts')
  r.update(accuracy=0,accuracy_status='human_incorrect',accuracy_reason=v['reason'],factual_precision=0.,factual_recall=0.,factual_f1=0.,factual_status='human_incorrect',factual_tp=0,factual_fp=1,factual_fn=1,factual_reference_atoms=json.dumps([['function','annotation','reference']]),factual_prediction_atoms=json.dumps([['function','annotation','unmatched']]),human_review_source=vs['decision_source'])
  review.append(dict(r))
 if len(review)!=len(byid):raise ValueError('Missing verdict target')
 shutil.copytree(a.input,a.output)
 for name in ['validation.md','validation.json']:
  if (a.output/name).exists():(a.output/name).rename(a.output/('before_review_'+name))
 write_rows(a.output/'per_question.csv',rows);write_rows(a.output/'closed_reviews.csv',review)
 shutil.copyfile(a.verdicts,a.output/'human_verdicts.json')
 with (a.output/'factual_review.csv').open('w',encoding='utf-8-sig') as f:f.write('model,method,run,sample_id,factual_status\n')
 groups=collections.defaultdict(list)
 for r in rows:
  for sub in ['all',r['difficulty']]:groups[(r['model'],r['method'],r['run'],sub)].append(r)
 summaries=read_rows(a.input/'per_run.csv')
 for s in summaries:
  rs=groups[tuple(s[k] for k in ['model','method','run','subset'])];n=len(rs)
  ac=sum(float(r['accuracy']) for r in rs if r['accuracy']!='');ap=sum(r['accuracy']=='' for r in rs)
  ff=sum(float(r['factual_f1']) for r in rs if r['factual_f1']!='');pending=sum(r['factual_f1']=='' for r in rs)
  tp,fp,fn=[sum(int(r[k] or 0) for r in rs) for k in ['factual_tp','factual_fp','factual_fn']]
  s.update(accuracy=ac/n if not ap else '',accuracy_lower_bound=ac/n,accuracy_upper_bound=(ac+ap)/n,accuracy_pending=ap,factual_f1=ff/n if not pending else '',factual_f1_lower_bound=ff/n,factual_f1_upper_bound=(ff+pending)/n,factual_pending=pending,factual_micro_f1=2*tp/(2*tp+fp+fn) if not pending and 2*tp+fp+fn else '')
 write_rows(a.output/'per_run.csv',summaries);full=[s for s in summaries if s['method']=='s_cot_raps'];abl=[s for s in summaries if s['subset']=='all']
 write_rows(a.output/'model_comparison.csv',full);write_rows(a.output/'ablation.csv',abl)
 lines=['# 三指标结果：统一最终回答＋人工复核','','沿用固定单次run；20条Baseline功能记录依用户人工审核判为错误，待复核0条。','BERTScore原数值完整保留；长文本使用窗口编码全局匹配变体。此次未重跑任何模型或评分器。','']
 for title,ss in [('完整方法',full),('消融全部题',abl)]:
  lines+=['## '+title,'','| 模型 | 方法 | 子集 | run | Accuracy | Factual F1 | BERTScore F1 |','|---|---|---|---:|---:|---:|---:|']
  for s in ss:lines.append('| '+' | '.join([s['model'],s['method'],s['subset'],s['run']]+[f'{float(s[k])*100:.2f}%' for k in ['accuracy','factual_f1','bertscore_f1']])+' |')
  lines.append('')
 lines+=['20条功能按当前整块单事实定义赋F1=0；这不是将功能拆成多个事实的人工标注。事实抽取盲区、best-of-N及基因ID分词问题仍需披露。']
 (a.output/'summary.md').write_text('\n'.join(lines)+'\n')
 manifest=json.loads((a.output/'manifest.json').read_text());manifest.update(human_adjudication={'source':vs['decision_source'],'records':len(review),'verdicts_sha256':hashlib.sha256(a.verdicts.read_bytes()).hexdigest(),'previous_results':str(a.input),'bertscore_unchanged':True});(a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 (a.output/'validation.json').write_text(json.dumps({'records':len(rows),'adjudications_applied':len(review),'pending_accuracy':sum(r['accuracy']=='' for r in rows),'pending_factual':sum(r['factual_f1']=='' for r in rows),'bertscore_unchanged':True},indent=2))
 (a.output/'validation.md').write_text('人工复核已应用；旧验证报告保存为before_review文件。最终结果以per_question.csv和summary.md为准；原复制的中间检查点仍是人工复核前数据。\n')
 print('Applied human incorrect verdicts:',len(review))
if __name__=='__main__':main()
