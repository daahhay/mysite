import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from build_drugs import load_drugs, build_drugs, folders
from build_blog import frame, ArticleHTML, safe_url

class DrugLibraryTests(unittest.TestCase):
    def test_folders(self):
        self.assertEqual(folders(['Cardiology/Pressors', ' Cardiology / Pressors ', ' / ']), ['Cardiology / Pressors'])

    def test_drafts_and_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'content/drugs').mkdir(parents=True)
            (root/'drugs').mkdir()
            for name in ['drugs.css','drugs.js']:
                (root/'drugs'/name).write_text('')
            drug={'title':'Test drug','slug':'test-drug','published':True,
                  'categories':['Cardiology / Pressors'], 'aliases':['Test alias'],
                  'doses':[{'condition':'Condition A','population':'Adult','route':'IV','body':'<p>TEST CONTENT ONLY</p><script>alert(1)</script><img src="javascript:x">'},
                           {'condition':'Condition B','body':'<table><tr><td>Test table</td></tr></table>'}],
                  'renal':'<p>Test renal section</p>', 'references':[{'title':'Bad','url':'javascript:x'},{'title':'Source','url':'https://example.org'}]}
            (root/'content/drugs/test.json').write_text(json.dumps(drug))
            (root/'content/drugs/draft.json').write_text(json.dumps({'title':'Draft secret','slug':'draft','published':False}))
            self.assertEqual(len(load_drugs(root)),1)
            self.assertEqual(len(load_drugs(root,True)),2)
            output=root/'out';output.mkdir()
            build_drugs(root,output,frame,ArticleHTML,safe_url)
            page=(output/'drugs/test-drug/index.html').read_text()
            index=(output/'drugs/index.html').read_text()
            self.assertNotIn('Draft secret',index)
            self.assertFalse((output/'drugs/draft').exists())
            self.assertNotIn('alert(1)',page)
            self.assertNotIn('javascript:',page)
            self.assertIn('Test table',page)
            self.assertIn('Kidney impairment',page)
            self.assertNotIn('Liver impairment',page)
            self.assertIn('data-folder="Cardiology"',index)
            self.assertIn('data-folder="Cardiology / Pressors"',index)
            self.assertIn('href="https://tamerlanerdniev.ru/drugs/"',page)
            import re
            ids=re.findall(r'id="(section-[0-9]+)"',page)
            self.assertEqual(len(ids),len(set(ids)))
            for anchor in ids:self.assertIn('href="#'+anchor+'"',page)

    def test_invalid_slug(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'content/drugs').mkdir(parents=True)
            for slug in ['../escape','edit','Mixed Case']:
                (root/'content/drugs/test.json').write_text(json.dumps({'title':'Test','slug':slug,'published':True}))
                with self.assertRaises(ValueError):load_drugs(root)


    def test_bilingual_pages_and_draft_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'content/drugs').mkdir(parents=True); (root/'drugs').mkdir()
            for name in ['drugs.css','drugs.js']:(root/'drugs'/name).write_text('')
            d={'title':'Test medicine','slug':'medicine','published':True,'language':'en',
               'categories':['Test / Folder'],'renal':'<p>English renal information</p>',
               'translation':{'published':True,'title':'Тестовый препарат',
                              'doses':[{'condition':'Тестовое показание','body':'<p>Тестовый текст</p>'}]}}
            file=root/'content/drugs/medicine.json';file.write_text(json.dumps(d))
            out=root/'out';out.mkdir()
            build_drugs(root,out,frame,ArticleHTML,safe_url)
            en=(out/'drugs/medicine/index.html').read_text()
            ru=(out/'drugs/medicine-ru/index.html').read_text()
            index=(out/'drugs/index.html').read_text()
            self.assertIn('<html lang="ru">',ru)
            self.assertIn('Дозирование по показаниям',ru)
            self.assertIn('Тестовый текст',ru)
            self.assertNotIn('English renal information',ru)
            self.assertIn('href="/drugs/medicine-ru/"',en)
            self.assertIn('href="/drugs/medicine/"',ru)
            self.assertIn('1 drugs</p>',index)
            self.assertEqual(index.count('data-group="medicine"'),2)
            self.assertEqual(index.count('class="drug-row" hidden'),1)
            self.assertIn('Test / Folder',ru)
            d['translation']['published']=False;file.write_text(json.dumps(d))
            out2=root/'out2';out2.mkdir()
            build_drugs(root,out2,frame,ArticleHTML,safe_url)
            self.assertFalse((out2/'drugs/medicine-ru').exists())
            self.assertNotIn('Тестовый препарат',(out2/'drugs/index.html').read_text())

    def test_russian_original_and_slug_collision(self):
        from build_drugs import drug_versions
        d={'title':'Название','slug':'test','categories':[],'language':'ru','published':True,
           'translation':{'title':'Name','published':True}}
        self.assertEqual(drug_versions(d)[1]['slug'],'test-en')
        d['translation']['title']=''
        with self.assertRaises(ValueError):drug_versions(d)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'content/drugs').mkdir(parents=True);(root/'drugs').mkdir()
            for name in ['drugs.css','drugs.js']:(root/'drugs'/name).write_text('')
            d['translation']={'title':'Name','published':True,'slug':'test'}
            (root/'content/drugs/test.json').write_text(json.dumps(d))
            out=root/'out';out.mkdir()
            with self.assertRaises(ValueError):build_drugs(root,out,frame,ArticleHTML,safe_url)

if __name__ == '__main__':unittest.main()
