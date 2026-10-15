"""Semantic regressions; deliberately no historical prediction scoring."""
import csv,json,unittest
from pathlib import Path
from .structured_facts_v2 import build_profile,score
ROOT=Path(__file__).resolve().parents[2]

def profile(t,g,q='LOC_Os01g01010查询',sid=None):
    return build_profile({'split':'type'+str(t),'question':q,'ground_truth':g},sid)

class Tests(unittest.TestCase):
    def test_all_gold_profiles_and_self_matches(self):
        with (ROOT/'methods/s_cot_raps/dataset.csv').open() as h:rows=list(csv.DictReader(h))
        self.assertEqual(len(rows),150)
        for i,row in enumerate(rows):
            with self.subTest(sample_id=i):
                p=build_profile(row,i)
                self.assertEqual(p['profile_status'],'valid',p['profile_issues'])
                s=score(p,row['ground_truth'])
                self.assertEqual(s['accuracy'],1,s['review_reasons'])
                self.assertEqual(s['structured_fact_f1'],1,s)

    def test_previous_16_counterexamples(self):
        path=Path(__file__).parent/'fixtures/structured_counterexamples.json'
        cases=json.loads(path.read_text())
        expected={'negated_strand':(0,1,1),'negated_list':(0,2,2),'reversed_direction':(0,2,2),
                  'negated_ogi_relation':(0,2,2),'wrong_function_gene':(0,1,1),
                  'wrong_gene_location_detected':(0,3,3),'partial_members':(1,0,2),
                  'extra_member':(2,1,0),'missing_count_with_full_list':(2,0,0),
                  'extra_explicit_count':(2,0,0),'only_correct_start':(2,0,1),
                  'correct_strand_negated_antonym':(1,0,0),'wrong_region':(0,2,2),'negated_transcript':(0,1,1)}
        for c in cases:
            with self.subTest(case=c['case']):
                p=build_profile({'split':c['split'],'question':c['question'],'ground_truth':c['reference']})
                s=score(p,c['prediction'])
                if c['case'] in expected:
                    self.assertEqual((s['tp'],s['fp'],s['fn']),expected[c['case']],s)
                    self.assertEqual(s['status'],'scored',s)
                else:
                    self.assertEqual(s['status'],'prediction_review',s)
                    self.assertIsNone(s['accuracy']);self.assertIsNone(s['structured_fact_f1'])

    def test_accuracy_not_f1(self):
        p=profile(14,'LOC_Os01g01010上游基因包括LOC_Os01g02020、LOC_Os01g03030、LOC_Os01g04040。')
        s=score(p,'LOC_Os01g01010上游基因包括LOC_Os01g02020、LOC_Os01g03030。')
        self.assertEqual(s['accuracy'],0);self.assertEqual(s['structured_fact_f1'],.8)

    def test_count_conflict_not_double_member_penalty(self):
        p=profile(14,'LOC_Os01g01010上游共有3个基因:LOC_Os01g02020、LOC_Os01g03030、LOC_Os01g04040。')
        a=score(p,'LOC_Os01g01010上游共有2个基因:LOC_Os01g02020、LOC_Os01g03030。')
        self.assertEqual((a['tp'],a['fp'],a['fn']),(2,0,1))
        b=score(p,'LOC_Os01g01010上游共有4个基因:LOC_Os01g02020、LOC_Os01g03030、LOC_Os01g04040。')
        self.assertEqual((b['tp'],b['fp'],b['fn']),(3,1,0))

    def test_transcript_suffix_not_truncated(self):
        p=profile(3,'LOC_Os01g01010的转录本为LOC_Os01g01010.T01。')
        self.assertEqual(score(p,'LOC_Os01g01010的转录本为LOC_Os01g01010.T02。')['structured_fact_f1'],0)

    def test_polarity_conflict_and_duplicate_mentions(self):
        p=profile(14,'LOC_Os01g01010上游包括LOC_Os01g02020。')
        s=score(p,'LOC_Os01g01010上游包括LOC_Os01g02020。LOC_Os01g01010上游不包括LOC_Os01g02020。')
        self.assertEqual((s['tp'],s['fp'],s['fn']),(1,1,0));self.assertEqual(s['accuracy'],0)
        self.assertEqual(score(p,'LOC_Os01g01010上游包括LOC_Os01g02020。LOC_Os01g01010上游包括LOC_Os01g02020。')['structured_fact_f1'],1)

    def test_question_hypothesis_refusal_not_assertions(self):
        p=profile(2,'LOC_Os01g01010在正链。')
        for a in ['如果LOC_Os01g01010在正链。','LOC_Os01g01010是否在正链？','不知道LOC_Os01g01010是否在正链。']:
            self.assertEqual(score(p,a)['tp'],0)

    def test_unknown_inv_needs_review_not_zero(self):
        p=profile(27,'G46 Chr01:1000-2000存在2个DEL类型的结构变异。')
        s=score(p,'G46 Chr01:1000-2000存在2个DEL类型的结构变异，0个INV类型的结构变异。')
        self.assertEqual(s['tp'],1);self.assertEqual(s['status'],'prediction_review');self.assertIsNone(s['structured_fact_f1'])

    def test_te_categories_deduplicated(self):
        p=profile(29,'结构变异G46_G8_INS0100010关联TE：long_terminal_repeat long_terminal_repeat repeat_region。')
        s=score(p,'结构变异G46_G8_INS0100010关联TE：long_terminal_repeat repeat_region。')
        self.assertEqual((s['tp'],s['fp'],s['fn']),(2,0,0))

    def test_think_and_malformed(self):
        p=profile(2,'LOC_Os01g01010在正链。')
        self.assertEqual(score(p,'<think>负链</think>LOC_Os01g01010在正链。')['accuracy'],1)
        self.assertEqual(score(p,'<think>LOC_Os01g01010在正链。')['status'],'preprocessing_review')

    def test_95_exception_is_local(self):
        gold='LOC_Os01g01010下游包括LOC_Os01g02020。'
        pred='LOC_Os01g01010上游包括LOC_Os01g02020。'
        self.assertEqual(score(profile(19,gold,sid=95),pred)['accuracy'],1)
        self.assertEqual(score(profile(19,gold,sid=94),pred)['accuracy'],0)

    def test_type_contract_not_literal_question(self):
        p=profile(12,'LOC_Os01g01010在叶中的表达量为1，根中的表达量为2，幼穗的表达数据暂无。','根和茎有什么差异？')
        s=score(p,p['ground_truth']);self.assertEqual(s['accuracy'],1)
        partial=score(p,'LOC_Os01g01010在根中的表达量为2。')
        self.assertEqual((partial['tp'],partial['fp'],partial['fn']),(1,0,2));self.assertEqual(partial['accuracy'],0)

    def test_sv_roles_bound_to_individual_objects(self):
        g='G46 Chr01:1000-2000结构变异G8_G46_INS0100010，查询基因组：G46，参考基因组：G8。'
        p=profile(23,g)
        a=score(p,g.replace('参考基因组：G8','参考基因组：Wrong'))
        self.assertEqual((a['tp'],a['fp'],a['fn']),(2,1,1));self.assertEqual(a['accuracy'],0)

    def test_multiple_subjects_cannot_merge(self):
        p=profile(1,'LOC_Os01g01010在Chr01:1000-2000。')
        a=score(p,'LOC_Os01g01010在Chr01:1000-2000，LOC_Os01g02020在Chr01:1000-2000。')
        self.assertEqual((a['tp'],a['fp'],a['fn']),(3,3,0));self.assertEqual(a['accuracy'],0)

    def test_negated_expression_and_availability_are_local(self):
        p=profile(12,'LOC_Os01g01010在叶中的表达数据暂无，根中的表达量为2，幼穗中的表达量为3。')
        a=score(p,'LOC_Os01g01010 leaf is not available, root is 2, panicle is 3.')
        self.assertEqual(a['accuracy'],1,a)
        b=score(p,'LOC_Os01g01010在叶中的表达数据暂无，根中的表达量不是2，幼穗中的表达量为3。')
        self.assertEqual((b['tp'],b['fp'],b['fn']),(2,1,1))

    def test_extra_unfamiliar_annotation_category_is_fp(self):
        g='结构变异G46_G8_INS0100010关联TE：long_terminal_repeat repeat_region。'
        a=score(profile(29,g),g+' novel_feature')
        self.assertEqual((a['tp'],a['fp'],a['fn']),(2,1,0));self.assertEqual(a['accuracy'],0)

    def test_sv_id_does_not_hide_wrong_type(self):
        g='G46 Chr01:1000-2000最长结构变异G8_G46_INS0100010，类型为INS，长度为300，查询基因组为G46，参考基因组为G8。'
        a=score(profile(25,g),g.replace('类型为INS','类型为INV'))
        self.assertEqual(a['fp'],1);self.assertEqual(a['fn'],0);self.assertEqual(a['accuracy'],0)

    def test_extra_unknown_sv_statistic_is_review(self):
        g='G46 Chr01:1000-2000存在2个DEL类型的结构变异。'
        self.assertEqual(score(profile(27,g),g+' DUP:3')['status'],'prediction_review')

    def test_fractional_bp_is_not_truncated(self):
        p=profile(13,'G46 Chr01:1000-2000包括LOC_Os01g02020。')
        a=score(p,'G46 Chr01:1000.5-2000包括LOC_Os01g02020。')
        self.assertEqual(a['status'],'prediction_review');self.assertIsNone(a['accuracy'])

    def test_id_leading_zeros_and_suffix_are_exact(self):
        p=profile(14,'LOC_Os01g01010上游包括OsXX_01g0000200.01。')
        for a in ['LOC_Os01g01010上游包括OsXX_01g000200.01。','LOC_Os01g01010上游包括OsXX_01g0000200.02。']:
            r=score(p,a);self.assertEqual((r['tp'],r['fp'],r['fn']),(0,1,1))

    def test_empty_and_unknown_formats_are_distinct(self):
        p=profile(2,'LOC_Os01g01010在正链。')
        a=score(p,'');self.assertEqual(a['accuracy'],0);self.assertEqual(a['structured_fact_f1'],0)
        b=score(p,'something unspecified');self.assertEqual(b['status'],'prediction_review')

    def test_different_gene_relation_cannot_match(self):
        p=profile(14,'LOC_Os01g01010上游包括LOC_Os01g02020。')
        a=score(p,'LOC_Os01g01010与LOC_Os01g02020具有RBH同源关系。')
        self.assertEqual(a['tp'],0);self.assertEqual(a['status'],'prediction_review')

    def test_profile_tampering_is_rejected(self):
        p=profile(2,'LOC_Os01g01010在正链。');p['required_facts'][0]['object']='-'
        with self.assertRaises(ValueError):score(p,'LOC_Os01g01010在负链。')

    def test_unrecognized_extra_clause_cannot_be_silently_accepted(self):
        p=profile(2,'LOC_Os01g01010在正链。')
        a=score(p,'LOC_Os01g01010在正链。另有一项未经核实的结论。')
        self.assertEqual(a['status'],'prediction_review');self.assertIsNone(a['accuracy'])

    def test_negative_then_positive_assertions(self):
        p=profile(2,'LOC_Os01g01010在负链。')
        a=score(p,'LOC_Os01g01010不是正链而是负链。');self.assertEqual(a['accuracy'],1,a)
        p=profile(14,'LOC_Os01g01010上游包括LOC_Os01g03030。')
        b=score(p,'LOC_Os01g01010上游不包括LOC_Os01g02020，但包括LOC_Os01g03030。')
        self.assertEqual(b['tp'],1);self.assertEqual(b['accuracy'],1);self.assertEqual(len(b['verified_noncore_supplements']),1)

    def test_annotation_source_whitespace(self):
        g='基因LOC_Os01g01010的注释是Pirin-like protein [UniProtKB/Swiss-Prot:Q9SEE4]。'
        self.assertEqual(score(profile(11,g),g.replace('Prot:Q9','Prot: Q9'))['accuracy'],1)

if __name__=='__main__':unittest.main()
