"""Reevaluate fixed selected runs using a shared final answer; no generation/API."""
import argparse,json,sys,importlib.metadata
from pathlib import Path
from .run import read_rows,write_rows,digest
from .accuracy import make_reference,score_accuracy
from .preprocessing import prepare_answer,VERSION
from .bertscore import score_rows
from . import factual_run

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--bert-snapshot',type=Path,required=True);p.add_argument('--batch-size',type=int,default=8);a=p.parse_args()
 if a.output.exists():raise SystemExit('Choose a new output directory')
 a.output.mkdir(parents=True);rows=read_rows(a.input)
 for r in rows:
  r.update(prepare_answer(r['answer']))
  if r['answer_preprocessing_status']!='ok':raise ValueError('Malformed reasoning tags require manual review: '+str((r['model'],r['method'],r['sample_id'])))
  r.update(score_accuracy(make_reference(r),r['final_answer'],r.get('generation_error','')))
  # Remove inherited neural scores so stale values cannot survive partial scoring.
  for k in list(r):
   if k.startswith('bertscore_'):del r[k]
 write_rows(a.output/'preprocessed_per_question.csv',rows)
 a.bert_model='google-bert/bert-base-chinese';a.bert_revision=None;a.cpu_threads=4;a.preprocessing='legacy-jieba';a.long_text_policy='window-global'
 config={'input':str(a.input),'input_sha256':digest(a.input),'preprocessing_version':VERSION,'metric_answer_field':'final_answer','raw_answer_field':'answer','run_selection':'unchanged from input; no reselection','failure_policy':'common empty/error/no-result markers score zero for all metrics','bert_preprocessing':a.preprocessing}
 config.update(score_rows(rows,a))
 write_rows(a.output/'scored_input.csv',rows)
 original=sys.argv
 try:
  sys.argv=['factual_run','--input',str(a.output/'scored_input.csv'),'--output',str(a.output)];factual_run.main()
 finally:sys.argv=original
 config['versions']={k:importlib.metadata.version(k) for k in ['bert-score','torch','transformers','jieba']}
 config['code_sha256']={k:digest(Path(__file__).with_name(k)) for k in ['preprocessing.py','bertscore.py','long_bertscore.py','unified_run.py','accuracy.py','factual_f1.py']}
 config['rows']=len(rows);config['think_records']=sum(r['think_blocks_removed']>0 for r in rows);config['long_records']=sum(r.get('bertscore_variant')=='window-encoded-global-greedy-v1' for r in rows);config['truncated_records']=sum(r['bertscore_truncated'] for r in rows)
 previous=json.loads((a.output/'manifest.json').read_text());previous.update(config);(a.output/'manifest.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2))
 print(json.dumps({k:config[k] for k in ['rows','think_records','long_records','truncated_records']}),flush=True)
if __name__=='__main__':main()
