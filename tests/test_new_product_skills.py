import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / '.agents' / 'skills'
S1 = ROOT / 'new-product-competitor-research'
S2 = ROOT / 'competitor-keyword-root-builder'

def read_csv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(p, rows):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.candidates = self.base/'candidates.csv'
        self.keywords = self.base/'keywords.csv'
        self.review = self.base/'review.csv'
        shutil.copy(S1/'examples/candidates.csv', self.candidates)
        shutil.copy(S2/'examples/keywords.csv', self.keywords)
        shutil.copy(S2/'examples/competitor_review.csv', self.review)
        self.research = self.base/'research'
        self.result = self.base/'result'

    def tearDown(self):
        self.temp.cleanup()

    def run1(self, ok=True):
        p = subprocess.run([sys.executable,str(S1/'scripts/run.py'),
            '--product',str(S1/'examples/product.json'),'--seeds',str(S1/'examples/seeds.csv'),
            '--candidates',str(self.candidates),'--out',str(self.research)], capture_output=True,text=True)
        self.assertEqual(p.returncode,0 if ok else 2,p.stdout+p.stderr)
        return p

    def run2(self, ok=True):
        p = subprocess.run([sys.executable,str(S2/'scripts/run.py'),
            '--research',str(self.research/'research_context.json'),
            '--keywords',str(self.keywords),'--competitor-review',str(self.review),
            '--out',str(self.result)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0 if ok else 2,p.stdout+p.stderr)
        return p

    def result_data(self):
        return json.loads((self.result/'keyword_context.json').read_text())

    def test_mean_unique_and_relevance_separation(self):
        self.run1();self.run2();d=self.result_data()
        self.assertEqual(d['baseline'],'4000')
        self.assertEqual(d['baseline_denominator'],3)
        kw={x['keyword']:x for x in d['keywords']}
        self.assertEqual(kw['yoga mat']['asin_coverage'],2)
        self.assertEqual(kw['exercise mat']['search_band'],'high')
        self.assertEqual(kw['yoga mat']['search_band'],'low')
        self.assertFalse(any(x['root']=='bag' for x in d['roots']))
        self.assertTrue(any(x['root']=='non slip' for x in d['roots']))

    def test_mean_boundary_missing_zero_and_no_stopword_stitch(self):
        rows=read_csv(self.keywords)
        for r in rows:
            if r['relevance']=='high':r['search_volume']='0'
        extra=dict(rows[0],keyword='mat for yoga',search_volume='')
        rows.append(extra)
        rows.append(dict(extra,keyword='mat for home',search_volume='0',relevance='medium'))
        write_csv(self.keywords,rows)
        self.run1();self.run2();d=self.result_data()
        self.assertEqual(d['baseline'],'0')
        self.assertEqual(d['baseline_denominator'],3)
        kw={x['keyword']:x for x in d['keywords']}
        self.assertEqual(kw['yoga mat']['search_band'],'high')
        self.assertEqual(kw['mat for yoga']['search_band'],'unknown')
        self.assertFalse(any(x['root']=='mat yoga' for x in d['roots']))

    def test_conflicting_volume_stops_before_output(self):
        rows=read_csv(self.keywords);rows[1]['search_volume']='999';write_csv(self.keywords,rows)
        self.run1();p=self.run2(False)
        self.assertIn('搜索量冲突',p.stderr)
        self.assertFalse(self.result.exists())

    def test_conflicting_relevance_stops(self):
        rows=read_csv(self.keywords);rows[1]['relevance']='medium';write_csv(self.keywords,rows)
        self.run1();self.assertIn('分类冲突',self.run2(False).stderr)

    def test_category_mismatch_stops(self):
        rows=read_csv(self.keywords);rows[0]['category_id']='OTHER';write_csv(self.keywords,rows)
        self.run1();self.assertIn('口径不一致',self.run2(False).stderr)

    def test_no_valid_high_volume_stops(self):
        rows=read_csv(self.keywords)
        for r in rows:r['search_volume']=''
        write_csv(self.keywords,rows)
        self.run1();self.assertIn('无法计算基准',self.run2(False).stderr)

    def test_family_representative_and_sales_order(self):
        rows=read_csv(self.candidates);rows[1]['parent_asin']=rows[0]['parent_asin'];write_csv(self.candidates,rows)
        self.run1()
        selected=read_csv(self.research/'selected_asins.csv')
        self.assertEqual([r['asin'] for r in selected],['B0DEMO0001','B0DEMO0003'])
        self.assertEqual(read_csv(self.research/'reserve_asins.csv')[0]['asin'],'B0DEMO0002')

    def test_low_relevance_high_sales_does_not_enter(self):
        rows=read_csv(self.candidates);rows[0]['relevance']='low';rows[0]['sales']='99999';write_csv(self.candidates,rows)
        self.run1();selected=read_csv(self.research/'selected_asins.csv')
        self.assertEqual([r['asin'] for r in selected],['B0DEMO0002','B0DEMO0003'])

    def test_excluded_competitor_not_counted(self):
        rows=read_csv(self.review);rows[-1]['decision']='exclude';write_csv(self.review,rows)
        self.run1();self.run2();d=self.result_data()
        self.assertEqual(d['baseline'],'2000')
        self.assertEqual(len(d['effective_asins']),2)
        self.assertFalse(any(r['keyword']=='thick yoga mat' for r in d['keywords']))

    def test_no_overwrite(self):
        self.run1();p=self.run1(False)
        self.assertIn('已存在',p.stderr)

    def test_all_approved_high_keywords_follow_mean_formula(self):
        rows=read_csv(self.keywords)
        rows.append(dict(rows[0],keyword='demo brand yoga mat',search_volume='4000',term_type='brand'))
        write_csv(self.keywords,rows)
        self.run1();self.run2();d=self.result_data()
        self.assertEqual(d['baseline_denominator'],4)
        self.assertEqual(d['baseline'],'4000')
        self.assertFalse(any(x['root']=='demo' for x in d['roots']))

if __name__=='__main__':
    unittest.main(verbosity=2)
