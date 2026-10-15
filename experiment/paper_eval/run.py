"""Re-score saved outputs without invoking the rice Agent or changing old results.

python -m experiment.paper_eval.run --output experiment/results_paper_v1
Use --accuracy-only to run without neural-model packages.
"""
import argparse
import collections
import csv
import hashlib
import importlib.metadata
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from .accuracy import VERSION, make_reference, score_accuracy
from .preprocessing import prepare_answer

ROOT=Path(__file__).resolve().parents[2]
METHODS=['baseline','mdr_static','no_gotci','s_cot_raps']
MODELS={'DeepSeek-V3':'experiment/results_models/deepseek_v3_0324','GPT-4o':'experiment/results_models/gpt4o','MiniMax-M2.5':'experiment/results_models/minimax_m2_5','Qwen3-14B':'experiment/results_final'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read_rows(path):
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_rows(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def load_inputs():
    dataset=read_rows(ROOT/'methods/s_cot_raps/dataset.csv')
    byq={r['question']:(i,r,make_reference(r)) for i,r in enumerate(dataset)}
    if len(byq)!=len(dataset):raise ValueError('Duplicate dataset questions')
    difficulty=json.loads((Path(__file__).with_name('difficulty.json')).read_text())
    mapping=difficulty['question_mapping']
    if set(mapping)!=set(byq):raise ValueError('Difficulty map does not match dataset')
    refs=[{'sample_id':i,**row,**ref,'difficulty':mapping[row['question']]} for i,row,ref in byq.values()]
    errors=[r for r in refs if r['reference_status']!='valid']
    if errors:raise ValueError('Invalid references: '+str([(x['sample_id'],x['reference_issues']) for x in errors]))
    output=[];sources=[]
    for model,folder in MODELS.items():
        for method in METHODS:
            files=sorted((ROOT/folder).glob(method+'_run*.csv'))
            if not files:raise ValueError(f'Missing outputs for {model}/{method}')
            for p in files:
                run=int(p.stem.rsplit('_run',1)[1]);seen=set()
                rows=read_rows(p)
                for original in rows:
                    if original['question'] not in byq:raise ValueError(f'Unknown question in {p}')
                    sample,row,ref=byq[original['question']]
                    if sample in seen:raise ValueError(f'Duplicate sample in {p}')
                    seen.add(sample)
                    if original['ground_truth'].strip()!=row['ground_truth'].strip():raise ValueError(f'Changed reference in {p}:{sample}')
                    answer=original.get('answer','')
                    prepared=prepare_answer(answer)
                    if prepared['answer_preprocessing_status']!='ok':raise ValueError(f'Malformed reasoning tags require review: {p}:{sample}')
                    scored=score_accuracy(ref,prepared['final_answer'],original.get('error',''))
                    output.append({'model':model,'method':method,'run':run,'sample_id':sample,'split':row['split'],'difficulty':mapping[row['question']],'question':row['question'],'ground_truth':row['ground_truth'],'answer':answer,'generation_error':original.get('error',''),'legacy_is_correct':original.get('is_correct',''),'source_file':str(p.relative_to(ROOT)),**prepared,**scored})
                if len(seen)!=150:raise ValueError(f'Incomplete run {p}: {len(seen)} samples')
                sources.append({'file':str(p.relative_to(ROOT)),'sha256':digest(p),'rows':len(rows)})
    return refs,output,sources

def summarize(rows):
    result=[]
    groups=collections.defaultdict(list)
    for r in rows:
        for subset in ['all',r['difficulty']]:groups[(r['model'],r['method'],r['run'],subset)].append(r)
    for (model,method,run,subset),rs in sorted(groups.items()):
        correct=sum(r['accuracy']==1 for r in rs);pending=sum(r['accuracy'] is None for r in rs)
        f1=[r.get('bertscore_f1') for r in rs if r.get('bertscore_f1') is not None]
        result.append({'model':model,'method':method,'run':run,'subset':subset,'n':len(rs),'accuracy':correct/len(rs) if not pending else None,'accuracy_lower_bound':correct/len(rs),'accuracy_upper_bound':(correct+pending)/len(rs),'accuracy_review_pending':pending,'bertscore_f1':statistics.mean(f1) if len(f1)==len(rs) else None,'bertscore_scored':len(f1),'bertscore_truncated':sum(bool(r.get('bertscore_truncated')) for r in rs)})
    return result

def aggregate(per_run):
    groups=collections.defaultdict(list)
    for r in per_run:groups[(r['model'],r['method'],r['subset'])].append(r)
    result=[]
    for (model,method,subset),rs in sorted(groups.items()):
        row={'model':model,'method':method,'subset':subset,'runs':','.join(str(r['run']) for r in rs),'n_per_run':rs[0]['n'],'run_count':len(rs),'accuracy_review_pending':sum(r['accuracy_review_pending'] for r in rs),'bertscore_truncated':sum(r['bertscore_truncated'] for r in rs)}
        for metric in ['accuracy','accuracy_lower_bound','accuracy_upper_bound','bertscore_f1']:
            values=[r[metric] for r in rs if r[metric] is not None]
            row[metric+'_mean']=statistics.mean(values) if len(values)==len(rs) else None
            row[metric+'_sd']=statistics.stdev(values) if len(values)>1 and len(values)==len(rs) else None
        result.append(row)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--accuracy-only',action='store_true')
    p.add_argument('--bert-model',default='google-bert/bert-base-chinese')
    p.add_argument('--bert-snapshot',type=Path,help='Locally verified snapshot with source.json')
    p.add_argument('--bert-revision',help='HF commit ID; resolved and recorded when omitted')
    p.add_argument('--preprocessing',choices=['raw','legacy-jieba'],default='legacy-jieba')
    p.add_argument('--long-text-policy',choices=['window-global','legacy-truncate'],default='window-global')
    p.add_argument('--batch-size',type=int,default=8)
    p.add_argument('--cpu-threads',type=int,default=4)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    # New output directories prevent replacement of published or earlier runs.
    if (args.output/'per_question.csv').exists():raise SystemExit('Output already exists; choose a new directory')
    refs,rows,sources=load_inputs()
    config={'created_at':datetime.now(timezone.utc).isoformat(),'accuracy_version':VERSION,'accuracy_source_sha256':digest(Path(__file__).with_name('accuracy.py')),'difficulty_sha256':digest(Path(__file__).with_name('difficulty.json')),'dataset_sha256':digest(ROOT/'methods/s_cot_raps/dataset.csv'),'sources':sources,'metrics':['accuracy'] if args.accuracy_only else ['accuracy','bertscore_f1'],'preprocessing':args.preprocessing,'metric_answer_field':'final_answer','long_text_policy':args.long_text_policy,'aggregation':'all available runs; no best-run selection; arithmetic mean per question then per run','bert_model':args.bert_model,'bert_layers':8,'bert_idf':False,'bert_rescale_with_baseline':False,'device':'cpu','cpu_threads':args.cpu_threads,'accuracy_pending_policy':'no point estimate until adjudicated; full-N lower/upper bounds','generation_error_policy':'Accuracy=0 and BERTScore=0; all samples remain in denominator'}
    (args.output/'references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2)+'\n')
    # Always checkpoint deterministic results before neural scoring.
    write_rows(args.output/'accuracy_per_question.csv',rows)
    if not args.accuracy_only:
        from .bertscore import score_rows
        config.update(score_rows(rows,args))
    per_run=summarize(rows);agg=aggregate(per_run)
    write_rows(args.output/'per_question.csv',rows);write_rows(args.output/'per_run.csv',per_run)
    write_rows(args.output/'model_comparison.csv',[r for r in agg if r['method']=='s_cot_raps'])
    write_rows(args.output/'ablation.csv',[r for r in agg if r['subset']=='all'])
    write_rows(args.output/'accuracy_review.csv',[r for r in rows if r['accuracy'] is None])
    for package in ['bert-score','torch','transformers','jieba']:
        try:config.setdefault('versions',{})[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    (args.output/'manifest.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    from .report import generate_report
    generate_report(args.output)
    print(f'Saved {len(rows)} answers across {len(sources)} runs to {args.output}',flush=True)
    print('Accuracy manual reviews:',sum(r['accuracy'] is None for r in rows),flush=True)

if __name__=='__main__':main()
