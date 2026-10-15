"""Synthetic release-adapter checks; no historical model outputs or API calls."""
import csv,json,tempfile,unittest
from pathlib import Path
from experiment.prepare_eval_input import prepare,ROOT
from experiment.score_bertscore import summarize

class PublicAdapters(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)
        self.profiles=ROOT/'experiment/datasets/gold_profiles.json'
        self.data=json.loads(self.profiles.read_text())
        self.rows=[dict(model='synthetic-test',method='s_cot_raps',run='1',sample_id=str(p['sample_id']),answer=p['ground_truth']) for p in self.data]
    def write_input(self):
        path=self.directory/'raw.csv'
        fields=list(dict.fromkeys(k for r in self.rows for k in r))
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(self.rows)
        return path
    def execute(self):return prepare(self.write_input(),self.directory/'prepared.csv',self.profiles)
    def test_complete_cohort_preserved(self):
        self.rows[0]['answer']='<think>private reasoning</think>'+self.rows[0]['answer']
        self.assertEqual(self.execute(),150)
        with (self.directory/'prepared.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]['final_answer'],self.data[0]['ground_truth'])
        self.assertIn('<think>',rows[0]['answer'])
        self.assertEqual(sum(r['difficulty']=='C' for r in rows),65)
        self.assertEqual(sum(r['difficulty']=='S' for r in rows),85)
    def test_incomplete_cohort_rejected(self):
        self.rows.pop()
        with self.assertRaises(ValueError):self.execute()
    def test_duplicate_rejected(self):
        self.rows.append(self.rows[0].copy())
        with self.assertRaises(ValueError):self.execute()
    def test_changed_reference_rejected(self):
        self.rows[0]['ground_truth']='changed reference'
        with self.assertRaises(ValueError):self.execute()
    def test_malformed_think_rejected(self):
        self.rows[0]['answer']='<think>unclosed'
        with self.assertRaises(ValueError):self.execute()
    def test_final_answer_mismatch_rejected(self):
        self.rows[0]['final_answer']='different'
        with self.assertRaises(ValueError):self.execute()
    def test_no_overwrite(self):
        self.execute()
        with self.assertRaises(FileExistsError):self.execute()
    def test_macro_average_and_review_bounds(self):
        rows=[dict(model='synthetic',method='s_cot_raps',run='1',difficulty=d,v3_accuracy=acc,v3_structured_fact_f1=f1,bertscore_f1=b) for d,acc,f1,b in [('S','0','.5','.8'),('C','1','1','.9'),('C','','','.7')]]
        groups=summarize(rows);all_group=next(g for g in groups if g['subset']=='all')
        self.assertEqual(all_group['n'],3)
        self.assertEqual(all_group['v3_accuracy'],'')
        self.assertAlmostEqual(all_group['v3_accuracy_lower_bound'],1/3)
        self.assertAlmostEqual(all_group['v3_accuracy_upper_bound'],2/3)
        self.assertAlmostEqual(all_group['v3_structured_fact_f1_lower_bound'],.5)
        self.assertAlmostEqual(all_group['bertscore_f1'],.8)

if __name__=='__main__':unittest.main()
