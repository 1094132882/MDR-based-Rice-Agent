import csv
from pathlib import Path
import unittest
from .accuracy import make_reference,score_accuracy,parse_facts
from .run import summarize,aggregate

ROOT=Path(__file__).resolve().parents[2]

class AccuracyTests(unittest.TestCase):
    def setUp(self):
        with (ROOT/'methods/s_cot_raps/dataset.csv').open(encoding='utf-8-sig') as f:self.rows=list(csv.DictReader(f))
    def score(self,i,answer):return score_accuracy(make_reference(self.rows[i]),answer)
    def test_all_150_references_are_valid_and_self_match(self):
        self.assertEqual(len(self.rows),150)
        for i,row in enumerate(self.rows):
            with self.subTest(i=i):self.assertEqual(self.score(i,row['ground_truth'])['accuracy'],1)
    def test_unrelated_answer_never_accepted(self):
        for i in range(150):
            with self.subTest(i=i):self.assertNotEqual(self.score(i,'Completely unrelated answer')['accuracy'],1)
    def test_coordinate_order_chromosome_and_both_endpoints(self):
        for wrong in ['Chr09:662167-667559','Chr08:667559-662167','Chr08:662167-999999']:
            self.assertEqual(self.score(0,wrong)['accuracy'],0)
        self.assertEqual(self.score(0,'Chr08:662167-667559')['accuracy'],1)
    def test_missing_reference_never_passes(self):
        row={**self.rows[0],'ground_truth':'No parseable reference'}
        self.assertIsNone(score_accuracy(make_reference(row),'No parseable reference')['accuracy'])
    def test_opposite_or_contradictory_strand_fails(self):
        self.assertEqual(self.score(5,'negative strand')['accuracy'],0)
        self.assertEqual(self.score(5,'positive strand and negative strand')['accuracy'],0)
        self.assertEqual(self.score(5,'positive strand')['accuracy'],1)
    def test_gene_echo_and_partial_list_do_not_pass(self):
        row=self.rows[26]
        self.assertEqual(self.score(26,'OsMH63_03G0194400')['accuracy'],0)
        self.assertEqual(self.score(26,'22NBF05')['accuracy'],0)
        self.assertEqual(self.score(26,row['ground_truth']+' 22NBZ99')['accuracy'],0)
    def test_wrong_url_same_domain_fails(self):
        self.assertEqual(self.score(14,'https://riceome.hzau.edu.cn/dev/genecard/WRONG/') ['accuracy'],0)
    def test_sv_regions_and_stats_cannot_default_to_gene(self):
        for i in range(108,135):
            self.assertEqual(self.score(i,'OsMH63_03G0194400')['accuracy'],0)
    def test_te_duplicate_annotation_is_required(self):
        row=self.rows[136];wrong=row['ground_truth'].replace('4.long_terminal_repeat','')
        self.assertEqual(self.score(136,wrong)['accuracy'],0)
    def test_equal_reference_numbers_keep_tissue_identity(self):
        gold=self.rows[52]['ground_truth'];wrong=gold.replace('0.221995','0.151120').replace('0.151120,','0.221995,')
        self.assertEqual(self.score(52,'leaf: 0.151120; root: 0.221995; panicle unavailable')['accuracy'],0)
    def test_gene_ids_preserve_decimal_and_transcript_suffixes(self):
        facts=parse_facts('1.OsWSSMG0508338800.01.T02 2.OsWSSMG0508338800.01.T01','transcripts')
        self.assertEqual(len(facts['members']),2)
        self.assertTrue(all('.01.t0' in x for x in facts['members']))
    def test_explicit_no_result_never_passes_function(self):
        self.assertEqual(self.score(46,'未查询到相关信息')['accuracy'],0)
    def test_negated_function_does_not_pass_literal_overlap(self):
        self.assertEqual(self.score(46,'不是Pirin-like protein')['accuracy'],0)
    def test_different_function_and_accession_is_wrong_not_review(self):
        self.assertEqual(self.score(48,'Pirin-like protein [UniProtKB/Swiss-Prot:Q9SEE4]')['accuracy'],0)
    def test_function_wrong_accession_is_not_accepted(self):
        self.assertEqual(self.score(46,self.rows[46]['ground_truth'].replace('Q9SEE4','Q9XXXXX'))['accuracy'],0)
    def test_long_unrelated_ascii_text_does_not_backtrack_quadratically(self):
        self.assertEqual(self.score(108,'A'*150000)['accuracy'],0)
    def test_empty_and_generation_error(self):
        self.assertEqual(self.score(0,'')['accuracy'],0)
        self.assertEqual(self.score(0,'Error: timed out')['accuracy'],0)
    def test_summaries_never_drop_unreviewed_samples(self):
        rows=[{'model':'M','method':'s_cot_raps','run':1,'difficulty':'S','accuracy':1,'bertscore_f1':1.0}, {'model':'M','method':'s_cot_raps','run':1,'difficulty':'C','accuracy':None,'bertscore_f1':0.0}]
        allrow=next(r for r in summarize(rows) if r['subset']=='all')
        self.assertIsNone(allrow['accuracy']);self.assertEqual(allrow['accuracy_lower_bound'],0.5)
        self.assertEqual(allrow['accuracy_upper_bound'],1);self.assertEqual(allrow['bertscore_f1'],0.5)
    def test_gold_function_paraphrases_require_review(self):
        self.assertIsNone(self.score(46,'This is a protein of the pirin family.')['accuracy'])

if __name__=='__main__':unittest.main()
