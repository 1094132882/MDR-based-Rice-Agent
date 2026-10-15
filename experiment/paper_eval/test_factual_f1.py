import unittest
from .accuracy import make_reference
from .factual_f1 import score_factual_f1
class Tests(unittest.TestCase):
 def test_coordinates(self):
  ref=make_reference({'split':'type1','question':'LOC_Os08g02050位置','ground_truth':'LOC_Os08g02050 Chr08:662167-667559'})
  self.assertAlmostEqual(score_factual_f1(ref,'LOC_Os08g02050 Chr08:662167-999999')['factual_f1'],2/3)
  self.assertEqual(score_factual_f1(ref,'LOC_Os08g99999 Chr08:662167-667559')['factual_f1'],0)
  self.assertEqual(score_factual_f1(ref,'<think>Chr01:99999-88888</think> LOC_Os08g02050 Chr08:662167-667559')['factual_f1'],1)
 def test_list(self):
  ref=make_reference({'split':'type13','question':'区域基因','ground_truth':'LOC_Os01g10000 LOC_Os01g20000'})
  self.assertEqual(score_factual_f1(ref,'LOC_Os01g10000 LOC_Os01g30000')['factual_f1'],.5)
  self.assertEqual(score_factual_f1(ref,'LOC_Os01g10000 LOC_Os01g20000 LOC_Os01g20000')['factual_f1'],1)
if __name__=='__main__':unittest.main()
