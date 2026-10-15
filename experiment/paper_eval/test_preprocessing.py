import unittest
from .preprocessing import prepare_answer,generation_failed
from .long_bertscore import windows,global_match
class Tests(unittest.TestCase):
 def test_tags(self):
  self.assertEqual(prepare_answer(' <think>wrong</think> correct ')['final_answer'],'correct')
  self.assertEqual(prepare_answer('A<think>x<think>y</think>z</think>B')['final_answer'],'AB')
  self.assertEqual(prepare_answer('<THINK>x</THINK>答案') ['final_answer'],'答案')
  self.assertEqual(prepare_answer('<think>unfinished')['answer_preprocessing_status'],'malformed_think')
 def test_keep_payload(self):
  s='**基因** [链接](https://example.com)\n```json\n{}\n```'
  self.assertEqual(prepare_answer(s)['final_answer'],s)
 def test_failures(self):
  self.assertTrue(generation_failed('答案: 未查询到相关信息'))
  self.assertTrue(generation_failed('{}'))
  self.assertFalse(generation_failed('基因A在Chr01:100-200。'))
 def test_no_token_drop(self):
  ids=list(range(1601));ws=windows(ids,510)
  self.assertEqual([v for w in ws for v in w],ids)
  self.assertTrue(all(len(w)<=510 for w in ws))
 def test_global_match(self):
  import torch
  h=torch.eye(3);r=torch.eye(3)[:2];p,rec,f=global_match(h,r,torch.ones(3),torch.ones(2),block=1)
  self.assertAlmostEqual(p,2/3,places=6);self.assertEqual(rec,1);self.assertAlmostEqual(f,.8,places=6)
if __name__=='__main__':unittest.main()
