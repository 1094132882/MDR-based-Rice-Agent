"""Explicit batch entry point: fixed saved answers, fresh output, no model calls."""
import argparse
import collections
import csv
import json
from pathlib import Path
from .structured_facts_v3 import score,validate_profile,digest,VERSION


def replay_verdict(profile,row,result,verdict):
    if profile['type']!=11 or len(profile['required_facts'])!=1:
        raise ValueError('Existing verdict applies only to the unchanged single-function contract')
    for field in ['question','ground_truth','answer','final_answer']:
        if digest(row[field])!=verdict['sha256'][field]:raise ValueError('Human verdict input changed: '+field)
    if verdict['accuracy']!=0 or verdict['factual_f1']!=0:raise ValueError('Unsupported verdict')
    if result['status'] in ['preprocessing_review','reference_review'] or result.get('tp',0)>0:
        raise ValueError('Scorer or preprocessing conflicts with saved human verdict; review required')
    result=dict(result)
    # Reuse the separately reviewed F1=0; never obtain it from Accuracy.
    # The old verdict did not annotate every extra claim: do not invent an FP count.
    result.update(accuracy=verdict['accuracy'],structured_fact_f1=verdict['factual_f1'],
                  structured_fact_precision=0.,structured_fact_recall=0.,tp=0,fn=1,
                  fp=result.get('fp') if result['status']=='scored' else None,
                  status='human_incorrect',human_reason=verdict['reason'],human_verdict_id=verdict['id'])
    return result


def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def run(input_file,profile_file,output,expected_records=2400,verdict_file=None):
    if output.exists():raise FileExistsError('Choose a new output directory')
    with input_file.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    if len(rows)!=expected_records:raise ValueError('Unexpected input record count')
    profiles={str(p['sample_id']):p for p in json.loads(profile_file.read_text())}
    for p in profiles.values():validate_profile(p)
    verdicts=json.loads(verdict_file.read_text()) if verdict_file else {'records':[]}
    by_id={v['id']:v for v in verdicts['records']}
    if len(by_id)!=len(verdicts['records']):raise ValueError('Duplicate human verdict IDs')
    keys=[];groups=collections.defaultdict(list)
    for row in rows:
        key='|'.join(row[k] for k in ['model','method','run','sample_id']);keys.append(key)
        p=profiles[row['sample_id']]
        for field,hash_field in [('question','question_sha256'),('ground_truth','gold_sha256')]:
            if digest(row[field])!=p[hash_field]:raise ValueError('Input does not match frozen Gold profile: '+key)
        if row['difficulty']!=p['difficulty']:raise ValueError('Difficulty changed')
        groups[(row['model'],row['method'],row['run'])].append(row)
    if len(set(keys))!=len(keys):raise ValueError('Duplicate input rows')
    if not set(by_id).issubset(keys):raise ValueError('Human verdict targets missing')
    if expected_records==2400:
        if len(groups)!=16 or any({r['sample_id'] for r in rs}!={str(i) for i in range(150)} for rs in groups.values()):
            raise ValueError('Expected 16 fixed cohorts, each containing all 150 questions')
        if len({r['model'] for r in rows})!=4:raise ValueError('Expected four models')
        model_methods=collections.Counter((r['model'],r['method']) for r in rows)
        if any(n!=150 for n in model_methods.values()):raise ValueError('More than one run per model/configuration')
    scored=[];reviews=[];result_groups=collections.defaultdict(list)
    for row,key in zip(rows,keys):
        p=profiles[row['sample_id']];s=score(p,row['final_answer'],row.get('generation_error','') or row.get('error',''))
        if key in by_id:s=replay_verdict(p,row,s,by_id[key])
        if s.get('final_answer',row['final_answer'])!=row['final_answer'].strip():
            raise ValueError('Input final_answer was not already unified: '+key)
        out=dict(row)
        for src,dest in [('accuracy','v3_accuracy'),('structured_fact_precision','v3_precision'),('structured_fact_recall','v3_recall'),('structured_fact_f1','v3_structured_fact_f1'),('tp','v3_tp'),('fp','v3_fp'),('fn','v3_fn'),('status','v3_status')]:
            out[dest]=s.get(src)
        out['v3_details_json']=json.dumps(s,ensure_ascii=False);scored.append(out)
        if s['accuracy'] is None or s['structured_fact_f1'] is None:reviews.append(out)
        for subset in ['all',row['difficulty']]:result_groups[(row['model'],row['method'],row['run'],subset)].append(s)
    summaries=[]
    for (model,method,run_id,subset),rs in sorted(result_groups.items()):
        item={'model':model,'method':method,'run':run_id,'subset':subset,'n':len(rs)}
        for field,label in [('accuracy','accuracy'),('structured_fact_f1','structured_fact_f1')]:
            known=sum(s[field] for s in rs if s[field] is not None);pending=sum(s[field] is None for s in rs)
            item.update({label:known/len(rs) if not pending else None,label+'_pending':pending,
                         label+'_lower_bound':known/len(rs),label+'_upper_bound':(known+pending)/len(rs)})
        summaries.append(item)
    output.mkdir(parents=True)
    write_csv(output/'per_question.csv',scored);write_csv(output/'per_group.csv',summaries)
    if reviews:write_csv(output/'manual_review.csv',reviews)
    else:(output/'manual_review.csv').write_text('model,method,run,sample_id\n')
    lines=['# 新版事实评价结果','','固定输入中的run与分组；保留全部原有评分列，新增v3列。','F1逐题宏平均；待复核项保留固定分母，区间为保守[0,1]边界，不是置信区间。','']
    for title,ss in [('完整方法 Simple / Complex / All',[s for s in summaries if s['method']=='s_cot_raps']),('四种配置 All',[s for s in summaries if s['subset']=='all'])]:
        lines+=['## '+title,'','| 模型 | 配置 | run | 子集 | n | Accuracy | Structured Fact F1 |','|---|---|---|---|---:|---:|---:|']
        for s in ss:
            vals=[]
            for k in ['accuracy','structured_fact_f1']:
                vals.append(f'{100*s[k]:.2f}%' if s[k] is not None else f"{100*s[k+'_lower_bound']:.2f}–{100*s[k+'_upper_bound']:.2f}% ({s[k+'_pending']}待复核)")
            lines.append('| '+' | '.join([str(s[k]) for k in ['model','method','run','subset','n']]+vals)+' |')
        lines.append('')
    (output/'summary.md').write_text('\n'.join(lines))
    manifest={'scoring_version':VERSION,'input':str(input_file),'input_sha256':digest(input_file.read_text(encoding='utf-8-sig')),
              'profiles':str(profile_file),'profiles_sha256':digest(profile_file.read_text()),'records':len(rows),
              'pending':len(reviews),'human_verdicts_replayed':len(by_id),'model_calls':0,'BERTScore_recomputed':False,
              'original_columns_preserved':True,'run_selection_changed':False}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--profiles',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-records',type=int,default=2400)
    p.add_argument('--human-verdicts',type=Path)
    a=p.parse_args();print(json.dumps(run(a.input,a.profiles,a.output,a.expected_records,a.human_verdicts),ensure_ascii=False))

if __name__=='__main__':main()
