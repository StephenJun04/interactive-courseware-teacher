#!/usr/bin/env python3
"""Static lesson data linter: ensures mappings, questions, arithmetic domains."""
import argparse, json,sys
from collections import Counter
from pathlib import Path
try: import fitz
except ImportError: fitz=None
ALLOWED={'paragraph','heading','equation','note','example','list','interactive','quiz','figure'}
INTERACTIONS={'convolution','output_shape'}
Q_TYPES={'single_choice','numeric','multi_part'}

def lint(lesson, pdf_pages=None):
    errors=[]; warnings=[]
    def err(m):errors.append(m)
    def warn(m):warnings.append(m)
    lessons=lesson.get('lessons',[])
    if not lessons:err('No lessons supplied')
    seen=set(); last=0; total=0; counts=Counter()
    scope=lesson.get('scope',{})
    for l in lessons:
        p=l.get('page')
        if not isinstance(p,int) or p<1:err(f'Invalid page: {p}');continue
        if p in seen:err(f'Page {p} duplicate')
        if p<last:warn(f'Page order is not ascending: {p} after {last}')
        seen.add(p);last=p
        if pdf_pages and p>pdf_pages:err(f'Page {p} exceeds PDF page count {pdf_pages}')
        if not str(l.get('title','')).strip():err(f'P{p}: missing title')
        blocks=l.get('blocks',[])
        if not blocks:err(f'P{p}: no explanation blocks')
        prose=0
        for b in blocks:
            t=b.get('type');counts[t]+=1
            if t not in ALLOWED:err(f'P{p}: unknown block {t}')
            if t in ('paragraph','heading','note'):
                if not b.get('text','').strip():err(f'P{p}: empty text in {t}')
                else:prose+=1
            if t=='equation' and not b.get('latex','').strip():err(f'P{p}: missing latex')
            if t=='interactive':
                if b.get('kind') not in INTERACTIONS:err(f'P{p}: unsupported Lab {b.get("kind")}')
                cfg=b.get('config',{})
                if b.get('kind')=='output_shape':
                    if any(int(cfg.get(k,0))<0 for k in ('N','F','P','S')):err(f'P{p}: invalid shape params')
                    if int(cfg.get('S',0))==0 or int(cfg.get('F',0))==0:err(f'P{p}: F and S must >0')
                if b.get('kind')=='convolution':
                    X=cfg.get('input',[]);K=cfg.get('kernel',[])
                    if not X or not K or len(X)<len(K) or len(X[0])<len(K[0]):err(f'P{p}: invalid conv input size')
                    if X and any(len(row)!=len(X[0]) for row in X):err(f'P{p}: ragged conv matrix')
                    if K and any(len(row)!=len(K[0]) for row in K):err(f'P{p}: ragged kernel')
            if t=='quiz':
                for q in b.get('questions',[]):
                    total+=1; qt=q.get('type')
                    if qt not in Q_TYPES:err(f'P{p}: unknown quiz type {qt}')
                    if not q.get('id'):err(f'P{p}: question missing id')
                    if not q.get('explanation'):warn(f'P{p}: {q.get("id")} missing explanation')
                    if qt=='single_choice' and (not isinstance(q.get('answer'),int) or not (0<=q['answer']<len(q.get('options',[])))):err(f'P{p}: invalid choice answer')
                    if qt=='numeric' and not isinstance(q.get('answer'),(int,float)):err(f'P{p}: invalid numeric answer')
                    if qt=='multi_part':
                        if not q.get('parts'):err(f'P{p}: multipart empty')
                        for part in q.get('parts',[]):
                            if not isinstance(part.get('answer'),(int,float)):err(f'P{p}: multipart has nonnumeric answer')
        if prose==0:warn(f'P{p}: no continuous prose')
    if scope.get('start_page') and scope.get('end_page'):
        for p in range(scope['start_page'],scope['end_page']+1):
            if p not in seen:err(f'Scope page {p} missing lesson')
    return errors,warnings,total,counts

def main():
    ap=argparse.ArgumentParser();ap.add_argument('lesson',type=Path);ap.add_argument('--pdf',type=Path)
    a=ap.parse_args()
    doc=json.loads(a.lesson.read_text(encoding='utf-8'))
    pp=None
    if a.pdf:
        if not fitz:print('Install PyMuPDF to check PDF length',file=sys.stderr);sys.exit(2)
        with fitz.open(a.pdf) as d:pp=len(d)
    err,warn,qs,counts=lint(doc,pp)
    for x in err: print('ERROR:',x)
    for x in warn:print('WARNING:',x)
    print(f'Pages: {len(doc.get("lessons",[]))} | Questions: {qs} | Labs: {counts["interactive"]} | errors: {len(err)} | warnings: {len(warn)}')
    sys.exit(1 if err else 0)
if __name__=='__main__':main()
