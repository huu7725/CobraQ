"""Background document extraction and traceable results for PDF / DOCX."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from ..core.config import get_settings
from ..core.security import get_current_user
from ..services.document_store import DocumentStore, document_jobs
from ..services.document_extraction import ExtractionError, ocr_runtime

router=APIRouter(prefix='/documents',tags=['documents'])


def owner(user,x_user_id,x_file_for=''):
    if x_file_for:
        if not user or user.get('role') not in {'teacher','admin'}:raise HTTPException(403,'Cần quyền giáo viên')
        return x_file_for
    return user['sub'] if user else (x_user_id or 'guest')


@router.get('/capabilities')
def capabilities():
    runtime=ocr_runtime()
    return {'extensions':['pdf','docx'],'max_upload_bytes':get_settings().max_upload_bytes,
            'max_pdf_pages':get_settings().max_document_pages,'ocr':{k:v for k,v in runtime.items() if k in {'available','languages','reason'}},
            'processing':'local','question_types':['multiple_choice'],'auto_approval':False}


async def receive(file):
    content=await file.read(get_settings().max_upload_bytes+1)
    if len(content)>get_settings().max_upload_bytes:raise HTTPException(413,f'Tệp vượt giới hạn {get_settings().max_upload_bytes // (1024*1024)} MB. Hãy chia nhỏ tài liệu.')
    return content


@router.post('/upload',status_code=202)
async def upload(file: UploadFile=File(...),x_user_id:str=Header(default='guest'),x_file_for:str=Header(default=''),
                 user:dict=Depends(get_current_user)):
    uid=owner(user,x_user_id,x_file_for)
    content=await receive(file)
    try:return document_jobs().submit(uid,content,file.filename or 'document')
    except ExtractionError as exc:raise HTTPException(429 if exc.code=='queue_full' else 422,{'code':exc.code,'message':str(exc)}) from exc


@router.get('')
def documents(x_user_id:str=Header(default='guest'),user:dict=Depends(get_current_user)):
    return {'documents':DocumentStore().list(owner(user,x_user_id))}


@router.get('/{document_id}')
def status(document_id:str,x_user_id:str=Header(default='guest'),x_file_for:str=Header(default=''),user:dict=Depends(get_current_user)):
    try:return DocumentStore().status(owner(user,x_user_id,x_file_for),document_id)
    except KeyError:raise HTTPException(404,'Không tìm thấy tài liệu')


@router.get('/{document_id}/content')
def content(document_id:str,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),
            x_user_id:str=Header(default='guest'),user:dict=Depends(get_current_user)):
    try:report=DocumentStore().report(owner(user,x_user_id),document_id)
    except KeyError:raise HTTPException(404,'Tài liệu chưa có kết quả trích xuất')
    return {'filename':report['filename'],'source_sha256':report['source_sha256'],'summary':report['summary'],
            'pages':report['pages'],'warnings':report['warnings'], 'chunks':report['chunks'][offset:offset+limit],
            'total_chunks':len(report['chunks']),'offset':offset,'review_status':report['review_status']}


@router.get('/{document_id}/source')
def source(document_id:str,x_user_id:str=Header(default='guest'),user:dict=Depends(get_current_user)):
    store=DocumentStore();uid=owner(user,x_user_id)
    try:row=store.status(uid,document_id)
    except KeyError:raise HTTPException(404,'Không tìm thấy tài liệu')
    return FileResponse(store.folder(uid,document_id)/('source'+Path(row['filename']).suffix.lower()),
                        filename=row['filename'],media_type='application/octet-stream')


@router.get('/{document_id}/pages/{page}')
def page_image(document_id:str,page:int,x_user_id:str=Header(default='guest'),user:dict=Depends(get_current_user)):
    import pymupdf
    store=DocumentStore();uid=owner(user,x_user_id)
    try:row=store.status(uid,document_id)
    except KeyError:raise HTTPException(404,'Không tìm thấy tài liệu')
    if Path(row['filename']).suffix.lower()!='.pdf':raise HTTPException(422,'Word không có số trang cố định. Hãy mở tệp nguồn để đối chiếu.')
    with pymupdf.open(store.folder(uid,document_id)/'source.pdf') as doc:
        if doc.needs_pass:raise HTTPException(422,'PDF có mật khẩu')
        if not 1<=page<=len(doc):raise HTTPException(404,'Trang không hợp lệ')
        image=doc[page-1].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3),alpha=False)
        return Response(image.tobytes('png'),media_type='image/png')
