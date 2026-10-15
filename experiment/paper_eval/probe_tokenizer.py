"""Offline tokenizer discrimination audit; no embedding/model inference."""
import argparse,csv,json,re,collections,hashlib
from pathlib import Path
from transformers import AutoTokenizer
from .accuracy import GENE,SV,normalize
from .run import read_rows,write_rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--xlm-snapshot',type=Path,required=True);p.add_argument('--bert-snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Choose a new output directory')
 a.output.mkdir(parents=True)
 bert=AutoTokenizer.from_pretrained(a.bert_snapshot,local_files_only=True,use_fast=False)
 xlm=AutoTokenizer.from_pretrained(a.xlm_snapshot,local_files_only=True,use_fast=True)
 rows=read_rows(a.input);entities=collections.defaultdict(set)
 patterns={'gene':GENE,'sv':SV,'ogi':r'OGI:\d{6,10}','mutant':r'22NB[A-Z]\d+'}
 for r in rows:
  for field in ['question','ground_truth','final_answer']:
   for kind,pattern in patterns.items():
    for m in re.finditer(pattern,normalize(r[field]),re.I):entities[kind].add(m.group())
 results=[];summary={};collisions=[]
 for kind,values in entities.items():
  summary[kind]={'surface_forms':len(values)}
  for label,t in [('bert-base-chinese',bert),('xlm-roberta-base',xlm)]:
   sequences=collections.defaultdict(list);unknown=[];roundtrip=[]
   for value in sorted(values):
    ids=t.encode(value,add_special_tokens=False,truncation=False);sequences[tuple(ids)].append(value)
    unk=t.unk_token_id in ids
    if unk:unknown.append(value)
    decoded=t.decode(ids,skip_special_tokens=True)
    if decoded.replace(' ','')!=value.replace(' ',''):roundtrip.append(value)
    results.append({'kind':kind,'model':label,'id':value,'token_ids':json.dumps(ids),'tokens':json.dumps(t.convert_ids_to_tokens(ids),ensure_ascii=False),'has_unk':unk,'decoded':decoded})
   cs=[vs for vs in sequences.values() if len({v.casefold() for v in vs})>1]
   collisions.extend({'kind':kind,'model':label,'ids':vs} for vs in cs)
   summary[kind][label]={'unk_surface_forms':len(unknown),'distinct_id_collision_groups':len(cs),'collision_surface_forms':sum(len(vs) for vs in cs),'roundtrip_mismatches':len(roundtrip),'unknown_examples':unknown[:5]}
 write_rows(a.output/'id_tokens.csv',results)
 # Actual wrong-answer cases, retaining the same jieba policy for fair tokenizer comparison.
 import jieba
 cache=a.output/'jieba_cache';cache.mkdir();jieba.dt.tmp_dir=str(cache)
 case_results=[]
 for r in rows:
  if r['model']=='MiniMax-M2.5' and r['method']=='s_cot_raps' and r['sample_id'] in ['20','23']:
   item={'sample_id':r['sample_id'],'question':r['question'],'answer':r['final_answer'],'reference':r['ground_truth']}
   for label,t in [('bert',bert),('xlm',xlm)]:
    ca=' '.join(jieba.cut(r['final_answer']));ref=' '.join(jieba.cut(r['ground_truth']))
    ci=t.encode(ca,add_special_tokens=False,truncation=False);ri=t.encode(ref,add_special_tokens=False,truncation=False)
    item[label+'_same_token_sequence']=ci==ri;item[label+'_candidate_unk_count']=ci.count(t.unk_token_id);item[label+'_reference_unk_count']=ri.count(t.unk_token_id)
    item[label+'_candidate_tokens']=t.convert_ids_to_tokens(ci);item[label+'_reference_tokens']=t.convert_ids_to_tokens(ri)
   case_results.append(item)
 # Controlled one-digit substitutions test near-identical strings, not biological annotations.
 controls=[]
 for gene in sorted(entities['gene']):
  matches=list(re.finditer(r'\d',gene))
  if not matches:continue
  i=matches[-1].start();other=gene[:i]+str((int(gene[i])+1)%10)+gene[i+1:]
  controls.append({'id':gene,'perturbed':other,'xlm_distinguishes':xlm.encode(gene,add_special_tokens=False)!=xlm.encode(other,add_special_tokens=False),'bert_distinguishes':bert.encode(gene,add_special_tokens=False)!=bert.encode(other,add_special_tokens=False)})
 write_rows(a.output/'one_digit_controls.csv',controls)
 (a.output/'actual_error_cases.json').write_text(json.dumps(case_results,ensure_ascii=False,indent=2));(a.output/'collisions.json').write_text(json.dumps(collisions,ensure_ascii=False,indent=2))
 manifest={'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'xlm_source':json.loads((a.xlm_snapshot/'source.json').read_text()),'xlm_tokenizer_class':type(xlm).__name__,'summary':summary,'controls':{'n':len(controls),'xlm_distinguishes':sum(c['xlm_distinguishes'] for c in controls),'bert_distinguishes':sum(c['bert_distinguishes'] for c in controls)},'neural_inference_performed':False,'collision_definition':'different IDs ignoring case share exactly identical token-ID sequences; original surface forms retained'}
 (a.output/'results.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print(json.dumps(manifest['summary'],ensure_ascii=False,indent=2));print('Controls',manifest['controls']);print('Cases',[(c['sample_id'],c['bert_same_token_sequence'],c['xlm_same_token_sequence']) for c in case_results])
if __name__=='__main__':main()
