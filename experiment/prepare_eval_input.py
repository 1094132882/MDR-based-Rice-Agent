"""Attach frozen references and canonical final answers; never score or choose runs."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from experiment.paper_eval.preprocessing import prepare_answer
from experiment.paper_eval.structured_facts_v3 import validate_profile, digest

ROOT = Path(__file__).resolve().parents[1]

def prepare(input_path, output_path, profiles_path):
    if output_path.exists():
        raise FileExistsError('Choose a fresh output path')
    profiles = {str(p['sample_id']): p for p in json.loads(profiles_path.read_text())}
    for p in profiles.values():
        validate_profile(p)
    with input_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not {'model', 'method', 'run', 'sample_id', 'answer'}.issubset(reader.fieldnames or []):
            raise ValueError('Required columns: model,method,run,sample_id,answer')
        rows = list(reader)
    if not rows:
        raise ValueError('Empty input')
    keys = set()
    groups = collections.defaultdict(set)
    for row in rows:
        key = tuple(row[k] for k in ['model', 'method', 'run', 'sample_id'])
        if any(not x.strip() for x in key) or key in keys:
            raise ValueError('Empty or duplicate identity')
        keys.add(key)
        p = profiles[row['sample_id']]
        for field, hash_field in [('question', 'question_sha256'), ('ground_truth', 'gold_sha256')]:
            if row.get(field) and digest(row[field]) != p[hash_field]:
                raise ValueError('Reference mismatch: ' + str(key))
            row[field] = p[field]
        if row.get('difficulty') and row['difficulty'] != p['difficulty']:
            raise ValueError('Difficulty mismatch')
        row['difficulty'] = p['difficulty']
        clean = prepare_answer(row['answer'])
        if clean['answer_preprocessing_status'] != 'ok':
            raise ValueError('Malformed think tags require review: ' + str(key))
        if 'final_answer' in row and row['final_answer'] != clean['final_answer']:
            raise ValueError('Existing final_answer disagrees with canonical preprocessing')
        row.update(clean)
        row['generation_error'] = row.get('generation_error', '') or row.get('error', '')
        groups[key[:3]].add(row['sample_id'])
    if any(ids != set(profiles) for ids in groups.values()):
        raise ValueError('Each supplied model/method/run must contain all 150 questions')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with output_path.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--profiles', type=Path, default=ROOT/'experiment/datasets/gold_profiles.json')
    a = p.parse_args()
    print(json.dumps({'records': prepare(a.input, a.output, a.profiles), 'run_selection': 'unchanged'}))

if __name__ == '__main__':
    main()
