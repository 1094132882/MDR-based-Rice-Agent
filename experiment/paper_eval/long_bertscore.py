"""Window-encoded BERTScore variant: retain all tokens, global greedy matching.

Not identical to standard truncated BERTScore for long inputs. Payload windows
have disjoint tokens; each receives CLS/SEP for encoding, then global matching
uses concatenated embeddings. No text is dropped and no mean of chunk F1s.
"""
import torch

def windows(ids,payload):return [ids[i:i+payload] for i in range(0,len(ids),payload)]
def encode_full(scorer,text,max_length):
 tokenizer=scorer._tokenizer;ids=tokenizer.encode(text,add_special_tokens=False,truncation=False)
 encoded=[];weights=[]
 chunks=windows(ids,max_length-tokenizer.num_special_tokens_to_add(False))
 with torch.no_grad():
  for chunk in chunks:
   tokens=tokenizer.build_inputs_with_special_tokens(chunk)
   x=torch.tensor([tokens],device=scorer.device);mask=torch.ones_like(x)
   embeddings=scorer._model(x,attention_mask=mask)[0][0]
   encoded.append(embeddings)
   # Same idf=False special-token weight convention as BERTScore.
   weights.extend(0. if t in [tokenizer.cls_token_id,tokenizer.sep_token_id] else 1. for t in tokens)
 if not chunks:return None,None,0,0
 return torch.cat(encoded),torch.tensor(weights,device=scorer.device),len(ids),len(chunks)
def global_match(hyp,ref,hyp_weights,ref_weights,block=512):
 hyp=hyp/torch.linalg.vector_norm(hyp,dim=-1,keepdim=True);ref=ref/torch.linalg.vector_norm(ref,dim=-1,keepdim=True)
 precision=[];recall=torch.full((len(ref),),-float('inf'),device=ref.device)
 for start in range(0,len(hyp),block):
  sim=hyp[start:start+block]@ref.T
  precision.append(sim.max(dim=1).values);recall=torch.maximum(recall,sim.max(dim=0).values)
 p=(torch.cat(precision)*hyp_weights).sum()/hyp_weights.sum();r=(recall*ref_weights).sum()/ref_weights.sum()
 f=2*p*r/(p+r) if float(p+r)!=0 else p*0
 return [float(p),float(r),float(f)]
def score_long(scorer,candidate,reference,max_length):
 hyp,hw,nt,nc=encode_full(scorer,candidate,max_length);ref,rw,rt,rc=encode_full(scorer,reference,max_length)
 values=[0.,0.,0.] if hyp is None or ref is None else global_match(hyp,ref,hw,rw)
 return values,{'bertscore_candidate_payload_tokens':nt,'bertscore_reference_payload_tokens':rt,'bertscore_candidate_windows':nc,'bertscore_reference_windows':rc,'bertscore_variant':'window-encoded-global-greedy-v1'}
