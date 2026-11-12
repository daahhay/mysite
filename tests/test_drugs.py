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

if __name__ == '__main__':unittest.main()
