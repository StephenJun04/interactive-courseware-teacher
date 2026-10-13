#!/usr/bin/env python3
"""Build a self-contained V8-style bilingual PDF+teaching HTML from authored JSON."""
import argparse,base64,hashlib,html,json,re,subprocess,sys,time,zipfile
from pathlib import Path
try: import fitz
except ImportError:
    print('PyMuPDF required: pip install pymupdf',file=sys.stderr);sys.exit(2)
from check_lesson import lint
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def pdf_images(source, scale, quality, cache_dir=None):
    """Reuse only exact PDF bytes + render settings + PyMuPDF version matches."""
    signature=hashlib.sha256(source.read_bytes()).hexdigest()
    identity=json.dumps([signature,scale,quality,fitz.VersionBind,1])
    cache_file=None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True,exist_ok=True)
        cache_file=cache_dir/(hashlib.sha256(identity.encode()).hexdigest()+'.json')
        try:
            value=json.loads(cache_file.read_text(encoding='utf-8'))
            if value['identity']==identity and value['slides'] and all(
                x['page']==i+1 and x['width']>0 and x['height']>0 and x['data']
                for i,x in enumerate(value['slides'])):
                return value['slides'],True
        except (OSError,ValueError,KeyError,TypeError):
            pass
    slides=[]
    with fitz.open(source) as pdf:
        for p in pdf:
            pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            data=base64.b64encode(pix.tobytes('jpeg',jpg_quality=quality)).decode('ascii')
            slides.append({'page':p.number+1,'width':pix.width,'height':pix.height,'data':data})
    if cache_file is not None:
        # Atomic replacement prevents interrupted builds from leaving partial JSON.
        import os,tempfile
        fd,tmp=tempfile.mkstemp(prefix='.pdf-',dir=cache_dir)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump({'identity':identity,'slides':slides},f,separators=(',',':'))
            os.replace(tmp,cache_file)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return slides,False

def svg_math(exprs):
    unique=list(dict.fromkeys(x for x in exprs if x))
    if not unique: return {},True
    try:
        p=subprocess.run(['node',str(HERE/'render_math.cjs')],
                input=json.dumps({'expressions':unique}).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=50,check=True)
        res=json.loads(p.stdout)
        ok=all(x and '<svg' in x for x in res)
        return dict(zip(unique,res)),ok
    except (OSError,subprocess.CalledProcessError,ValueError,subprocess.TimeoutExpired) as e:
        print('WARNING: offline SVG formulas unavailable (install node + mathjax-full); using LaTeX text fallback.',file=sys.stderr)
        return {},False

def safe_inline(s):
    """Render lightweight emphasis; no arbitrary HTML content from author data."""
    s=html.escape(str(s),quote=True)
    return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)

def prepare(course,pdf,math):
    for l in course['lessons']:
        for b in l['blocks']:
            t=b['type']
            if t=='paragraph':b['html']=safe_inline(b.get('text',''))
            if t=='list':
                b['items']=[{'html':safe_inline(i.get('text','') if isinstance(i,dict) else i)} for i in b.get('items',[])]
            if t=='equation':b['svg']=math.get(b.get('latex',''))
            if t=='example':
                for step in b.get('steps',[]):
                    if step.get('latex'):step['svg']=math.get(step['latex'])
            if t=='figure':
                p=int(b.get('page',l['page']))
                if not 1<=p<=len(pdf):raise ValueError(f'Figure page {p} out of bounds')
                page=pdf[p-1]
                rect=page.rect
                if 'rect_rel' in b:
                    coords=b['rect_rel']
                    if len(coords)!=4 or any(not 0<=x<=1 for x in coords):raise ValueError('rect_rel needs 4 normalized coords')
                    clip=fitz.Rect(rect.x0+rect.width*coords[0],rect.y0+rect.height*coords[1],rect.x0+rect.width*coords[2],rect.y0+rect.height*coords[3])
                    if clip.is_empty:raise ValueError('Empty figure crop')
                else:clip=rect
                pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),clip=clip,alpha=False)
                b['src']='data:image/jpeg;base64,'+base64.b64encode(pix.tobytes('jpeg',jpg_quality=80)).decode()
    return course

def build(a):
    started=time.perf_counter();metrics={}
    course=json.loads(a.lesson.read_text(encoding='utf-8'))
    with fitz.open(a.pdf) as pdf:
        errors,warnings,nq,ct=lint(course,len(pdf))
        for w in warnings:print('WARNING:',w,file=sys.stderr)
        if errors:
            for e in errors:print('ERROR:',e,file=sys.stderr)
            raise RuntimeError('Lesson schema check failed')
        exprs=[]
        for l in course['lessons']:
            for b in l.get('blocks',[]):
                if b['type']=='equation':exprs.append(b.get('latex'))
                if b['type']=='example':exprs.extend(s.get('latex') for s in b.get('steps',[]) if s.get('latex'))
        t=time.perf_counter();math,mathok=svg_math(exprs)
        metrics['math_seconds']=round(time.perf_counter()-t,4)
        course=prepare(course,pdf,math)
    t=time.perf_counter()
    cache=None if a.no_cache else (a.cache_dir or a.out.parent/'.courseware-cache')
    slides,hit=pdf_images(a.pdf,a.scale,a.jpeg_quality,cache)
    metrics['pdf_seconds']=round(time.perf_counter()-t,4)
    metrics['pdf_cache_hit']=hit
    data=json.dumps(course,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page_images=json.dumps(slides,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    appjs=(HERE/'reader.js').read_bytes();template=(ROOT/'templates/reader.html').read_text(encoding='utf-8')
    replacements={'__PAGE_TITLE__':html.escape(course['title']),'__BRAND_TITLE__':html.escape(course['title']),
                  '__BRAND_SUBTITLE__':html.escape(course.get('subtitle','原版课件 · 独立对照')),
                  '__COURSE_DATA__':data,'__SLIDE_DATA__':page_images,'__APP_SCRIPT_B64__':base64.b64encode(appjs).decode()}
    for src,repl in replacements.items():template=template.replace(src,repl)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(template,encoding='utf-8')
    print(f'Wrote: {a.out} ({a.out.stat().st_size//1024} KB), {len(slides)} PDF pages, {len(course["lessons"])} lessons, {nq} questions, {ct["interactive"]} Labs, Math SVG: {mathok}')
    if a.zip:
        a.zip.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
            z.write(a.out,arcname=a.out.name);z.write(a.pdf,arcname=a.pdf.name)
            z.writestr('打开方式.txt','请先解压，再用 Chrome/Edge/Firefox 等浏览器打开 HTML。左侧讲解，右侧原始 PDF 页面独立滚动。\n')
        print('Wrote offline zip:',a.zip)
    metrics['total_seconds']=round(time.perf_counter()-started,4)
    print('Build timing:',json.dumps(metrics,ensure_ascii=False))
    if a.metrics_json:
        a.metrics_json.parent.mkdir(parents=True,exist_ok=True)
        a.metrics_json.write_text(json.dumps(metrics,indent=2),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--lesson',required=True,type=Path);ap.add_argument('--pdf',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path);ap.add_argument('--zip',type=Path)
    ap.add_argument('--scale',type=float,default=1.5,help='Render scale for PDF preview')
    ap.add_argument('--jpeg-quality',type=int,default=77)
    ap.add_argument('--cache-dir',type=Path,help='PDF render cache; defaults next to output HTML')
    ap.add_argument('--no-cache',action='store_true',help='Render directly without reading/writing cache')
    ap.add_argument('--metrics-json',type=Path,help='Write observed build timing (not authoring time)')
    a=ap.parse_args()
    if a.scale<=0 or not 20<=a.jpeg_quality<=95:ap.error('scale must >0 and jpeg quality 20..95')
    build(a)
if __name__=='__main__':main()
