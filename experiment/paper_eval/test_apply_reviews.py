import unittest,tempfile,json,csv,sys
from pathlib import Path
from unittest.mock import patch
from .apply_reviews import main,checksum
class Tests(unittest.TestCase):
 def test_changed_text_rejected_without_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'input';src.mkdir();out=root/'output'
   row={'model':'test','method':'baseline','run':'1','sample_id':'46','split':'type11','question':'question','ground_truth':'reference','answer':'answer','final_answer':'answer','accuracy':'','factual_f1':''}
   with (src/'per_question.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
   record={'id':'test|baseline|1|46','sha256':{k:checksum(row[k]) for k in ['question','ground_truth','answer','final_answer']},'accuracy':0,'factual_f1':0,'reason':'human audit'}
   record['sha256']['answer']=checksum('different answer');v=root/'verdicts.json';v.write_text(json.dumps({'decision_source':'human','records':[record]}))
   with patch.object(sys,'argv',['apply_reviews','--input',str(src),'--verdicts',str(v),'--output',str(out)]):
    with self.assertRaisesRegex(ValueError,'Verdict input changed'):main()
   self.assertFalse(out.exists())
if __name__=='__main__':unittest.main()
