"""Same window-global-v1 definition plus special-token matching diagnostics."""
import torch
from .long_bertscore import encode_full

def match_audited(hyp,ref,hw,rw,block=512):
 hyp=hyp/torch.linalg.vector_norm(hyp,dim=-1,keepdim=True);ref=ref/torch.linalg.vector_norm(ref,dim=-1,keepdim=True)
 precisions=[];recall=torch.full((len(ref),),-float('inf'),device=ref.device)
 recall_sources=torch.full((len(ref),),-1,dtype=torch.long,device=ref.device);p_special=0
 for start in range(0,len(hyp),block):
  sim=hyp[start:start+block]@ref.T
  pv,pi=sim.max(dim=1);rv,ri=sim.max(dim=0)
  precisions.append(pv)
  p_special+=int(((rw[pi]==0)&(hw[start:start+len(pv)]>0)).sum())
  improve=rv>recall;recall_sources[improve]=ri[improve]+start
  recall=torch.maximum(recall,rv)
 p=(torch.cat(precisions)*hw).sum()/hw.sum();r=(recall*rw).sum()/rw.sum()
 f=2*p*r/(p+r) if float(p+r)!=0 else p*0
 r_special=int(((hw[recall_sources]==0)&(rw>0)).sum())
 return [float(p),float(r),float(f)],{'bertscore_p_special_target_tokens':p_special,'bertscore_r_special_target_tokens':r_special,'bertscore_hyp_weight_sum':float(hw.sum()),'bertscore_ref_weight_sum':float(rw.sum())}

def score_long_audited(scorer,candidate,reference,max_length):
 h,hw,nt,nc=encode_full(scorer,candidate,max_length);r,rw,rt,rc=encode_full(scorer,reference,max_length)
 values,info=match_audited(h,r,hw,rw)
 assert float(hw.sum())==nt and float(rw.sum())==rt,'Payload weights/count mismatch'
 return values,{**info,'bertscore_candidate_payload_tokens':nt,'bertscore_reference_payload_tokens':rt,'bertscore_candidate_windows':nc,'bertscore_reference_windows':rc,'bertscore_variant':'window-encoded-global-greedy-v1'}
