"""Deterministic MCQ extraction. Answer labels are never inferred from subject knowledge."""
from __future__ import annotations

import re
import unicodedata

QUESTION = re.compile(r"^\s*(?:C[âa]u\s*)?(\d{1,4})\s*[.:)]\s*(.*)", re.I)
CHOICE = re.compile(r"(?<!\w)([A-D])[.:)]\s+", re.I)
ANSWER = re.compile(r"^\s*(?:Đ[áa]p\s*[áa]n|ĐA|Answer)\s*[:\-]?\s*([A-D])\b", re.I)
LESSON = re.compile(r"^\s*B[àa]i\s+(\d+)\b", re.I)
KEY = re.compile(r"(?<!\w)(\d{1,4})\s*[.):-]\s*([ABCD])\b", re.I)


def norm(text):
    return " ".join(unicodedata.normalize('NFKC', text).casefold().split())


def parse_questions(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    questions, warnings = [], []
    current = None
    lesson, section, key_mode = "", "", False
    keys: dict[tuple[str, int], set[str]] = {}
    continuation = None

    def finish():
        nonlocal current, continuation
        if current is None: return
        choices = current.pop('_choices')
        marks = current.pop('_marks')
        explicit = current.pop('_explicit')
        labels = set(choices)
        if len(labels) < 2:
            warnings.append({'code':'question_without_choices','number':current['source_number'],
                             'page':current['source_page'], 'message':'Nội dung câu chưa đủ phương án; được giữ trong văn bản nguồn.'})
        else:
            current['choices'] = [{'label':label,'text':choices[label].strip()} for label in 'ABCD' if label in choices]
            issues = current['extraction_issues']
            if labels != set('ABCD'): issues.append('missing_choices')
            values = [norm(c['text']) for c in current['choices']]
            if len(set(values)) != len(values) or any(not v for v in values): issues.append('duplicate_or_empty_choices')
            candidates = explicit | marks
            current['answer'] = next(iter(candidates)) if len(candidates) == 1 and next(iter(candidates)) in labels else ''
            current['answer_origin'] = 'explicit' if current['answer'] and explicit else 'formatting' if current['answer'] else ''
            if len(candidates) > 1: issues.append('conflicting_answers')
            questions.append(current)
        current, continuation = None, None

    for block in blocks:
        raw = block['text'].strip()
        if not raw: continue
        original=raw
        raw=re.sub(r'(?<!\w)([АВСＤ])(?=[.:)]\s)',lambda m:m[1].translate(str.maketrans('АВСＤ','ABCD')),raw)
        explicit_answer=ANSWER.match(raw)
        if explicit_answer and current:
            current['_explicit'].add(explicit_answer[1].upper());continuation=None;continue
        # Teacher review forms contain unrelated metadata after each candidate.
        if re.match(r"^(?:PHẦN|BÀI|CHỦ ĐỀ|HƯỚNG DẪN|ĐÁP ÁN|MA TRẬN)\b", raw, re.I):
            finish()
            if re.match(r'^ĐÁP\s*ÁN\b|^ANSWER\s*KEY', raw, re.I): key_mode = True
            match = LESSON.match(raw)
            if match: lesson = match[1]
            if re.match(r'^PHẦN',raw,re.I):
                section = raw
                key_mode = False
            continue
        match = LESSON.match(raw)
        if key_mode and match:
            lesson = match[1]; continue
        if block.get('kind') == 'answer_key' or (key_mode and block.get('kind')!='table'):
            for number, answer in KEY.findall(raw):
                keys.setdefault((lesson,int(number)),set()).add(answer.upper())
            if block.get('kind')=='answer_key':
                for number,answer in re.findall(r'(?<!\w)(\d{1,4})([ABCD])[.)]?(?!\w)',raw):
                    keys.setdefault((lesson,int(number)),set()).add(answer)
            continue
        if block.get('kind')=='table':
            if current:current['question']+='\n'+raw
            continue
        # Lowercase a/b/c/d in true/false sections are not four-option MCQs.
        if re.search(r'đúng\s*[-–]?\s*sai|nối\s*(?:cột|sự kiện)|tự luận', section, re.I):
            continue
        if raw.startswith(('Trang ', 'thuvienhoclieu.com')) and len(raw)<80: continue
        lines = raw.splitlines()
        for text in lines:
            text=text.strip()
            if not text: continue
            ans = ANSWER.match(text)
            if ans and current:
                current['_explicit'].add(ans[1].upper()); continuation=None; continue
            header = QUESTION.match(text)
            if header:
                finish()
                current = {'id':0,'question':'','choices':[], 'answer':'','explanation':'',
                           'source_number':int(header[1]),'source_page':block.get('page'),
                           'source_block':block.get('index'), 'lesson':lesson,'section':section,
                           'review_status':'review_required','extraction_issues':[],
                           '_choices':{},'_marks':set(),'_explicit':set()}
                text = header[2]
                continuation='question'
            if current is None: continue
            if raw!=original:current['extraction_issues'].append('normalized_choice_label')
            # Mid-sentence letters such as "Hoa Kỳ A." are only split at a label with text.
            matches=list(CHOICE.finditer(text))
            if matches and (matches[0].start()==0 or header):
                prefix=text[:matches[0].start()].strip()
                if prefix: current['question']+=' '+prefix
                for i,match in enumerate(matches):
                    label=match[1].upper()
                    value=text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
                    # Answer appended to the last option is consumed separately.
                    answer_part=re.search(r'\s+(?:Đáp\s*án|ĐA|Answer)\s*[:\-]\s*([ABCD])\b',value,re.I)
                    if answer_part:
                        current['_explicit'].add(answer_part[1].upper()); value=value[:answer_part.start()].strip()
                    if label in current['_choices']:
                        current['extraction_issues'].append('repeated_choice_label')
                    current['_choices'][label]=value
                    continuation=label
                # Colored runs/spans are mapped by offsets against the whole block, not broad paragraph color.
                for marked in block.get('marked_text',[]):
                    marked=marked.strip()
                    if not marked: continue
                    for match in CHOICE.finditer(raw):
                        label=match[1].upper()
                        end=next((m.start() for m in CHOICE.finditer(raw) if m.start()>match.start()),len(raw))
                        option=raw[match.start():end]
                        if marked in option and (len(norm(marked))>=3 or re.match(r'^[ABCD][.)]',marked)):
                            current['_marks'].add(label)
            elif continuation=='question': current['question']+=' '+text
            elif continuation and continuation in 'ABCD':
                current['_choices'][continuation]+=' '+text
    finish()
    for i,q in enumerate(questions,1):
        q['id']=i; q['question']=' '.join(q['question'].split())
        mapped=keys.get((q['lesson'],q['source_number']),set())
        if mapped:
            combined=mapped | ({q['answer']} if q['answer'] else set())
            if len(combined)==1:
                q['answer']=next(iter(combined)); q['answer_origin']='answer_key'
            else:
                q['answer']=''; q['answer_origin']='';q['extraction_issues'].append('conflicting_answers')
        if not q['answer']:q['extraction_issues'].append('answer_not_found')
        q['extraction_issues']=sorted(set(q['extraction_issues']))
    return questions,warnings
