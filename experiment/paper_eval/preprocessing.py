"""Canonical returned-answer preprocessing, independent of metric/model."""
import hashlib,re
VERSION='final-answer-v1'
def prepare_answer(raw):
 raw=str(raw or '');depth=0;start=0;parts=[];blocks=0;malformed=False
 for m in re.finditer(r'</?think\b[^>]*>',raw,re.I):
  closing=m.group().startswith('</')
  if not closing:
   if depth==0:parts.append(raw[start:m.start()]);blocks+=1
   depth+=1
  elif depth:
   depth-=1
   if depth==0:start=m.end()
  else:malformed=True
 if depth:
  malformed=True # Conservative: do not guess final text inside unclosed reasoning.
 else:parts.append(raw[start:])
 return {'final_answer':''.join(parts).strip(),'answer_preprocessing_version':VERSION,'think_blocks_removed':blocks,'answer_preprocessing_status':'malformed_think' if malformed else 'ok','raw_answer_sha256':hashlib.sha256(raw.encode()).hexdigest()}
def generation_failed(answer,error=''):
 text=str(answer or '').strip()
 return bool(error or not text or text.casefold() in ['nan','none','{}','[]'] or re.match(r'(?i)\s*(?:\[ERROR\]|Error\s*:)',text) or re.search(r'未查询到相关信息|答案[:：]\s*未查询|^no relevant information',text,re.I))
