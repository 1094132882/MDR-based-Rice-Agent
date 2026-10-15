import csv,json,tempfile,unittest
from pathlib import Path
from .structured_facts_v3 import build_profile,digest,score
from .structured_run_v3 import run,replay_verdict

class Tests(unittest.TestCase):
    def test_synthetic_batch_preserves_original_metrics_and_macro_denominator(self):
        p=build_profile({'split':'type14','question':'LOC_Os01g01010上游查询','ground_truth':'LOC_Os01g01010上游包括LOC_Os01g02020、LOC_Os01g03030、LOC_Os01g04040。'},0)
        p['difficulty']='S';p.pop('profile_sha256');p['profile_sha256']=digest(json.dumps(p,ensure_ascii=False,sort_keys=True))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'profiles.json').write_text(json.dumps([p]))
            rows=[]
            for model,answer in [('M1',p['ground_truth']),('M2','LOC_Os01g01010上游包括LOC_Os01g02020、LOC_Os01g03030。')]:
                rows.append({'model':model,'method':'s_cot_raps','run':'fixed','sample_id':'0','difficulty':'S','question':p['question'],'ground_truth':p['ground_truth'],'answer':answer,'final_answer':answer,'accuracy':'OLD_ACC','factual_f1':'OLD_F1','bertscore_f1':'OLD_BERT'})
            with (root/'in.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            m=run(root/'in.csv',root/'profiles.json',root/'out',expected_records=2)
            with (root/'out/per_question.csv').open(encoding='utf-8-sig') as f:out=list(csv.DictReader(f))
            self.assertEqual(m['model_calls'],0)
            self.assertEqual([r['accuracy'] for r in out],['OLD_ACC']*2)
            self.assertEqual([r['bertscore_f1'] for r in out],['OLD_BERT']*2)
            self.assertEqual(float(out[1]['v3_accuracy']),0);self.assertEqual(float(out[1]['v3_structured_fact_f1']),.8)
            self.assertEqual([r['run'] for r in out],['fixed']*2)
            with self.assertRaises(FileExistsError):run(root/'in.csv',root/'profiles.json',root/'out',2)

    def test_saved_verdict_hash_binding_and_no_invented_fp(self):
        p=build_profile({'split':'type11','question':'LOC_Os01g01010功能','ground_truth':'基因LOC_Os01g01010的注释是Pirin-like protein [UniProtKB/Swiss-Prot:Q9SEE4]。'})
        row={'question':p['question'],'ground_truth':p['ground_truth'],'answer':'功能是另一种蛋白。','final_answer':'功能是另一种蛋白。'}
        v={'id':'synthetic','accuracy':0,'factual_f1':0,'reason':'synthetic human annotation verdict','sha256':{k:digest(s) for k,s in row.items()}}
        out=replay_verdict(p,row,score(p,row['final_answer']),v)
        self.assertEqual(out['accuracy'],0);self.assertEqual(out['structured_fact_f1'],0)
        self.assertIsNone(out['fp'])
        row['answer']='Changed'
        with self.assertRaises(ValueError):replay_verdict(p,row,out,v)

if __name__=='__main__':unittest.main()
