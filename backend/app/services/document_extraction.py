"""Read PDF/DOCX into traceable blocks, pages and chunks, with bounded local OCR."""
from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import unicodedata
import zipfile

from ..core.config import get_settings, PROJECT_ROOT, data_path
from .question_parser import parse_questions

EXTRACTOR_VERSION='documents-v1'


class ExtractionError(ValueError):
    def __init__(self,code,message):
        super().__init__(message);self.code=code


def clean(text: str) -> str:
    text=unicodedata.normalize('NFC',text).replace('\x00','').replace('\u00ad','')
    return '\n'.join(re.sub(r'[ \t]+',' ',line).strip() for line in text.splitlines()).strip()


def validate_source(content: bytes, filename: str):
    if not content: raise ExtractionError('empty_file','Tệp rỗng. Chọn lại tài liệu có nội dung.')
    extension=Path(filename).suffix.lower()
    if extension not in {'.pdf','.docx'}:raise ExtractionError('unsupported_type','Chỉ hỗ trợ tệp Word .docx hoặc PDF.')
    if extension=='.pdf':
        if not content.lstrip()[:1024].startswith(b'%PDF-'):
            raise ExtractionError('invalid_pdf','Tệp không có định dạng PDF hợp lệ.')
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names=archive.namelist()
                if 'word/document.xml' not in names or '[Content_Types].xml' not in names:
                    raise ExtractionError('invalid_docx','Tệp không phải tài liệu Word .docx hợp lệ.')
                if len(names)>10000 or sum(i.file_size for i in archive.infolist())>150*1024*1024:
                    raise ExtractionError('expanded_file_limit','Tài liệu Word quá lớn sau khi giải nén. Hãy chia tài liệu nhỏ hơn.')
        except (zipfile.BadZipFile,RuntimeError) as exc:
            raise ExtractionError('invalid_docx','Tệp Word bị hỏng hoặc không đọc được.') from exc
    return extension


def ocr_runtime(prepare=False):
    cfg=get_settings()
    configured=cfg.tesseract_cmd
    exe=shutil.which(configured or 'tesseract')
    if not exe:
        candidate=Path(configured) if configured else Path('C:/Program Files/Tesseract-OCR/tesseract.exe')
        exe=str(candidate) if candidate.is_file() else None
    if not exe:return {'available':False,'languages':[],'reason':'Chưa có Tesseract để đọc PDF scan.'}
    roots=[Path(cfg.tessdata_dir)] if cfg.tessdata_dir else []
    roots += [PROJECT_ROOT/'research/tools/tessdata', Path(exe).parent/'tessdata',Path('/usr/share/tesseract-ocr/5/tessdata'),Path('/usr/share/tessdata')]
    assets={lang:next((root/f'{lang}.traineddata' for root in roots if (root/f'{lang}.traineddata').is_file()),None) for lang in ('vie','eng')}
    langs=[lang for lang,asset in assets.items() if asset]
    if not langs:return {'available':False,'languages':[],'reason':'Thiếu dữ liệu ngôn ngữ OCR tiếng Việt/Anh.'}
    folder=data_path('cache','tessdata')
    if prepare:
        folder.mkdir(parents=True,exist_ok=True)
        for lang in langs:
            source=assets[lang];target=folder/source.name
            if not target.exists() or target.stat().st_size!=source.stat().st_size:
                shutil.copyfile(source,target)
    return {'available':True,'executable':exe,'languages':langs,'tessdata':str(folder)}


def ocr_image(png: bytes) -> tuple[list[dict],float | None]:
    runtime=ocr_runtime(prepare=True)
    if not runtime['available']:raise ExtractionError('ocr_unavailable',runtime['reason'])
    try:
        process=subprocess.run([runtime['executable'],'stdin','stdout','--tessdata-dir',runtime['tessdata'],
              '-l','+'.join(runtime['languages']),'--psm','3','-c','tessedit_create_tsv=1'],input=png,capture_output=True,
              timeout=get_settings().ocr_page_timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError('ocr_timeout','Trang scan vượt thời gian OCR cho phép; cần kiểm tra hoặc tách trang.') from exc
    if process.returncode:raise ExtractionError('ocr_failed','Không đọc được ảnh trang bằng OCR.')
    groups=defaultdict(list); scores=[]
    output=process.stdout.decode('utf-8',errors='replace')
    if not output.startswith('level\t'):raise ExtractionError('ocr_format','OCR không trả dữ liệu vị trí/confidence hợp lệ.')
    for row in csv.DictReader(io.StringIO(output),delimiter='\t'):
        text=(row.get('text') or '').strip()
        if not text:continue
        key=tuple(row.get(k,'') for k in ('block_num','par_num','line_num'))
        groups[key].append(text)
        try:
            score=float(row['conf'])
            if score>=0:scores.append(score)
        except (KeyError,ValueError):pass
    return [{'text':' '.join(words),'kind':'paragraph','marked_text':[]} for words in groups.values()],sum(scores)/len(scores) if scores else None


def word_blocks(content: bytes):
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    from docx.oxml.ns import qn
    doc=Document(io.BytesIO(content));blocks=[];warnings=[]
    def paragraph(p):
        text=p.text
        marked=[]
        for run in p.runs:
            rgb=run.font.color.rgb
            red=rgb is not None and int(str(rgb)[:2],16)>150 and int(str(rgb)[2:4],16)<110 and int(str(rgb)[4:],16)<110
            if red or run.font.highlight_color is not None:marked.append(run.text)
        if text.strip():blocks.append({'text':text,'kind':'paragraph','page':None,'marked_text':marked})
    for element in doc.element.body:
        if element.tag==qn('w:p'):paragraph(Paragraph(element,doc))
        elif element.tag==qn('w:tbl'):
            table=Table(element,doc)
            pending_numbers=[]
            # Body-order traversal prevents answer keys from different lessons being mixed.
            for row in table.rows:
                seen=set();cells=[]
                for cell in row.cells:
                    if id(cell._tc) not in seen:cells.append(cell);seen.add(id(cell._tc))
                texts=[c.text.strip() for c in cells]
                number_cells=texts[1:] if texts and re.fullmatch(r'Câu(?: hỏi)?|STT|Số câu',texts[0],re.I) else texts
                if number_cells and all(re.fullmatch(r'\d{1,4}[.)]?',t) for t in number_cells):
                    pending_numbers=[int(t.rstrip('.)')) for t in number_cells]
                    blocks.append({'text':' | '.join(texts),'kind':'table','page':None,'marked_text':[]})
                    continue
                answer_cells=texts[1:] if texts and re.fullmatch(r'Đáp\s*án|ĐA|Answer',texts[0],re.I) else texts
                if pending_numbers and len(answer_cells)==len(pending_numbers) and all(re.fullmatch('[A-D]',t) for t in answer_cells):
                    blocks.append({'text':'  '.join(f'{n}.{a}' for n,a in zip(pending_numbers,answer_cells)),
                                   'kind':'answer_key','page':None,'marked_text':[]})
                    pending_numbers=[];continue
                if len(texts)==2 and re.fullmatch(r'\d{1,4}[.)]?',texts[0]) and re.fullmatch('[ABCD]',texts[1]):
                    blocks.append({'text':texts[0].rstrip('.)')+'.'+texts[1],'kind':'answer_key','page':None,'marked_text':[]});continue
                if texts and all(not t or re.fullmatch(r'\d{1,4}\s*(?:[.)-]\s*[ABCD]?|[ABCD][.)]?)',t,re.I) for t in texts) and any(re.search('[ABCD]',t) for t in texts):
                    blocks.append({'text':'  '.join(texts),'kind':'answer_key','page':None,'marked_text':[]})
                elif len(cells)>=5 and re.fullmatch(r'(?:Câu\s*)?\d+[.)]?',texts[0],re.I):
                    # Typical TT | Nội dung | A | B | C | D table.
                    number=texts[0].rstrip('.)');body=texts[1]
                    blocks.append({'text':f'Câu {number}. {body}','kind':'paragraph','page':None,'marked_text':[]})
                    for i,cell in enumerate(cells[2:6]):
                        marks=[]
                        shading=cell._tc.xpath('.//w:shd')
                        if any(s.get(qn('w:fill'),'').upper() not in {'','AUTO','FFFFFF','000000'} for s in shading):marks=[f'{"ABCD"[i]}. {cell.text}']
                        blocks.append({'text':f'{"ABCD"[i]}. {cell.text}','kind':'paragraph','page':None,'marked_text':marks})
                else:
                    if any(re.match(r'^\s*(?:Câu\s*)?\d+[.:)]',t,re.I) and re.search(r'\b[A-D][.)]\s',t) for t in texts):
                        for cell in cells:
                            for p in cell.paragraphs:paragraph(p)
                    else:blocks.append({'text':' | '.join(texts),'kind':'table','page':None,'marked_text':[]})
    images=len(doc.inline_shapes)
    if images:warnings.append({'code':'word_images','message':f'Tài liệu có {images} ảnh nhúng. Chữ trong ảnh Word chưa được OCR; xuất PDF nếu cần đọc phần này.'})
    if not blocks:raise ExtractionError('no_text','Không tìm thấy văn bản trong Word. Nếu nội dung là ảnh, hãy xuất sang PDF để OCR.')
    return blocks,[{'page':None,'method':'docx','status':'extracted','confidence':None}],warnings


def pdf_question_tables(page):
    """Recover grid tables whose columns explicitly describe four MCQ choices."""
    result=[]
    try:tables=page.find_tables().tables
    except Exception:return result
    red_spans=[];highlights=[]
    import pymupdf
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                color=span.get('color',0)
                if (color>>16)&255>150 and (color>>8)&255<110 and color&255<110:
                    box=pymupdf.Rect(span['bbox']);red_spans.append(pymupdf.Point((box.x0+box.x1)/2,(box.y0+box.y1)/2))
    for drawing in page.get_drawings():
        fill=drawing.get('fill')
        if fill and max(fill)-min(fill)>.2 and max(fill)>.5:highlights.append(drawing['rect'])
    for table in tables:
        rows=table.extract()
        if not rows or len(rows[0])<6:continue
        header=[clean(c or '') for c in rows[0]]
        question_column=next((i for i,v in enumerate(header) if re.search(r'Nội\s*dung|Câu\s*hỏi|Question',v,re.I)),None)
        choice_columns={label:next((i for i,v in enumerate(header) if re.fullmatch(rf'(?:Đáp\s*án\s*)?{label}',v,re.I)),None) for label in 'ABCD'}
        if question_column is None or any(i is None for i in choice_columns.values()):continue
        for row_index,values in enumerate(rows[1:],1):
            values=[clean(v or '') for v in values]
            if len(values)<6 or not re.fullmatch(r'\d+[.)]?',values[0]):continue
            number=values[0].rstrip('.)')
            def cell_text(col):
                bbox=table.rows[row_index].cells[col]
                return clean(page.get_textbox(bbox)) if bbox else values[col]
            result.append({'text':f'Câu {number}. {cell_text(question_column)}','kind':'question_only','marked_text':[]})
            for label,col in choice_columns.items():
                value=cell_text(col)
                bbox=table.rows[row_index].cells[col]
                box=pymupdf.Rect(bbox) if bbox else None
                marked=box is not None and (any(box.contains(point) for point in red_spans) or
                    any(rect.contains(pymupdf.Point((box.x0+box.x1)/2,(box.y0+box.y1)/2)) for rect in highlights))
                text=label+'. '+value
                result.append({'text':text,'kind':'question_only','marked_text':[text] if marked else []})
    return result


def pdf_blocks(content: bytes, progress=None):
    import pymupdf as fitz
    try:doc=fitz.open(stream=content,filetype='pdf')
    except Exception as exc:raise ExtractionError('invalid_pdf','PDF bị hỏng hoặc không thể mở.') from exc
    blocks,pages,warnings=[],[],[];started=time.monotonic()
    with doc:
        if doc.needs_pass:raise ExtractionError('encrypted_pdf','PDF có mật khẩu. Hãy mở khóa rồi tải lại.')
        if len(doc)>get_settings().max_document_pages:raise ExtractionError('page_limit',f'PDF vượt giới hạn {get_settings().max_document_pages} trang. Hãy chia nhỏ tài liệu.')
        for i,page in enumerate(doc):
            if progress:progress(i,len(doc),'Đang đọc trang '+str(i+1))
            if time.monotonic()-started>get_settings().extraction_timeout:
                raise ExtractionError('document_timeout','Tài liệu vượt thời gian xử lý. Hãy chia PDF thành các phần nhỏ hơn.')
            text=page.get_text(sort=True)
            letters=len(re.findall(r'\w',text))
            method='pdf_text';confidence=None;page_blocks=[];issue=''
            # Nearly empty text or corrupted glyph mapping requires OCR, page by page.
            if letters<15 or text.count('\ufffd')>max(3,len(text)*.03):
                try:
                    area=max(1,page.rect.width*page.rect.height)
                    scale=min(2.5, math.sqrt(12_000_000/area))
                    png=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
                    page_blocks,confidence=ocr_image(png);method='tesseract'
                    if not page_blocks:issue='empty_page'
                    elif confidence is not None and confidence<70:issue='low_ocr_confidence'
                except ExtractionError as exc:
                    issue=exc.code
                    warnings.append({'code':exc.code,'page':i+1,'message':str(exc)})
                except Exception:
                    issue='page_render_failed'
                    warnings.append({'code':issue,'page':i+1,'message':'Không dựng được ảnh trang để OCR; cần kiểm tra trang này.'})
            else:
                # Preserve colors at span granularity for marked answer choices.
                marks=[]
                for b in page.get_text('dict')['blocks']:
                    for line in b.get('lines',[]):
                        for span in line['spans']:
                            color=span.get('color',0);r,g,b=(color>>16)&255,(color>>8)&255,color&255
                            if r>150 and g<110 and b<110:marks.append(span['text'])
                rects=[]
                for drawing in page.get_drawings():
                    fill=drawing.get('fill')
                    if fill and max(fill)-min(fill)>.2 and max(fill)>.5:rects.append(drawing['rect'])
                for b in page.get_text('dict')['blocks']:
                    for line in b.get('lines',[]):
                        for span in line['spans']:
                            x0,y0,x1,y1=span['bbox']
                            if any(rect.contains(fitz.Point((x0+x1)/2,(y0+y1)/2)) for rect in rects):marks.append(span['text'])
                page_blocks=[{'text':line,'kind':'paragraph','marked_text':marks} for line in text.splitlines() if line.strip()]
                page_blocks+=pdf_question_tables(page)
            pages.append({'page':i+1,'method':method,'status':'needs_review' if issue else 'extracted',
                          'confidence':round(confidence,2) if confidence is not None else None,'issue':issue,
                          'characters':sum(len(b['text']) for b in page_blocks)})
            for block in page_blocks:block['page']=i+1;blocks.append(block)
            if issue and issue not in {'ocr_unavailable','ocr_timeout','ocr_failed'}:
                warnings.append({'code':issue,'page':i+1,'message':'Cần kiểm tra nội dung hoặc chất lượng OCR của trang này.'})
        if progress:progress(len(doc),len(doc),'Hoàn tất đọc các trang')
    if not blocks:raise ExtractionError('no_readable_pages','Không đọc được trang nào. Kiểm tra OCR và chất lượng PDF scan.')
    return blocks,pages,warnings


def chunk_blocks(blocks, source_hash):
    chunks=[];buffer=[];pages=set();count=0
    def flush():
        nonlocal buffer,pages,count
        text='\n'.join(buffer).strip()
        if text:
            chunks.append({'id':'chunk-'+hashlib.sha256(f'{source_hash}:{len(chunks)}:{text}'.encode()).hexdigest()[:24],
                           'text':text,'source_sha256':source_hash,'pages':sorted(pages),
                           'review_status':'review_required'})
        buffer=[];pages=set();count=0
    for block in blocks:
        if block.get('kind')=='question_only':continue
        text=clean(block['text'])
        # Bound even unusually long paragraphs without dropping their suffix.
        pieces=[text[i:i+1000] for i in range(0,len(text),1000)]
        for piece in pieces:
            page=block.get('page')
            if buffer and (count+len(piece)>1400 or (page is not None and pages and page not in pages)):flush()
            buffer.append(piece);count+=len(piece)
            if page is not None:pages.add(page)
    flush();return chunks


def extract_document(content: bytes, filename: str, progress=None) -> dict:
    started=time.monotonic();extension=validate_source(content,filename)
    try:
        blocks,pages,warnings=pdf_blocks(content,progress) if extension=='.pdf' else word_blocks(content)
    except ExtractionError:raise
    except Exception as exc:raise ExtractionError('read_failed','Không đọc được tài liệu. Kiểm tra tệp hoặc lưu lại bằng Word/PDF chuẩn.') from exc
    for i,block in enumerate(blocks):block['index']=i+1;block['text']=unicodedata.normalize('NFC',block['text']).replace('\x00','')
    sha=hashlib.sha256(content).hexdigest()
    questions,question_warnings=parse_questions(blocks)
    unique=[];seen=set()
    for q in questions:
        key=(q['source_page'],q['lesson'],q['source_number'],q['question'],tuple((c['label'],c['text']) for c in q['choices']))
        if key not in seen:unique.append(q);seen.add(key)
    questions=unique
    for i,q in enumerate(questions,1):q['id']=i
    warnings+=question_warnings
    flagged=sum(bool(q['extraction_issues']) for q in questions)
    if flagged:warnings.append({'code':'questions_need_review','message':f'{flagged} câu cần kiểm tra phương án hoặc bổ sung đáp án.'})
    return {'version':EXTRACTOR_VERSION,'source_sha256':sha,'filename':filename,'filetype':extension[1:],
            'pages':pages,'blocks':[{k:v for k,v in b.items() if k!='marked_text'} for b in blocks if b.get('kind')!='question_only'],
            'chunks':chunk_blocks(blocks,sha),'questions':questions,'warnings':warnings,
            'summary':{'pages':len(pages) if extension=='.pdf' else None,'blocks':len(blocks),
                       'characters':sum(len(b['text']) for b in blocks),'questions':len(questions),
                       'with_answer':sum(bool(q['answer']) for q in questions),
                       'questions_need_review':flagged,
                       'ocr_pages':sum(p['method']=='tesseract' for p in pages),
                       'review_pages':sum(p['status']=='needs_review' for p in pages),
                       'elapsed_seconds':round(time.monotonic()-started,3)},
            'review_status':'review_required'}
