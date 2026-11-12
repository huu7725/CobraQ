"""Persist original files and extraction reports; publish complete results atomically."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from functools import wraps
import hashlib
import json
import logging
from pathlib import Path
import re
from threading import Event, RLock
from uuid import uuid4

from ..core.config import data_path
from .document_extraction import extract_document, validate_source, ExtractionError, EXTRACTOR_VERSION

log=logging.getLogger(__name__)
LOCK=RLock()


def storage_write_lock(function):
    @wraps(function)
    def synchronized(*args,**kwargs):
        with LOCK:return function(*args,**kwargs)
    return synchronized


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)


def read_json(path, default=None):
    if not path.exists():return default
    return json.loads(path.read_text(encoding='utf-8'))


def user_folder(uid):
    return data_path('users')/re.sub(r'[^\w]','_',uid or 'guest')


class DocumentStore:
    def __init__(self, root=None):
        self.root=Path(root) if root else data_path('documents')

    def owner(self,uid):
        return self.root/hashlib.sha256(uid.encode()).hexdigest()[:24]

    def folder(self,uid,document_id):
        if not re.fullmatch(r'doc-[a-f0-9]{24}',document_id):raise KeyError(document_id)
        return self.owner(uid)/document_id

    def status(self,uid,document_id):
        row=read_json(self.folder(uid,document_id)/'status.json')
        if row is None:raise KeyError(document_id)
        return row

    def report(self,uid,document_id):
        self.status(uid,document_id)
        row=read_json(self.folder(uid,document_id)/'extraction.json')
        if row is None:raise KeyError(document_id)
        return row

    def list(self,uid):
        return sorted([read_json(p) for p in self.owner(uid).glob('doc-*/status.json')],
                      key=lambda r:r.get('created_at',''),reverse=True)

    def reserve(self,uid,content,filename):
        extension=validate_source(content,filename)
        document_id='doc-'+hashlib.sha256(content).hexdigest()[:24]
        folder=self.folder(uid,document_id)
        with LOCK:
            existing=read_json(folder/'status.json')
            if existing and existing['status'] in {'queued','processing','completed','needs_review'}:
                return existing,False
            if sum(row['status'] in {'queued','processing'} for row in self.list(uid))>=5:
                raise ExtractionError('queue_full','Bạn đang có 5 tài liệu chờ xử lý. Hãy chờ các tài liệu này hoàn tất.')
            folder.mkdir(parents=True,exist_ok=True)
            source=folder/('source'+extension)
            temp=folder/'source.tmp';temp.write_bytes(content);temp.replace(source)
            safe_name=Path(filename.replace('\\','/')).stem[:180]+extension
            row={'id':document_id,'file_id':document_id,'owner':uid,'filename':safe_name,
                 'source_sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),
                 'status':'queued','processed_pages':0,'total_pages':None,'message':'Đang chờ trích xuất',
                 'created_at':datetime.now(timezone.utc).isoformat(),'extractor_version':EXTRACTOR_VERSION}
            atomic_json(folder/'status.json',row)
            return row,True

    def run(self,uid,document_id,cancel=None):
        folder=self.folder(uid,document_id)
        def update(**values):
            with LOCK:
                row=read_json(folder/'status.json');row.update(values);atomic_json(folder/'status.json',row)
        row=self.status(uid,document_id)
        update(status='processing',message='Đang mở tài liệu')
        def progress(done,total,message):
            if cancel is not None and cancel.is_set():raise ExtractionError('interrupted','Server đã dừng. Tải lại tệp để tiếp tục trích xuất.')
            update(processed_pages=done,total_pages=total,message=message)
        try:
            progress(0,None,'Đang mở tài liệu')
            content=(folder/('source'+Path(row['filename']).suffix.lower())).read_bytes()
            result=extract_document(content,row['filename'],progress)
            if cancel is not None and cancel.is_set():raise ExtractionError('interrupted','Server đã dừng. Tải lại tệp để tiếp tục trích xuất.')
            atomic_json(folder/'extraction.json',result)
            # Bank and index are serialized under one lock, preserving manual changes on re-upload.
            bank=user_folder(uid)
            with LOCK:
                index=read_json(bank/'files_index.json',{})
                if document_id not in index:
                    atomic_json(bank/(document_id+'.json'),result['questions'])
                    summary=result['summary']
                    index[document_id]={'name':Path(row['filename']).stem,'filename':row['filename'],'file_id':document_id,
                        'document_id':document_id,'count':summary['questions'],'with_answer':summary['with_answer'],
                        'uploaded_at':row['created_at'],'parse_method':'local_ocr' if summary['ocr_pages'] else 'local_text',
                        'source_sha256':row['source_sha256'],'extraction_summary':summary}
                    atomic_json(bank/'files_index.json',index)
            summary=result['summary']
            update(status='needs_review' if result['warnings'] else 'completed',message='Đã trích xuất, cần kiểm tra trước khi sử dụng',
                   summary=summary,warnings=result['warnings'][:30],finished_at=datetime.now(timezone.utc).isoformat(),
                   processed_pages=summary['pages'],total_pages=summary['pages'])
        except ExtractionError as exc:
            update(status='interrupted' if exc.code=='interrupted' else 'failed',error_code=exc.code,message=str(exc))
        except Exception:
            log.exception('Document extraction failed: %s',document_id)
            update(status='failed',error_code='processing_failed',message='Không xử lý được tài liệu. Hãy kiểm tra tệp và thử lại.')
        return self.status(uid,document_id)


class DocumentJobs:
    def __init__(self,store):
        self.store=store;self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='document-extraction')
        self.stopping=Event()
        # Interrupted work remains visible and can be retried by re-upload; never report silent success.
        for path in store.root.glob('*/doc-*/status.json'):
            row=read_json(path)
            if row['status'] in {'queued','processing'}:
                row.update(status='interrupted',message='Server đã dừng khi đang xử lý. Tải lại tệp để tiếp tục.')
                atomic_json(path,row)

    def submit(self,uid,content,filename):
        with LOCK:
            validate_source(content,filename)
            document_id='doc-'+hashlib.sha256(content).hexdigest()[:24]
            existing=read_json(self.store.folder(uid,document_id)/'status.json')
            if existing and existing['status'] in {'queued','processing','completed','needs_review'}:
                return {**existing,'already_exists':True}
            if sum(read_json(p)['status'] in {'queued','processing'} for p in self.store.root.glob('*/doc-*/status.json'))>=10:
                raise ExtractionError('queue_full','Hệ thống đang xử lý nhiều tài liệu. Vui lòng thử lại sau.')
            row,fresh=self.store.reserve(uid,content,filename)
            if self.stopping.is_set():raise ExtractionError('server_stopping','Server đang dừng. Vui lòng thử lại sau.')
            if fresh:self.executor.submit(self.store.run,uid,row['id'],self.stopping)
            return {**row,'already_exists':not fresh}

    def close(self):
        self.stopping.set()
        self.executor.shutdown(wait=True,cancel_futures=True)
        for path in self.store.root.glob('*/doc-*/status.json'):
            row=read_json(path)
            if row['status'] in {'queued','processing'}:
                row.update(status='interrupted',message='Server đã dừng khi đang xử lý. Tải lại tệp để tiếp tục.')
                atomic_json(path,row)


@lru_cache(maxsize=1)
def document_jobs():
    return DocumentJobs(DocumentStore())
