import importlib.util, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent.parent;sys.argv=sys.argv[:1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_lesson import lint
import fitz
class Regression(unittest.TestCase):
    def test_code_table(self):
        data={'title':'x','scope':{'start_page':1,'end_page':1},'lessons':[{'page':1,'title':'x','blocks':[{'type':'paragraph','text':'说明'},{'type':'code','text':'a < b'},{'type':'table','columns':['a','b'],'rows':[['1','2']]}]}]}
        self.assertEqual(lint(data,1)[0],[])
        data['lessons'][0]['blocks'][2]['rows']=[['1']]
        self.assertTrue(lint(data,1)[0])
    def test_pdf_cache_and_invalidation(self):
        spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_reader.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
        with tempfile.TemporaryDirectory() as d:
            pdf=Path(d)/'source.pdf';cache=Path(d)/'cache'
            doc=fitz.open();doc.new_page().insert_text((50,50),'first');doc.save(pdf);doc.close()
            images,hit=b.pdf_images(pdf,1.0,70,cache);self.assertFalse(hit)
            again,hit=b.pdf_images(pdf,1.0,70,cache);self.assertTrue(hit);self.assertEqual(images,again)
            _,hit=b.pdf_images(pdf,1.1,70,cache);self.assertFalse(hit)
            _,hit=b.pdf_images(pdf,1.0,75,cache);self.assertFalse(hit)
            doc=fitz.open();doc.new_page().insert_text((50,50),'second');doc.save(pdf);doc.close()
            changed,hit=b.pdf_images(pdf,1.0,70,cache);self.assertFalse(hit);self.assertNotEqual(images,changed)
            cache_file=list(cache.glob('*.json'))[-1];cache_file.write_text('broken')
            # Cache corruption must not prevent construction.
            for f in cache.glob('*.json'):f.write_text('broken')
            restored,hit=b.pdf_images(pdf,1.0,70,cache);self.assertFalse(hit);self.assertEqual(changed,restored)
if __name__=='__main__':unittest.main()
