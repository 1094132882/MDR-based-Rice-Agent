"""Task-specific whole-answer accuracy, independent of generation/templates.

Missing reference facts are never treated as correct. Numeric comparisons use
Decimal, ID suffixes are preserved, and lists preserve multiplicity. Ambiguous
function paraphrases are sent to review instead of using overlap thresholds.
"""
import collections
import decimal
import html
import json
import re
import unicodedata

VERSION = 'rice-facts-v1'
GENE = r'(?<![A-Za-z0-9_])(?:LOC_Os\d+g\d+(?:\.\d+)?|Os[A-Za-z0-9_]*[Gg]\d+(?:\.\d+)?(?:\.T\d+|_\d+)?|Oglab_\d+|TMG\d+(?:\.\d+)?|R\d+C\d+g\d+)'
SV = r'(?<![A-Za-z0-9_])[A-Za-z0-9_]+_[A-Za-z0-9_]+_(?:DEL|INS|TRA|INV|OTH)\d+(?:_\d+)?'
TE = r'(?<![A-Za-z0-9_])(?:[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_(?:retrotransposon|transposon)|long_terminal_repeat|repeat_region|target_site_duplication|helitron)'
KINDS = {1:'location',2:'strand',3:'transcripts',4:'url',5:'url',6:'url',7:'mutants',8:'genes',9:'ogi',10:'ogi_genes',11:'function',12:'expression',13:'genes',14:'genes',15:'genes',16:'neighbor',17:'neighbor',18:'genes',19:'genes',20:'ogi_count',21:'svs',22:'svs',23:'svs',24:'svs',25:'longest_sv',26:'longest_sv',27:'sv_stats',28:'sv_stats',29:'te'}
ALIASES = {'缺失':'DEL','插入':'INS','易位':'TRA','倒位':'INV','其他':'OTH','deletion':'DEL','insertion':'INS','translocation':'TRA','inversion':'INV','other':'OTH'}

def normalize(text):
    text = unicodedata.normalize('NFKC', html.unescape(str(text or '')))
    return re.sub(r'[*`]', '', text)

def entities(pattern, text):
    # Ignore repeated mentions in prose for entity lists; TE annotations below
    # deliberately retain duplicate annotations from the reference.
    return sorted(set(m.group(0).casefold() for m in re.finditer(pattern, text, re.I)))

def number(value):
    return str(decimal.Decimal(str(value).replace(',', '')).normalize())

def list_payload(text):
    # Enumerated item numbers must not be parsed as decimal suffixes in IDs.
    return re.sub(r'(?<![\w.])\d+[.、]\s*(?=[A-Za-z])', ' ', text)

def count_value(text):
    patterns = [r'(?:共(?:有|存在|与)?|总数(?:为|是)?|数量(?:为|是)?)\s*(\d+)\s*(?:个|条|种)',
                r'(?<![\w.])(\d+)\s*(?:个|条|种)',
                r'(?:total(?:\s+of)?|contains?|has|includes?|there\s+are)\s*(\d+)\b',
                r'\b(\d+)\s+(?:genes?|mutants?|transcripts?|structural\s+variations?|annotations?)\b']
    vals=[]
    for pattern in patterns:
        vals.extend(int(v) for v in re.findall(pattern,text,re.I))
    return vals[0] if vals else None

def parse_facts(text, kind, target=''):
    raw=normalize(text); clean=list_payload(raw); facts={}
    genes=entities(GENE,clean)
    target=target.casefold()
    if target in genes: genes.remove(target)
    if kind=='location':
        loc=re.search(r'Chr\s*0*(\d+)\s*[:：]\s*(\d[\d,]*)\s*[-–~至]\s*(\d[\d,]*)',raw,re.I)
        if loc:facts.update(chromosome=f'chr{int(loc[1]):02d}',position=[int(loc[2].replace(',','')),int(loc[3].replace(',',''))])
        else:
            chrom=re.search(r'(?:染色体|chromosome|Chr)\s*0*(\d+)',raw,re.I)
            start=re.search(r'(?:start(?:\s+position)?|起始(?:位置)?|起点)\s*[:：为是]?\s*(\d[\d,]*)',raw,re.I)
            end=re.search(r'(?:end(?:\s+position)?|终止(?:位置)?|终点)\s*[:：为是]?\s*(\d[\d,]*)',raw,re.I)
            if chrom:facts['chromosome']=f'chr{int(chrom[1]):02d}'
            if start and end:facts['position']=[int(start[1].replace(',','')),int(end[1].replace(',',''))]
    elif kind=='strand':
        pos=bool(re.search(r'正链|正向|\b(?:positive|plus|forward|coding|sense)\s+strand\b|(?<!\w)\+(?!\w)',raw,re.I))
        neg=bool(re.search(r'负链|反向|\b(?:negative|minus|reverse|antisense)\s+strand\b|(?<!\w)-(?!\w)',raw,re.I))
        if pos!=neg:facts['strand']='+' if pos else '-'
        elif pos and neg:facts['strand']='contradictory'
    elif kind in ['transcripts','genes','ogi_genes','neighbor']:
        facts['members']=genes
        c=count_value(raw)
        if c is not None:facts['count']=c
        if kind=='ogi_genes':facts['ogi']=entities(r'OGI:\d{6,10}',raw)
    elif kind=='mutants':
        facts['members']=entities(r'22NB[A-Z]\d+',clean)
        c=count_value(raw)
        if c is not None:facts['count']=c
    elif kind in ['ogi','ogi_count']:
        facts['ogi']=entities(r'OGI:\d{6,10}',raw)
        c=count_value(raw)
        if c is not None:facts['count']=c
    elif kind=='url':
        facts['urls']=sorted(set(x.rstrip('.,。') for x in re.findall(r'https?://[^\s)\]<>"\\]+',raw)))
    elif kind=='function':
        funcs=re.search(r'(?:注释是|功能(?:是|为)|annotation\s*(?:is|:)|function\s*(?:is|:))\s*(.+)',raw,re.I)
        if funcs:facts['function']=funcs[1].strip().rstrip('。.')
        facts['accessions']=entities(r'(?:UniProtKB/Swiss-Prot:)\s*[A-Z0-9]+',raw)
    elif kind=='expression':
        for label,pattern in [('leaf',r'叶|leaf'),('root',r'根|root'),('panicle',r'幼穗|young\s+ear|panicle')]:
            nums=re.findall(r'(?:'+pattern+r')[^,，。;；\n]{0,45}?(?:为|是|:|：|\bis\b|\bof\b)\s*([0-9]+(?:\.[0-9]+)?)',raw,re.I)
            if nums:facts[label]=number(nums[0])
            elif re.search(r'(?:'+pattern+r')[^,，。;；\n]{0,25}(?:暂无|无数据|not\s+available|unavailable|no\s+data)',raw,re.I):facts[label]='unavailable'
    elif kind in ['svs','longest_sv']:
        facts['svs']=entities(SV,clean)
        c=count_value(raw)
        if c is not None:facts['count']=c
        if kind=='longest_sv':
            m=re.search(r'(?:长度(?:为|是)?|length(?:\s+of|\s+is)?|SVLEN)\s*[:：=]?\s*(\d[\d,]*)',raw,re.I)
            if m:facts['length']=int(m[1].replace(',',''))
    elif kind=='sv_stats':
        stats={}
        types=r'DEL|INS|TRA|INV|OTH|缺失|插入|易位|倒位|其他|deletion|insertion|translocation|inversion|other'
        for n,t in re.findall(r'(\d+)\s*个\s*(?:类型为)?\s*('+types+r')',raw,re.I):stats[ALIASES.get(t.lower(),t.upper())]=int(n)
        for t,n in re.findall(r'\b(DEL|INS|TRA|INV|OTH)\b\s*(?:[:：=]|\bis\b|类型(?:数量)?为)\s*(\d+)',raw,re.I):stats[t.upper()]=int(n)
        for n,t in re.findall(r'\b(\d+)\s+('+types+r')\b',raw,re.I):stats[ALIASES.get(t.lower(),t.upper())]=int(n)
        if stats:facts['counts_by_type']=stats
    elif kind=='te':
        # Named numbered annotations form a multiset, not a set.
        facts['annotations']=sorted(m.group(0).casefold() for m in re.finditer(TE,clean,re.I))
    return facts

REQUIRED={'location':['chromosome','position'],'strand':['strand'],'transcripts':['members'],'genes':['members'],'ogi_genes':['ogi','members'],'neighbor':['members'],'mutants':['members'],'ogi':['ogi'],'ogi_count':['ogi','count'],'url':['urls'],'function':['function'],'expression':['leaf','root','panicle'],'svs':['svs'],'longest_sv':['svs','length'],'sv_stats':['counts_by_type'],'te':['annotations']}

def make_reference(row):
    split=row['split'];kind=KINDS[int(split.removeprefix('type'))]
    anchors=entities(GENE,row['question']);target=anchors[0] if anchors else ''
    facts=parse_facts(row['ground_truth'],kind,target)
    missing=[k for k in REQUIRED[kind] if facts.get(k) is None or facts.get(k)==[] or facts.get(k)=={} or facts.get(k)=='']
    issues=[]
    if missing:issues.append('missing reference fields: '+','.join(missing))
    if kind in ['genes','mutants','transcripts','ogi_genes','svs'] and 'count' in facts:
        members=facts.get('members',facts.get('svs',[]))
        if len(members)!=facts['count']:issues.append('reference count/list mismatch')
    if kind=='neighbor' and len(facts.get('members',[]))!=1:issues.append('nearest answer must contain one neighbor')
    if kind=='longest_sv' and len(facts.get('svs',[]))!=1:issues.append('longest answer must contain one SV')
    return {'kind':kind,'target':target,'facts':facts,'reference_status':'review' if issues else 'valid','reference_issues':issues}

def score_accuracy(reference, answer, error=''):
    if reference['reference_status']!='valid':return {'accuracy':None,'accuracy_status':'reference_review','accuracy_reason':'; '.join(reference['reference_issues'])}
    text=normalize(answer)
    if error or not text.strip() or text.strip().lower() in ['nan','none','{}','[]'] or re.match(r'(?i)\s*(?:\[ERROR\]|Error\s*:)',text) or re.search(r'未查询到相关信息|答案[:：]\s*未查询|^no relevant information',text,re.I):
        return {'accuracy':0,'accuracy_status':'incorrect','accuracy_reason':'generation failed or empty answer'}
    kind=reference['kind'];expected=reference['facts'];actual=parse_facts(text,kind,reference['target'])
    mismatches=[]
    for field in REQUIRED[kind]:
        got=actual.get(field);want=expected[field]
        if kind=='function':
            # Only exact reference annotation text is automatically accepted.
            # Paraphrases require explicit human adjudication; BERTScore is separate.
            core=re.sub(r'\s*\[UniProtKB/Swiss-Prot:[^\]]+\]', '', want)
            if actual.get('accessions') and actual['accessions']!=expected['accessions']:
                return {'accuracy':0,'accuracy_status':'incorrect','accuracy_reason':'mismatched function accession'}
            compact=re.sub(r'\s+','',text).casefold()
            annotation=re.sub(r'\s+','',core).casefold()
            position=compact.find(annotation)
            if position<0:
                return {'accuracy':None,'accuracy_status':'prediction_review','accuracy_reason':'function description needs semantic adjudication'}
            if re.search(r'(?:不是|并非|不属于|not)$',compact[max(0,position-8):position]):
                mismatches.append('negated function description')
        elif got!=want:mismatches.append(field)
    # If a count is explicitly stated it must agree, even when an exact list
    # already identifies all members. A count alone never substitutes for a list.
    if 'count' in actual and 'count' in expected and actual['count']!=expected['count']:mismatches.append('count')
    if kind=='location' and reference['target']:
        mentioned=entities(GENE,text)
        if mentioned and mentioned!=[reference['target']]:mismatches.append('answer gene identity')
    return {'accuracy':0 if mismatches else 1,'accuracy_status':'incorrect' if mismatches else 'correct','accuracy_reason':'missing or mismatched: '+','.join(mismatches) if mismatches else 'all required reference facts match'}
