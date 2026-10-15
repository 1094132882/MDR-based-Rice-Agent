"""Score final_answer with frozen XLM-R settings; preserve existing fact scores."""
import argparse
import collections
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from experiment.paper_eval.bertscore import score_rows
from experiment.paper_eval.preprocessing import prepare_answer
from experiment.paper_eval.run import read_rows, write_rows

MODEL = 'FacebookAI/xlm-roberta-base'
REVISION = 'e73636d4f797dec63c3081bb6ed5c7b0bb3f2089'

def summarize(rows):
    groups = collections.defaultdict(list)
    for r in rows:
        for subset in ['all', r['difficulty']]:
            groups[(r['model'], r['method'], r['run'], subset)].append(r)
    out = []
    for key, values in sorted(groups.items()):
        s = dict(zip(['model', 'method', 'run', 'subset'], key)); s['n'] = len(values)
        for field in ['v3_accuracy', 'v3_structured_fact_f1', 'bertscore_f1']:
            known = [float(r[field]) for r in values if r.get(field) not in ['', None]]
            if not all(math.isfinite(v) and 0 <= v <= 1.000001 for v in known):
                raise ValueError('Invalid score: ' + field)
            pending = len(values)-len(known)
            s[field] = sum(known)/len(values) if not pending else ''
            s[field+'_pending'] = pending
            s[field+'_lower_bound'] = sum(known)/len(values)
            s[field+'_upper_bound'] = (sum(known)+pending)/len(values)
        out.append(s)
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bert-snapshot', type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=8)
    a = p.parse_args()
    if a.output.exists(): raise FileExistsError('Choose a fresh output directory')
    rows = read_rows(a.input)
    if not rows: raise ValueError('Empty input')
    for row in rows:
        for field in ['model','method','run','sample_id','answer','final_answer','ground_truth','difficulty','generation_error','v3_accuracy','v3_structured_fact_f1']:
            if field not in row: raise ValueError('Missing field: '+field)
        clean = prepare_answer(row['answer'])
        if clean['answer_preprocessing_status'] != 'ok' or clean['final_answer'] != row['final_answer']:
            raise ValueError('Noncanonical final_answer')
    keys = [tuple(r[k] for k in ['model','method','run','sample_id']) for r in rows]
    if len(set(keys)) != len(keys): raise ValueError('Duplicate identities')
    protected = [{k:v for k,v in r.items() if not k.startswith('bertscore_')} for r in rows]
    a.output.mkdir(parents=True)
    a.bert_model=MODEL; a.bert_revision=REVISION; a.bert_layers=9
    a.cpu_threads=4; a.preprocessing='legacy-jieba'; a.long_text_policy='window-global'; a.audit_long_matching=True
    metadata = score_rows(rows,a)
    for old,r in zip(protected, rows):
        if any(r[k] != v for k,v in old.items()): raise ValueError('Protected field changed')
        if not math.isfinite(r['bertscore_f1']) or r['bertscore_truncated']: raise ValueError('Invalid/truncated score')
    write_rows(a.output/'per_question.csv', rows)
    groups=summarize(rows); write_rows(a.output/'per_group.csv',groups)
    write_rows(a.output/'model_comparison.csv',[s for s in groups if s['method']=='s_cot_raps'])
    write_rows(a.output/'ablation.csv',[s for s in groups if s['subset']=='all'])
    lines=['# Evaluation summary','','Metrics are percentages; pending factual decisions retain full denominators.','','| Model | Method | Run | Subset | n | Accuracy | Structured Fact F1 | BERTScore-F1 |','|---|---|---|---|---:|---:|---:|---:|']
    for s in groups:
        values=[]
        for field in ['v3_accuracy','v3_structured_fact_f1','bertscore_f1']:
            values.append(f'{100*s[field]:.2f}%' if s[field]!='' else f"{100*s[field+'_lower_bound']:.2f}–{100*s[field+'_upper_bound']:.2f}% ({s[field+'_pending']} pending)")
        lines.append('| '+' | '.join([str(s[k]) for k in ['model','method','run','subset','n']]+values)+' |')
    (a.output/'summary.md').write_text('\n'.join(lines)+'\n')
    metadata.update(model=MODEL,revision=REVISION,records=len(rows),run_selection='unchanged',input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),preprocessing='canonical final_answer + legacy-jieba',idf=False,rescale_with_baseline=False,lang='zh',layers=9,device='cpu',payload_window=510,overlap=0,versions={k:importlib.metadata.version(k) for k in ['bert-score','transformers','torch','sentencepiece','jieba','tokenizers']})
    metadata['code_sha256']={str(f.relative_to(Path(__file__).parent)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__), *[Path(__file__).parent/'paper_eval'/name for name in ['bertscore.py','long_bertscore.py','audited_bertscore.py','preprocessing.py']]]}
    (a.output/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
