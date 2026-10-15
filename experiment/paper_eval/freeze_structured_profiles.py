"""Freeze author-approved Gold contracts. No historical answer scoring."""
import argparse
import collections
import csv
import hashlib
import json
import shutil
from pathlib import Path
from .structured_facts_v2 import build_profile, digest, VERSION


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(gold, difficulty, output):
    if output.exists():raise FileExistsError('Use a new output directory; profiles are immutable')
    mapping=json.loads(difficulty.read_text())['question_mapping']
    with gold.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    if len(rows)!=150:raise ValueError('Expected 150 Gold questions')
    profiles=[]
    for i,row in enumerate(rows):
        p=build_profile(row,i)
        # Difficulty is provenance, not part of the mathematical scoring profile.
        p['difficulty']=mapping[row['question']]
        p.pop('profile_sha256')
        p['profile_sha256']=digest(json.dumps(p,ensure_ascii=False,sort_keys=True))
        if p['profile_status']!='valid':raise ValueError(f'Gold profile {i} requires review: {p["profile_issues"]}')
        profiles.append(p)
    if collections.Counter(p['difficulty'] for p in profiles)!={'S':85,'C':65}:raise ValueError('Difficulty mismatch')
    output.mkdir(parents=True)
    (output/'profiles.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2))
    counts=[]
    for t in range(1,30):
        ps=[p for p in profiles if p['type']==t]
        counts.append({'type':f'type{t}','mode':ps[0]['mode'],'questions':len(ps),'S':sum(p['difficulty']=='S' for p in ps),'C':sum(p['difficulty']=='C' for p in ps),'core_fact_counts':','.join(str(len(p['required_facts'])) for p in ps)})
    with (output/'type_rules.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(counts[0]));w.writeheader();w.writerows(counts)
    module=Path(__file__).parent
    files=['structured_facts_v2.py','freeze_structured_profiles.py','test_structured_facts_v2.py','preprocessing.py','fixtures/structured_counterexamples.json','structured_run_v2.py','test_structured_run_v2.py']
    for name in files:
        dest=output/'scoring_code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(module/name,dest)
    manifest={'scorer_version':VERSION,'contract':'type-and-gold-fields-author-approved-v1',
              'Gold_source':str(gold.resolve()),'Gold_sha256':sha(gold),'difficulty_sha256':sha(difficulty),
              'profiles_sha256':sha(output/'profiles.json'),'records':150,'types':29,'S':85,'C':65,
              'scoring_code_sha256':{name:sha(module/name) for name in files},
              'historical_answers_scored':0,'model_calls':0,'historical_runs_changed':False,
              'SV_partial_scope_sample_ids':[124,127,128,129],
              'SV_missing_type_policy':'unknown, never fill zero; explicit unverified counts require review',
              'author_exception_95':'member list only; direction not scored',
              'annotation_granularity':'single gene+annotation; source conflict checked, no automatic paraphrase equivalence',
              'manual_review_policy':'do not inherit numeric verdicts across changed fact contracts without hash and semantic applicability checks'}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    return profiles


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gold',type=Path,required=True);p.add_argument('--difficulty',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();ps=freeze(a.gold,a.difficulty,a.output);print('Frozen Gold profiles:',len(ps))

if __name__=='__main__':main()
