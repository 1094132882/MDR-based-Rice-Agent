"""Typed reference-fact multiset F1; function paraphrases require review."""
import collections,json,re
from .accuracy import parse_facts,normalize,entities,GENE,score_accuracy
VERSION='rice-factual-f1-v1'
def final_answer(text):
 from .preprocessing import prepare_answer
 prepared=prepare_answer(text)
 if prepared['answer_preprocessing_status']!='ok':raise ValueError('Malformed reasoning tags require review')
 return prepared['final_answer']
def atoms(facts,scope):
 result=[]
 for field,value in facts.items():
  if field in ['function','accessions']:continue
  if field=='position':result.extend((scope,k,str(v)) for k,v in zip(['start','end'],value))
  elif isinstance(value,dict):result.extend((scope,field+':'+str(k),str(v)) for k,v in value.items())
  elif isinstance(value,list):result.extend((scope,field,str(v)) for v in value)
  else:result.append((scope,field,str(value)))
 return collections.Counter(result)
def score_factual_f1(reference,answer,error=''):
 text=final_answer(answer);kind=reference['kind'];expected=reference['facts']
 if reference['reference_status']!='valid':return {'factual_precision':None,'factual_recall':None,'factual_f1':None,'factual_status':'reference_review'}
 accuracy=score_accuracy(reference,text,error)
 from .preprocessing import generation_failed
 failed=generation_failed(text,error)
 if kind=='function':
  if accuracy['accuracy'] is None and not failed:return {'factual_precision':None,'factual_recall':None,'factual_f1':None,'factual_status':'semantic_review'}
  ref=atoms({'annotation':'reference'},'function');pred=collections.Counter() if failed else atoms({'annotation':'reference' if accuracy['accuracy']==1 else 'unmatched'},'function')
 else:
  actual=parse_facts(text,kind,reference['target']);scope=reference['target'] or 'question';pred_scope=scope
  if reference['target'] and kind in ['location','strand','expression','url','ogi','ogi_count']:
   mentioned=entities(GENE,normalize(text))
   if mentioned and mentioned!=[reference['target']]:pred_scope='ambiguous-or-other-gene:'+','.join(mentioned)
  ref=atoms(expected,scope);pred=collections.Counter() if failed else atoms(actual,pred_scope)
 tp=sum((ref & pred).values());fp=sum(pred.values())-tp;fn=sum(ref.values())-tp
 precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.
 f1=2*precision*recall/(precision+recall) if precision+recall else 0.
 return {'factual_precision':precision,'factual_recall':recall,'factual_f1':f1,'factual_status':'generation_failed' if failed else 'scored','factual_tp':tp,'factual_fp':fp,'factual_fn':fn,'factual_reference_atoms':json.dumps(list(ref.elements()),ensure_ascii=False),'factual_prediction_atoms':json.dumps(list(pred.elements()),ensure_ascii=False)}
