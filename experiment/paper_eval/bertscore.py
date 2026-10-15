"""Real BERTScore; score caching never reuses a different preprocessing/model."""
import hashlib
import json
import math
import re
from pathlib import Path

def score_rows(rows,args):
    import torch
    from bert_score import BERTScorer
    from huggingface_hub import HfApi,snapshot_download
    torch.set_num_threads(args.cpu_threads)
    if args.bert_snapshot:
        local=str(args.bert_snapshot)
        source=json.loads((args.bert_snapshot/'source.json').read_text())
        if source['repo']!=args.bert_model:raise ValueError('Snapshot model does not match requested model')
        revision=source['revision']
        if args.bert_revision and args.bert_revision!=revision:raise ValueError('Snapshot revision mismatch')
        h=hashlib.sha256()
        with (args.bert_snapshot/'model.safetensors').open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=source['weights_sha256']:raise ValueError('Snapshot weights SHA mismatch')
    else:
        revision=args.bert_revision or HfApi().model_info(args.bert_model).sha
        local=snapshot_download(args.bert_model,revision=revision,allow_patterns=['config.json','vocab.txt','tokenizer.json','tokenizer_config.json','special_tokens_map.json','model.safetensors'])
    scorer=BERTScorer(model_type=local,num_layers=getattr(args,'bert_layers',8),lang='zh',idf=False,rescale_with_baseline=False,device='cpu',batch_size=args.batch_size,use_fast_tokenizer=False)
    if args.preprocessing=='legacy-jieba':
        import jieba
        jieba_cache=Path.home()/'.cache/rice-paper-eval/jieba'
        jieba_cache.mkdir(parents=True,exist_ok=True)
        jieba.dt.tmp_dir=str(jieba_cache)
        preprocess=lambda text:' '.join(jieba.cut(text))
    else:preprocess=lambda text:text
    unique={};indices={};failed=[]
    for i,r in enumerate(rows):
        answer=r.get('final_answer',r['answer']);error=r['generation_error']
        from .preprocessing import generation_failed
        if generation_failed(answer,error):
            r.update(bertscore_precision=0.0,bertscore_recall=0.0,bertscore_f1=0.0,bertscore_status='generation_failed',bertscore_truncated=False);continue
        pair=(preprocess(answer),preprocess(r['ground_truth']))
        key=hashlib.sha256(json.dumps(pair,ensure_ascii=False).encode()).hexdigest()
        unique[key]=pair;indices.setdefault(key,[]).append(i)
    keys=list(unique);cache={}
    max_length=scorer._tokenizer.model_max_length
    if max_length>100000:max_length=512
    for start in range(0,len(keys),args.batch_size):
        batch=keys[start:start+args.batch_size];cands=[unique[k][0] for k in batch];refs=[unique[k][1] for k in batch]
        long_policy=getattr(args,'long_text_policy','legacy-truncate')
        lengths=[(len(scorer._tokenizer.encode(c,truncation=False)),len(scorer._tokenizer.encode(r,truncation=False))) for c,r in zip(cands,refs)]
        short=[j for j,(cl,rl) in enumerate(lengths) if max(cl,rl)<=max_length or long_policy=='legacy-truncate']
        short_scores={}
        if short:
            P,R,F=scorer.score([cands[j] for j in short],[refs[j] for j in short],batch_size=args.batch_size)
            short_scores={j:[float(P[k]),float(R[k]),float(F[k])] for k,j in enumerate(short)}
        for j,key in enumerate(batch):
            candidate_length=len(scorer._tokenizer.encode(cands[j],truncation=False));reference_length=len(scorer._tokenizer.encode(refs[j],truncation=False))
            candidate_ids=scorer._tokenizer.encode(cands[j],add_special_tokens=False,truncation=False)
            reference_ids=scorer._tokenizer.encode(refs[j],add_special_tokens=False,truncation=False)
            extra={'bertscore_variant':'standard-bertscore','bertscore_candidate_windows':1,'bertscore_reference_windows':1,'bertscore_candidate_payload_tokens':len(candidate_ids),'bertscore_reference_payload_tokens':len(reference_ids),'bertscore_candidate_unk':candidate_ids.count(scorer._tokenizer.unk_token_id),'bertscore_reference_unk':reference_ids.count(scorer._tokenizer.unk_token_id)}
            if j in short_scores:values=short_scores[j]
            else:
                from .long_bertscore import score_long
                if getattr(args,'audit_long_matching',False):
                    from .audited_bertscore import score_long_audited
                    values,detail=score_long_audited(scorer,cands[j],refs[j],max_length)
                else:values,detail=score_long(scorer,cands[j],refs[j],max_length)
                extra.update(detail)
            if not all(math.isfinite(v) for v in values):raise RuntimeError('Nonfinite BERTScore; results must not be silently dropped')
            cache[key]={'bertscore_precision':values[0],'bertscore_recall':values[1],'bertscore_f1':values[2],'bertscore_status':'scored','bertscore_candidate_tokens':candidate_length,'bertscore_reference_tokens':reference_length,'bertscore_truncated':long_policy=='legacy-truncate' and max(candidate_length,reference_length)>max_length,**extra}
            for i in indices[key]:rows[i].update(cache[key])
        (args.output/'bertscore_cache.json').write_text(json.dumps(cache,ensure_ascii=False)+'\n')
        print(f'BERTScore {min(start+len(batch),len(keys))}/{len(keys)} unique answer/reference pairs',flush=True)
    return {'bert_tokenizer_class':type(scorer._tokenizer).__name__,'bert_encoder_class':type(scorer._model).__name__,'bert_num_layers':getattr(args,'bert_layers',8),'bert_tokenizer_special_ids':{'cls':scorer._tokenizer.cls_token_id,'sep':scorer._tokenizer.sep_token_id,'pad':scorer._tokenizer.pad_token_id,'unk':scorer._tokenizer.unk_token_id},'bert_weights_sha256':source['weights_sha256'] if args.bert_snapshot else None,'bert_revision':revision,'bert_local_snapshot':local,'bert_score_hash':scorer.hash,'bert_unique_pairs':len(keys),'bert_max_tokens':max_length,'bert_truncation_policy':getattr(args,'long_text_policy','legacy-truncate'),'bert_long_text_note':'Window-encoded variant for >512 tokens with global greedy matching; short inputs use standard BERTScore' if getattr(args,'long_text_policy','legacy-truncate')=='window-global' else 'Legacy truncation'}
