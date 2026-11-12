"""Extraction regression fixtures run with temporary data, never against real user stores."""
from __future__ import annotations
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from docx import Document
from docx.shared import RGBColor
import pymupdf

from backend.app.services.document_extraction import extract_document,validate_source,ExtractionError,chunk_blocks,ocr_runtime
from backend.app.services.question_parser import parse_questions
from tools.sandbox import PROJECT


def word_bytes(paragraphs):
    doc=Document()
    for text in paragraphs:doc.add_paragraph(text)
    stream=io.BytesIO();doc.save(stream);return stream.getvalue()


def text_pdf(pages):
    doc=pymupdf.open()
    for text in pages:
        page=doc.new_page();page.insert_text((50,70),text,fontsize=12)
    return doc.tobytes()


MCQ=['Câu 1. Liên hợp quốc được thành lập năm nào?','A. 1945  B. 1946  C. 1947  D. 1948','Đáp án: A']


class ExtractionTests(unittest.TestCase):
    def test_word_single_line_choices_and_explicit_answer(self):
        result=extract_document(word_bytes(MCQ),'quiz.docx')
        q=result['questions'][0]
        self.assertEqual(q['question'],'Liên hợp quốc được thành lập năm nào?')
        self.assertEqual([c['text'] for c in q['choices']],['1945','1946','1947','1948'])
        self.assertEqual(q['answer'],'A');self.assertIsNone(q['source_page'])

    def test_question_header_can_be_empty_and_stem_wraps(self):
        result=extract_document(word_bytes(['Câu 12.','Trình bày','nội dung câu hỏi?','A. Một','B. Hai','C. Ba','D. Bốn']),'q.docx')
        self.assertEqual(result['questions'][0]['source_number'],12)
        self.assertEqual(result['questions'][0]['question'],'Trình bày nội dung câu hỏi?')

    def test_missing_answer_is_not_guessed(self):
        result=extract_document(word_bytes(MCQ[:2]),'unknown.docx')
        self.assertEqual(result['questions'][0]['answer'],'')
        self.assertIn('answer_not_found',result['questions'][0]['extraction_issues'])

    def test_missing_and_duplicate_choices_are_flagged(self):
        result=extract_document(word_bytes(['Câu 1. Một câu hỏi kiểm tra?','A. Một B. Một C. Hai']),'q.docx')
        self.assertIn('missing_choices',result['questions'][0]['extraction_issues'])
        self.assertIn('duplicate_or_empty_choices',result['questions'][0]['extraction_issues'])

    def test_partial_word_keeps_the_raw_content(self):
        result=extract_document(word_bytes(['Tài liệu chỉ có nội dung học tập.','Dòng dữ liệu thứ hai.']),'notes.docx')
        self.assertEqual(result['questions'],[])
        self.assertIn('Dòng dữ liệu thứ hai.','\n'.join(c['text'] for c in result['chunks']))

    def test_answer_tables_are_scoped_by_lesson(self):
        doc=Document()
        for lesson in [12,13]:
            doc.add_paragraph(f'BÀI {lesson}. Nội dung học')
            for text in MCQ[:2]:doc.add_paragraph(text)
        doc.add_paragraph('ĐÁP ÁN')
        for lesson,answer in [(12,'A'),(13,'D')]:
            doc.add_paragraph(f'Bài {lesson}')
            table=doc.add_table(rows=1,cols=2);table.cell(0,0).text=f'1.{answer}';table.cell(0,1).text='2.'
        buf=io.BytesIO();doc.save(buf)
        qs=extract_document(buf.getvalue(),'scoped.docx')['questions']
        self.assertEqual([(q['lesson'],q['answer']) for q in qs],[('12','A'),('13','D')])

    def test_horizontal_and_vertical_answer_tables(self):
        for horizontal in [True,False]:
            with self.subTest(horizontal=horizontal):
                doc=Document()
                for text in MCQ[:2]:doc.add_paragraph(text)
                doc.add_paragraph('ĐÁP ÁN')
                table=doc.add_table(rows=2,cols=2)
                values=[['Câu','1'],['Đáp án','D']] if horizontal else [['Số','Đáp án'],['1','D']]
                for r,row in enumerate(values):
                    for c,value in enumerate(row):table.cell(r,c).text=value
                buf=io.BytesIO();doc.save(buf)
                self.assertEqual(extract_document(buf.getvalue(),'table.docx')['questions'][0]['answer'],'D')

    def test_pdf_grid_table_has_choices_and_highlighted_answer(self):
        doc=pymupdf.open();page=doc.new_page(width=900,height=400)
        xs=[30,65,390,500,610,720,850];ys=[40,80,140]
        for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]),color=(0,0,0))
        for y in ys:page.draw_line((xs[0],y),(xs[-1],y),color=(0,0,0))
        headers=['TT','Question','A','B','C','D'];values=['1','Which year was the event?','1945','1946','1947','1948']
        page.draw_rect((610,80,720,140),fill=(1,1,0),color=None,overlay=False)
        for i,value in enumerate(headers):page.insert_text((xs[i]+4,65),value,fontsize=10)
        for i,value in enumerate(values):page.insert_text((xs[i]+4,110),value,fontsize=10)
        result=extract_document(doc.tobytes(),'table.pdf')
        self.assertEqual(len(result['questions']),1)
        q=result['questions'][0]
        self.assertEqual(q['answer'],'C');self.assertEqual(len(q['choices']),4)

    def test_red_option_is_detected_but_blue_labels_are_not_answers(self):
        doc=Document();doc.add_paragraph(MCQ[0])
        p=doc.add_paragraph()
        for label,text in [('A','1945'),('B','1946'),('C','1947'),('D','1948')]:
            p.add_run(label+'. ').font.color.rgb=RGBColor(0,0,255)
            run=p.add_run(text+'  ')
            if label=='C':run.font.color.rgb=RGBColor(255,0,0)
        buf=io.BytesIO();doc.save(buf)
        q=extract_document(buf.getvalue(),'colored.docx')['questions'][0]
        self.assertEqual(q['answer'],'C');self.assertEqual(q['answer_origin'],'formatting')

    def test_conflicting_marked_and_explicit_answers_are_unset(self):
        blocks=[{'text':MCQ[0]},{'text':MCQ[1],'marked_text':['B. 1946']},{'text':MCQ[2]}]
        q=parse_questions(blocks)[0][0]
        self.assertEqual(q['answer'],'');self.assertIn('conflicting_answers',q['extraction_issues'])

    def test_cyrillic_labels_do_not_modify_content(self):
        q=extract_document(word_bytes(['Câu 1. Nơi nào?','А. АРЕС. B. Việt Nam C. Lào D. Thái Lan']),'q.docx')['questions'][0]
        self.assertEqual(q['choices'][0]['label'],'A');self.assertEqual(q['choices'][0]['text'],'АРЕС.')
        self.assertIn('normalized_choice_label',q['extraction_issues'])

    def test_true_false_section_is_kept_in_source_not_mcqs(self):
        result=extract_document(word_bytes(['PHẦN II. TRẮC NGHIỆM ĐÚNG - SAI','Câu 1. Dữ liệu nguồn','a. Đúng','b. Sai','c. Đúng','d. Sai']),'q.docx')
        self.assertFalse(result['questions']);self.assertTrue(result['chunks'])

    def test_source_matching_table_is_preserved_in_stem(self):
        doc=Document();doc.add_paragraph('Câu 1. Nối các nội dung sau?')
        table=doc.add_table(rows=2,cols=2)
        table.cell(0,0).text='Sự kiện';table.cell(0,1).text='Năm'
        table.cell(1,0).text='1. Thành lập';table.cell(1,1).text='1945'
        doc.add_paragraph('A. 1a B. 1b C. 1c D. 1d');buf=io.BytesIO();doc.save(buf)
        q=extract_document(buf.getvalue(),'table.docx')['questions'][0]
        self.assertIn('1945',q['question']);self.assertEqual(q['source_number'],1)

    def test_pdf_text_question_spans_pages(self):
        content=text_pdf(['Cau 1. Which year?\nA. 1945\nB. 1946','C. 1947\nD. 1948\nAnswer: B\nAdditional text for PDF character threshold.'])
        result=extract_document(content,'cross.pdf')
        self.assertEqual(len(result['questions']),1)
        self.assertEqual(result['questions'][0]['answer'],'B')
        self.assertEqual(result['questions'][0]['source_page'],1)
        self.assertTrue(all(c['pages'] for c in result['chunks']))

    def test_pdf_header_cannot_be_mistaken_for_answer_A(self):
        content=text_pdf(['Cau 1. Which year of history?\nA. 1945\nB. 1946\nC. 1947\nD. 1948\nAnswer: D'])
        self.assertEqual(extract_document(content,'q.pdf')['questions'][0]['answer'],'D')

    def test_encrypted_pdf_has_clear_error(self):
        doc=pymupdf.open();doc.new_page()
        content=doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='password')
        with self.assertRaisesRegex(ExtractionError,'mật khẩu'):extract_document(content,'protected.pdf')

    def test_bad_and_empty_files_fail_before_parsing(self):
        for content,name in [(b'','empty.pdf'),(b'fake','bad.pdf'),(b'PKnope','bad.docx'),(b'text','file.exe')]:
            with self.subTest(name=name):
                with self.assertRaises(ExtractionError):extract_document(content,name)

    def test_zip_without_word_document_is_rejected(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('readme.txt','x')
        with self.assertRaises(ExtractionError):validate_source(buf.getvalue(),'fake.docx')

    def test_long_content_is_not_truncated(self):
        text='x'*5200
        chunks=chunk_blocks([{'text':text,'page':3}],'hash')
        self.assertEqual(''.join(c['text'].replace('\n','') for c in chunks),text)
        self.assertTrue(all(len(c['text'])<=1401 for c in chunks))
        self.assertTrue(all(c['pages']==[3] for c in chunks))

    def test_pdf_partial_ocr_failure_retains_other_pages(self):
        content=text_pdf(['Some readable textbook content on this page, with enough English words.',''])
        with patch('backend.app.services.document_extraction.ocr_image',side_effect=ExtractionError('ocr_timeout','timeout')):
            result=extract_document(content,'partial.pdf')
        self.assertEqual(result['summary']['review_pages'],1)
        self.assertEqual(result['pages'][1]['issue'],'ocr_timeout');self.assertTrue(result['chunks'])

    def test_local_ocr_scan(self):
        if not ocr_runtime()['available']:self.skipTest('Tesseract unavailable')
        page_doc=pymupdf.open();page=page_doc.new_page()
        page.insert_text((40,70),'Cau 1. Which year was the event?\nA. 1945\nB. 1946\nC. 1947\nD. 1948\nAnswer: A',fontsize=16)
        png=page.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
        scan=pymupdf.open();page=scan.new_page();page.insert_image(page.rect,stream=png)
        with tempfile.TemporaryDirectory() as temp:
            from backend.app.core.config import get_settings
            settings=get_settings().model_copy(update={'data_dir':Path(temp)})
            with patch('backend.app.services.document_extraction.get_settings',return_value=settings),patch('backend.app.services.document_extraction.data_path',side_effect=lambda *parts:Path(temp).joinpath(*parts)):
                result=extract_document(scan.tobytes(),'scan.pdf')
        self.assertEqual(result['summary']['ocr_pages'],1)
        self.assertIn('1945',' '.join(c['text'] for c in result['chunks']))

    def test_real_review_document_has_120_scoped_answers(self):
        paths=list((PROJECT/'data').glob('*.docx'))
        if not paths:self.skipTest('Real source fixture absent')
        result=extract_document(paths[0].read_bytes(),paths[0].name)
        self.assertEqual(result['summary']['questions'],120);self.assertEqual(result['summary']['with_answer'],120)
        for lesson,answer in [('12','A'),('13','B'),('14','D'),('15','A')]:
            qs=[q for q in result['questions'] if q['lesson']==lesson]
            self.assertEqual(len(qs),30);self.assertEqual(qs[0]['answer'],answer)


class DocumentApiTests(unittest.TestCase):
    def test_isolated_api_upload_retry_edit_ownership_and_quiz(self):
        code=r'''
from pathlib import Path
import io,json,sys,tempfile
import os,shutil
temporary=tempfile.TemporaryDirectory();root=Path(temporary.name)
os.environ.update(COBRAQ_PROFILE='local',COBRAQ_DATA_DIR=str(root/'data'),COBRAQ_RESEARCH_ROOT=str(root/'research'),COBRAQ_VECTOR_ENABLED='false',COBRAQ_EXTERNAL_AI_ENABLED='false',COBRAQ_ENV_FILE=str(root/'empty.env'))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.document_store import document_jobs,DocumentJobs,DocumentStore
from docx import Document
doc=Document();doc.add_paragraph('Câu 1. Một câu hỏi thử nghiệm?');doc.add_paragraph('A. Một B. Hai C. Ba D. Bốn')
buf=io.BytesIO();doc.save(buf);content=buf.getvalue()
try:
 with TestClient(app) as c:
  from backend.app.core.security import create_access_token
  account={'email':'teacher@example.com'}
  token=create_access_token({'sub':account['email'],'role':'teacher'})
  headers={'Authorization':'Bearer '+token}
  r=c.post('/api/files/upload',headers=headers,files={'file':('input.docx',content)})
  assert r.status_code==200,r.text
  row=r.json();fid=row['file_id'];assert row['with_answer']==0
  source=c.get(f'/api/documents/{fid}/source',headers=headers);assert source.content==content
  assert c.get(f'/api/documents/{fid}/content',headers=headers).json()['chunks']
  assert c.get('/api/quiz/start?file_id='+fid,headers=headers).status_code==422
  questions=c.get(f'/api/files/{fid}/questions',headers=headers).json()['questions'];q=questions[0]
  update={k:q[k] for k in ('question','choices','answer')};update['answer']='B'
  assert c.put(f'/api/files/{fid}/questions/1',headers=headers,json=update).status_code==200
  assert c.get('/api/stats',headers=headers).json()['with_answer']==1
  quiz=c.get('/api/quiz/start?file_id='+fid,headers=headers);assert quiz.status_code==200,quiz.text
  bad={**update,'choices':[{'label':'A','text':'same'}]*4}
  assert c.put(f'/api/files/{fid}/questions/1',headers=headers,json=bad).status_code==422
  invalid_types={**update,'choices':[{'label':label,'text':{'nested':'invalid'}} for label in 'ABCD']}
  assert c.put(f'/api/files/{fid}/questions/1',headers=headers,json=invalid_types).status_code==422
  assert c.put(f'/api/files/{fid}/questions/1',headers=headers,json={**update,'answer':'AB'}).status_code==422
  retry=c.post('/api/files/upload',headers=headers,files={'file':('renamed.docx',content)})
  assert retry.json()['file_id']==fid and retry.json()['added']==0
  assert c.get(f'/api/files/{fid}/questions',headers=headers).json()['questions'][0]['answer']=='B'
  assert c.get(f'/api/documents/{fid}/source',headers={'X-User-Id':'other'}).status_code==401
  assert c.get(f'/api/documents/{fid}/content',headers={'X-User-Id':'other'}).status_code==401
  other_token=create_access_token({'sub':'other@example.com','role':'student'})
  assert c.get(f'/api/documents/{fid}/source',headers={'Authorization':'Bearer '+other_token,'X-User-Id':account['email']}).status_code==404
  assert c.get('/api/documents/doc-../../etc',headers=headers).status_code==404
  assert c.post('/api/documents/upload',headers=headers,files={'file':('bad.docx',b'invalid')}).status_code==422
  doc.add_paragraph('Nội dung khác cùng tên');b=io.BytesIO();doc.save(b)
  second=c.post('/api/files/upload',headers=headers,files={'file':('input.docx',b.getvalue())})
  assert second.json()['file_id']!=fid
  assert c.get('/api/documents',headers=headers).json()['documents']
  jobs=document_jobs();jobs.executor.shutdown(wait=True)
  # A partial job is explicitly interrupted after a restart.
  from backend.app.services.document_store import atomic_json
  row=jobs.store.status(account['email'],fid);row['status']='processing'
  atomic_json(jobs.store.folder(account['email'],fid)/'status.json',row)
  recovered=DocumentJobs(DocumentStore());assert recovered.store.status(account['email'],fid)['status']=='interrupted'
  recovered.executor.shutdown(wait=True)
 print('API upload/edit/retry/source isolation/restart checks passed')
finally:
 temporary.cleanup()
'''
        completed=subprocess.run([sys.executable,'-c',code],cwd=PROJECT,capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)


if __name__=='__main__':unittest.main()
