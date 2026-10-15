"""Replace only BERTScore on reviewed fixed runs; preserve all other fields."""
import argparse,collections,csv,json,math,statistics,hashlib,importlib.metadata,shutil
from pathlib import Path
from datetime import datetime,timezone
from transformers import AutoTokenizer
from .run import read_rows,write_rows,digest
from .bertscore import score_rows
from .accuracy import GENE,normalize
import re

def identity(r):return tuple(r[k] for k in ['model','method','run','sample_id'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--bert-snapshot',type=Path,required=True);p.add_argument('--batch-size',type=int,default=8);a=p.parse_args()
 if a.output.exists():raise SystemExit('Choose new output directory')
 old=read_rows(a.input/'per_question.csv');assert len(old)==2400 and len({identity(r) for r in old})==2400
 assert all(r['accuracy']!='' and r['factual_f1']!='' and 'final_answer' in r for r in old)
 a.output.mkdir(parents=True);sources=Path(__file__).parent;frozen=a.output/'scoring_code';frozen.mkdir()
 for name in ['xlm_only_run.py','bertscore.py','long_bertscore.py','audited_bertscore.py','preprocessing.py']:
  shutil.copyfile(sources/name,frozen/name)
 config={'created_at':datetime.now(timezone.utc).isoformat(),'source_directory':str(a.input),'input_sha256':digest(a.input/'per_question.csv'),'model':'FacebookAI/xlm-roberta-base','revision':'e73636d4f797dec63c3081bb6ed5c7b0bb3f2089','layers':9,'layer_choice':'BERTScore model2layers preset, not tuned','lang':'zh','idf':False,'rescale_with_baseline':False,'use_fast_tokenizer':False,'device':'cpu','preprocessing':'legacy-jieba on stored final_answer and ground_truth; no further answer selection','long_text_policy':'window-encoded-global-greedy-v1 unchanged','max_total_window_tokens':512,'max_payload_window_tokens':510,'window_overlap':0,'matching':'global many-to-one greedy cosine matching; CLS/SEP weight zero but remain matching targets (same existing definition)','length_normalization':'sum of non-special token weights separately for candidate and reference; harmonic mean P/R','generation_failure_policy':'same as source: zero for existing common failure markers; no dropped records','run_selection':'unchanged','human_adjudication':json.loads((a.input/'manifest.json').read_text()).get('human_adjudication'),'versions':{k:importlib.metadata.version(k) for k in ['bert-score','transformers','torch','sentencepiece','jieba','tokenizers']},'code_sha256':{p.name:digest(p) for p in frozen.iterdir()}}
 (a.output/'manifest.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
 a.bert_model=config['model'];a.bert_revision=config['revision'];a.bert_layers=9;a.cpu_threads=4;a.preprocessing='legacy-jieba';a.long_text_policy='window-global';a.audit_long_matching=True
 rows=[]
 for previous in old:
  r={k:v for k,v in previous.items() if not k.startswith('bertscore_')};r['previous_bertscore_f1']=previous['bertscore_f1'];rows.append(r)
 config.update(score_rows(rows,a));write_rows(a.output/'per_question.csv',rows)
 # Restore no protected field from a recalculation; exact per-row equality required.
 for before,after in zip(old,rows):
  assert all(after[k]==v for k,v in before.items() if not k.startswith('bertscore_'))
  assert math.isfinite(after['bertscore_f1']) and not after['bertscore_truncated']
 groups=collections.defaultdict(list)
 for r in rows:
  for subset in ['all',r['difficulty']]:groups[(r['model'],r['method'],r['run'],subset)].append(r)
 summaries=read_rows(a.input/'per_run.csv')
 for s in summaries:
  rs=groups[tuple(s[k] for k in ['model','method','run','subset'])]
  s['previous_bertscore_f1']=s['bertscore_f1'];s['bertscore_f1']=statistics.mean(r['bertscore_f1'] for r in rs)
  s['bertscore_f1_delta']=s['bertscore_f1']-float(s['previous_bertscore_f1']);s['bertscore_assigned']=len(rs);s['bertscore_neural_scored']=sum(r['bertscore_status']=='scored' for r in rs);s['bertscore_generation_failed']=sum(r['bertscore_status']=='generation_failed' for r in rs);s['bertscore_windowed']=sum(r.get('bertscore_variant')=='window-encoded-global-greedy-v1' for r in rs)
  assert len(rs)==int(s['n'])
 write_rows(a.output/'per_run.csv',summaries);full=[r for r in summaries if r['method']=='s_cot_raps'];abl=[r for r in summaries if r['subset']=='all'];write_rows(a.output/'model_comparison.csv',full);write_rows(a.output/'ablation.csv',abl)
 # Audit every final answer/reference, including policy-zero records, with the same tokenizer.
 tokenizer=AutoTokenizer.from_pretrained(a.bert_snapshot,local_files_only=True,use_fast=False)
 import jieba
 audit=[];gene_forms=set()
 for r in rows:
  c=tokenizer.encode(' '.join(jieba.cut(r['final_answer'])),add_special_tokens=False,truncation=False);ref=tokenizer.encode(' '.join(jieba.cut(r['ground_truth'])),add_special_tokens=False,truncation=False)
  if r['bertscore_status']=='scored':
   assert len(c)==r['bertscore_candidate_payload_tokens'] and len(ref)==r['bertscore_reference_payload_tokens']
   assert r['bertscore_candidate_windows']==max(1,math.ceil(len(c)/510)) and r['bertscore_reference_windows']==max(1,math.ceil(len(ref)/510))
  audit.append({'model':r['model'],'method':r['method'],'run':r['run'],'sample_id':r['sample_id'],'candidate_payload_tokens':len(c),'reference_payload_tokens':len(ref),'candidate_unk':c.count(tokenizer.unk_token_id),'reference_unk':ref.count(tokenizer.unk_token_id),'score_status':r['bertscore_status']})
  for text in [r['question'],r['ground_truth'],r['final_answer']]:gene_forms.update(m.group() for m in re.finditer(GENE,normalize(text),re.I))
 write_rows(a.output/'encoding_audit.csv',audit)
 collision_groups=collections.defaultdict(list);unknown_genes=[]
 for gene in sorted(gene_forms):
  ids=tokenizer.encode(gene,add_special_tokens=False,truncation=False);collision_groups[tuple(ids)].append(gene)
  if tokenizer.unk_token_id in ids:unknown_genes.append(gene)
 collisions=[vs for vs in collision_groups.values() if len({s.casefold() for s in vs})>1]
 (a.output/'gene_token_audit.json').write_text(json.dumps({'surface_forms':len(gene_forms),'unk_genes':unknown_genes,'collisions':collisions,'definition':'original surface forms; IDs differing only in case not considered different biological IDs'},ensure_ascii=False,indent=2))
 statuses=collections.Counter(r['bertscore_status'] for r in rows);long=[r for r in rows if r.get('bertscore_variant')=='window-encoded-global-greedy-v1']
 validation={'records':len(rows),'all_scores_finite':True,'evaluation_failures':0,'score_status_counts':dict(statuses),'protected_fields_unchanged':True,'human_incorrect_records_preserved':sum(r.get('accuracy_status')=='human_incorrect' for r in rows),'run_selection_unchanged':True,'truncated_records':0,'payload_tokens_covered_once':True,'long_records':len(long),'gene_surface_forms':len(gene_forms),'gene_unk_count':len(unknown_genes),'gene_collision_groups':len(collisions),'answers_with_unk':sum(r['candidate_unk']>0 for r in audit),'references_with_unk':sum(r['reference_unk']>0 for r in audit),'candidate_unk_total':sum(r['candidate_unk'] for r in audit),'reference_unk_total':sum(r['reference_unk'] for r in audit),'long_p_special_matches':sum(r['bertscore_p_special_target_tokens'] for r in long),'long_r_special_matches':sum(r['bertscore_r_special_target_tokens'] for r in long),'summary_rows_verified':len(summaries)}
 config.update(validation);(a.output/'manifest.json').write_text(json.dumps(config,ensure_ascii=False,indent=2));(a.output/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
 for name in ['human_verdicts.json','closed_reviews.csv']:
  if (a.input/name).exists():shutil.copyfile(a.input/name,a.output/name)
 lines=['# XLM-R BERTScore重新评价','','源：unified_final_answer_v3_reviewed；固定16个run、2400条，S85/C65/All150。Accuracy、Factual F1及20条人工判定原值完整保留。','XLM-R固定第9层，idf=False，rescale=False，legacy-jieba，CPU；长文本沿用窗口编码＋全局匹配变体，未截断。','']
 for title,ss in [('完整方法 Simple / Complex / All',full),('四模型消融 All',abl)]:
  lines+=['## '+title,'','| 模型 | 方法 | 子集 | run | Accuracy | Factual F1 | 旧中文BERT F1 | 新XLM-R F1 | 变化（百分点） |','|---|---|---|---:|---:|---:|---:|---:|---:|']
  for s in ss:lines.append('| '+' | '.join([s['model'],s['method'],s['subset'],s['run']]+[f'{float(s[k])*100:.2f}%' for k in ['accuracy','factual_f1','previous_bertscore_f1','bertscore_f1']]+[f"{s['bertscore_f1_delta']*100:+.2f}"])+' |')
  lines.append('')
 lines+=['新BERTScore为辅助文本语义相似度，不能判定基因ID/数值是否正确；长文本是已披露的窗口变体，不能冒充原库默认截断配置。']
 (a.output/'summary.md').write_text('\n'.join(lines)+'\n')
 # Full-method known errors; publish all 12, not only selected favorable examples.
 cases=[]
 for r in rows:
  if r['method']=='s_cot_raps' and r['accuracy']=='0':cases.append({k:r[k] for k in ['model','method','run','sample_id','question','ground_truth','final_answer','accuracy','factual_f1','accuracy_reason','previous_bertscore_f1','bertscore_f1']})
 write_rows(a.output/'error_cases.csv',cases)
 report=['# 验证与局限','','## 完整性','','```json',json.dumps(validation,ensure_ascii=False,indent=2),'```','','2400条均获得有限F1；原生成失败按与旧结果相同政策记0，不声称这些条目成功生成答案或经过神经模型打分。全部非BERT字段逐项核对，20条人工错误判定保留。全部48组汇总由逐题得分重建，无丢弃样本。','','## 窗口与匹配定义','','每窗口最多510正文token加首尾特殊token；窗口不重叠，全文token按顺序覆盖一次。Precision和Recall各按全文非特殊token权重之和归一化，再取调和平均，不平均窗口F1。每个窗口失去跨窗口上下文，仍是已披露的BERTScore变体。','贪心匹配允许多对一，这是保留的定义，不是重复计入某个正文token。特殊token不计入分母，但仍可作匹配目标，沿用旧定义；全量诊断计数见JSON。若计数非零，不自动修改算法或隐瞒，应单独分析其影响。','','## 完整方法错误案例','','| 模型 / ID | 旧中文BERT | 新XLM-R | 判定 |','|---|---:|---:|---|']
 for r in cases:report.append(f"| {r['model']} / {r['sample_id']} | {float(r['previous_bertscore_f1'])*100:.4f}% | {float(r['bertscore_f1'])*100:.4f}% | {r['accuracy_reason']} |")
 report+=['','案例20/23为错误基因链接；132为147代替103；104为SV数量/成员错误；11为错误转录本；68/69为邻近列表缺失；47/126/144为未查询到记录。完整原文见error_cases.csv。','XLM-R避免已知ID的UNK完全碰撞，但错误答案仍可能高相似。尤其数字或少量字段变化不应按语义相似度判断正确。','','## 论文适用性','','可以作为辅助语义相似度报告，必须同时报告精确Accuracy/规则Factual F1，并披露窗口变体、分词、固定版本与层数、失败政策、事后best-of-N和模板化答案。不能据此单独证明事实正确性、检索忠实性或组件收益显著。先前参考问题与事实抽取的其他局限未由本次模型切换修复。']
 (a.output/'validation.md').write_text('\n'.join(report)+'\n');print(json.dumps(validation),flush=True)
if __name__=='__main__':main()
