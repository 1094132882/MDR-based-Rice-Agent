import unittest,torch
from .audited_bertscore import match_audited
from .long_bertscore import global_match,windows
class Tests(unittest.TestCase):
 def test_numerical_parity_and_block_invariance(self):
  torch.manual_seed(31);h=torch.randn(121,24);r=torch.randn(47,24);hw=torch.ones(121);rw=torch.ones(47);hw[[0,60,120]]=0;rw[[0,46]]=0
  base=global_match(h,r,hw,rw)
  for block in [1,7,512]:
   actual,info=match_audited(h,r,hw,rw,block)
   self.assertLess(max(abs(a-b) for a,b in zip(actual,base)),1e-6)
 def test_special_target_is_recorded(self):
  h=torch.tensor([[1.,0.],[0.,1.]]);r=torch.tensor([[1.,0.],[0.,1.]]);hw=torch.ones(2);rw=torch.tensor([0.,1.])
  values,info=match_audited(h,r,hw,rw);self.assertEqual(info['bertscore_p_special_target_tokens'],1)
 def test_no_overlap_or_length_loss(self):
  for n in [1,509,510,511,1020,1021,6237]:
   ids=list(range(n));ws=windows(ids,510);self.assertEqual(sum(ws,[]),ids);self.assertTrue(all(len(w)<=510 for w in ws))
if __name__=='__main__':unittest.main()
