#!/usr/bin/env python3
"""Extract PDF page metadata as a drafting aid. Visual verification remains required."""
import argparse, json
from pathlib import Path
import fitz

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('pdf',type=Path); ap.add_argument('--out', type=Path, required=True)
    a=ap.parse_args(); doc=fitz.open(a.pdf)
    pages=[]
    for i, p in enumerate(doc):
        text=p.get_text('text').strip()
        pages.append({'page':i+1,'width':round(p.rect.width,1),'height':round(p.rect.height,1),
                      'text':text,'image_count':len(p.get_images(full=False)),
                      'drawing_count':len(p.get_drawings()),
                      'needs_visual_review': bool(len(p.get_images()) or len(p.get_drawings()) or len(text)<50)})
    result={'source_file':a.pdf.name,'page_count':len(doc),'pages':pages}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Extracted',len(doc),'pages ->',a.out)
    print('Visual-review candidates:',sum(p['needs_visual_review'] for p in pages))
if __name__=='__main__':main()
