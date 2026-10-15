"""Versioned, deterministic structured fact extraction and joint scoring.

This module does not call models, select runs, edit Gold, or invoke legacy scores.
Unsupported language is a review item, not an automatically accepted assertion.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal
import hashlib
import html
import json
import re
import unicodedata
from .preprocessing import prepare_answer, generation_failed

VERSION = 'rice-structured-facts-v3.0'
GENE = r'(?<![A-Za-z0-9_])(?:LOC_Os\d+g\d+|Os[A-Za-z0-9_]*[Gg]\d+|Oglab_\d+|TMG\d+|R\d+C\d+g\d+)(?:\.\d+)?(?:\.T\d+|_\d+)?(?![A-Za-z0-9_])'
SV = r'(?<![A-Za-z0-9_])[A-Za-z0-9_]+_[A-Za-z0-9_]+_(?:DEL|INS|TRA|INV|OTH)\d+(?:_\d+)?(?![A-Za-z0-9_])'
MUTANT = r'(?<![A-Za-z0-9_])22NB[A-Z]\d+(?![A-Za-z0-9_])'
OGI = r'OGI:\d{8}(?!\d)'
TE = r'(?<![A-Za-z0-9_])(?:[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_(?:retrotransposon|transposon)|long_terminal_repeat|repeat_region|target_site_duplication|helitron)(?![A-Za-z0-9_])'
URL = r'https?://[^\s)\]<>"\\]+'
NEG = r'不是|并非|不包含|不包括|不存在|不属于|不关联|未关联|没有|\bnot\b|\bnever\b'
ALIASES = {'缺失':'DEL','插入':'INS','易位':'TRA','倒位':'INV','其他':'OTH','deletion':'DEL','insertion':'INS','translocation':'TRA','inversion':'INV','other':'OTH'}
class ParseReview(ValueError):
    pass


LIST_TYPES = {3,7,8,10,13,14,15,16,17,18,19,21,22,23,24,29}
MEMBER_RELATIONS = {'has_transcript','associated_mutant','associated_gene','has_gene','contains_gene','neighbor','associated_sv','contains_sv','te_annotation_category'}
TYPE_NAMES = ['coordinates','strand','transcripts','DNA_URL','CDS_URL','protein_URL','mutants','mutant_genes','gene_OGI','OGI_genes','function','expression','region_genes','upstream_range','downstream_range','nearest_upstream','nearest_downstream','nearest_N_upstream','nearest_N_downstream','OGI_count','gene_SV','filtered_gene_SV','region_SV','filtered_region_SV','longest_SV','filtered_longest_SV','SV_counts','filtered_SV_count','TE_categories']


def digest(text):
    return hashlib.sha256(str(text).encode()).hexdigest()


def normalize(text):
    return unicodedata.normalize('NFKC', html.unescape(str(text or ''))).replace('`','').replace('*','')


def clean_list(text):
    return re.sub(r'(?<![\w.])\d+[.、]\s*(?=[A-Za-z])', ' ', text)


def matches(pattern, text):
    return list(re.finditer(pattern, text, re.I))


def numeric(text):
    return str(Decimal(str(text).replace(',','')).normalize())


def ids(pattern, text):
    return sorted(set(re.sub(r'\s+','',m.group()).casefold() for m in matches(pattern, clean_list(text))))


def quantity(text):
    patterns = [r'(?:共(?:有|存在|与)?|总数(?:为|是)?|数量(?:为|是)?)\s*(\d+)\s*(?:个|条|种)',
                r'(?<![\w.])(\d+)\s*(?:个|条|种)',r'\b(?:total(?:\s+of)?|there\s+are)\s*(\d+)',
                r'\b(\d+)\s+(?:genes?|mutants?|transcripts?|variants?|annotations?)\b']
    return sorted(set(int(n) for p in patterns for n in re.findall(p,text,re.I)))


@dataclass(frozen=True)
class Fact:
    subject: str
    relation: str
    object: str
    qualifiers: tuple = ()
    polarity: str = 'positive'

    @classmethod
    def make(cls, subject, relation, obj, qualifiers=None, polarity='positive'):
        return cls(str(subject), relation, str(obj), tuple(sorted((qualifiers or {}).items())), polarity)

    def record(self):
        return {**asdict(self), 'qualifiers': dict(self.qualifiers)}


def record_fact(record):
    return Fact.make(record['subject'],record['relation'],record['object'],record['qualifiers'],record['polarity'])


def region(text):
    p = r'(?:Chr|chromosome\s*)0*(\d+)\s*[:：]\s*(\d[\d,]*(?:\.\d+)?)\s*(kb|mb|bp)?\s*[-–~至]\s*(\d[\d,]*(?:\.\d+)?)\s*(kb|mb|bp)?'
    m = re.search(p,text,re.I)
    if not m:
        return None
    factors = {'kb':1000,'mb':1000000,'bp':1,'':1}
    u1=(m[3] or m[5] or '').lower();u2=(m[5] or m[3] or '').lower()
    start=Decimal(m[2].replace(',',''))*factors[u1];end=Decimal(m[4].replace(',',''))*factors[u2]
    if start!=start.to_integral_value() or end!=end.to_integral_value():
        raise ParseReview('fractional_base_coordinate_requires_review')
    before=text[:m.start()]
    g=re.search(r'([A-Za-z0-9_]+)(?:的)?\s*$',before)
    result={'chromosome':f'Chr{int(m[1]):02d}','start_bp':str(int(start)),'end_bp':str(int(end))}
    if g:result['genome']=g[1].casefold()
    return result


def subject_for(text, profile):
    """Only explicit grammatical subjects override the question context."""
    patterns = [r'(?:基因|gene\s+)\s*('+GENE+r')',
                r'('+GENE+r')\s*(?:的|在|位于|属于|不是|并非|上游|下游|\bis\b|\bhas\b)',
                r'('+MUTANT+r')\s*(?:共|关联|与|\bis\b|\bhas\b)',
                r'('+SV+r')\s*(?:关联|的|\bhas\b|\bis\b)',
                r'('+OGI+r')\s*(?:共|包含|不包含|包括|不包括|\bcontains?\b)']
    found=[]
    for p in patterns:
        found += [(m.start(1),m[1].casefold()) for m in matches(p,text)]
    return min(found)[1] if found else profile['subject']


def polarity(text, position):
    before=text[:position]
    # A conjunction/list separator keeps a governing negative across all members.
    negative=list(re.finditer(NEG,before,re.I))
    affirmative=list(re.finditer(r'而是|但是|但(?:是)?(?:包括|包含|位于|在)|\bbut\s+(?:is|includes?|contains?)\b',before,re.I))
    if not negative:return 'positive'
    return 'positive' if affirmative and affirmative[-1].start()>negative[-1].start() else 'negative'


def attribute_polarity(text, position):
    return polarity(re.split(r'[,，]',text[:position])[-1],len(re.split(r'[,，]',text[:position])[-1]))


def sv_filter(text):
    types=r'DEL|INS|TRA|INV|OTH|缺失|插入|易位|倒位|其他|deletion|insertion|translocation|inversion|other'
    m=re.search(r'(?:类型为|类型是)('+types+r')|('+types+r')类型',text,re.I)
    if not m:return None
    v=m[1] or m[2];return ALIASES.get(v.lower(),v.upper())


def clauses(text):
    text=re.sub(r'[,，]\s*(?=(?:不是|并非|not\b))','；',text,flags=re.I)
    text=re.sub(r'[,，]\s*(?=(?:基因|gene\s+)?'+GENE+r'\s*(?:的|在|位于|属于|\bis\b|\bhas\b))','；',text,flags=re.I)
    return [s.strip() for s in re.split(r'[。；;\n!?！？]+',text) if s.strip()]


def presentation_clause(text):
    clean=text
    for p in [GENE,SV,OGI,MUTANT]:clean=re.sub(p,'',clean,flags=re.I)
    clean=re.sub(r'查询结果|位置信息|表达信息|功能注释|基因|结构变异|转录本|成员|类别|结果|如下|答案|信息|here are|results|answer|gene|annotations', '', clean, flags=re.I)
    return not clean.strip(' ,，:：-[]()（）')


def profile_context(row, sample_id=None):
    gold=normalize(row['ground_truth']);q=row['question'];t=int(row.get('split',row.get('type','')).replace('type',''))
    gs=ids(GENE,gold); os=ids(OGI,gold);svs=ids(SV,gold)
    head=re.search(r'基因\s*('+GENE+r')',gold,re.I)
    subject=head[1].casefold() if head else ('question' if not gs else matches(GENE,clean_list(gold))[0].group().casefold())
    if t==8:subject=ids(MUTANT,gold)[0]
    if t==10:subject=os[0]
    if t==29:subject=svs[0]
    context=region(gold) if t in {13,23,24,25,26,27,28} else None
    if context:subject='region:'+json.dumps(context,sort_keys=True)
    qualifiers={}
    if t in {14,15,16,17,18,19}:
        qualifiers['direction']='upstream' if t in {14,16,18} else 'downstream'
        if t in {14,15}:
            m=re.search(r'(\d+(?:\.\d+)?)\s*(kb|mb|bp)',gold,re.I)
            if m:qualifiers['range_bp']=str(int(Decimal(m[1])*{'kb':1000,'mb':1000000,'bp':1}[m[2].lower()]))
    if sample_id is not None and int(sample_id)==95:qualifiers.pop('direction',None)
    if t in {22,24,26} and sv_filter(gold):qualifiers['sv_type_filter']=sv_filter(gold)
    annotation=None
    if t==11:
        m=re.search(r'注释是(.+?)(?:\s*\[UniProtKB/Swiss-Prot:[^\]]+\])?\s*[。.]?$',gold,re.I)
        annotation=re.sub(r'\s*\[UniProtKB/Swiss-Prot:[^\]]+\]','',m[1]).strip().rstrip('。.') if m else None
    return {'sample_id':sample_id,'type':t,'mode':TYPE_NAMES[t-1],'question':q,'ground_truth':row['ground_truth'],
            'question_sha256':digest(q),'gold_sha256':digest(row['ground_truth']),
            'subject':subject,'region':context,'qualifiers':qualifiers,'annotation':annotation,
            'annotation_accessions':ids(r'UniProtKB/Swiss-Prot:\s*[A-Z0-9]+',gold),
            'stats_complete':t==27 and len(set(re.findall(r'\b(?:DEL|INS|TRA|INV|OTH)\b',gold)))==5,
            'direction_ignored':sample_id is not None and int(sample_id)==95,
            'contract_version':'type-and-gold-fields-author-approved-v1'}


def selection_subject(profile, observed_subject=None, qualifiers=None):
    return 'selected_max:'+json.dumps({'region':observed_subject or profile['subject'],'filter':qualifiers if qualifiers is not None else profile['qualifiers']},sort_keys=True)


def extract(profile, final_answer, gold=False):
    """Return asserted facts and unresolved spans; no first-value overwrite."""
    if not gold:
        from .answer_formats_v3 import adapt
        try:final_answer,_=adapt(profile,normalize(final_answer))
        except ValueError as exc:raise ParseReview(str(exc))
    t=profile['type'];text=clean_list(normalize(final_answer));facts=set();reviews=[];counts=[];recognized=[False]
    def add(sub,rel,obj,q=None,pol='positive'):
        facts.add(Fact.make(sub,rel,obj,q,pol));recognized[0]=True
    if re.search(r'不过.*真正位置|更正(?:为|:|：)|纠正(?:为|:|：)|前述.*错误|correction|actually',text,re.I):
        reviews.append('retraction_scope: determine which assertions remain active')
    for clause in clauses(text):
        if t not in {4,5,6} and re.match(r'^(?:建议|推荐|您可以|你可以|请|需要(?:通过|查询|获取)|应当|访问|输入|搜索|查询方法|操作步骤)',clause):continue
        if t in LIST_TYPES and re.search(r'可能是.*(?:或|取决于)|\bmight be.*\bor\b',clause,re.I):continue
        if t==2 and re.search(r'正链.*(?:或|或者|\bor\b).*负链|负链.*(?:或|或者|\bor\b).*正链',clause,re.I):continue
        if re.search(r'引用|原问题|用户问|问题是|假设|如果|例如|举例|\bsuppose\b|\bif\b|\bfor example\b',clause,re.I):
            continue
        if re.search(r'未返回基因列表|未返回.*列表|无法直接提供|无法获取|无法回答|不知道|不确定|不能确定|\b(?:cannot answer|do not know|unsure)\b',clause,re.I):
            continue
        if re.search(r'是否|吗$|\bwhether\b',clause,re.I):
            continue
        recognized[0]=False;sub=subject_for(clause,profile);qual=dict(profile['qualifiers'])
        if t in {22,24,26} and sv_filter(clause):qual['sv_type_filter']=sv_filter(clause)
        if not profile['direction_ignored'] and t in {14,15,16,17,18,19}:
            ds=re.findall(r'上游|下游|\bupstream\b|\bdownstream\b',clause,re.I)
            if ds:
                directions={'upstream' if d.lower() in ['上游','upstream'] else 'downstream' for d in ds}
                if len(directions)==1:qual['direction']=directions.pop()
                elif set(ids(GENE,clause))-{sub,profile['subject']}:reviews.append('ambiguous_direction: '+clause)
            rng=re.search(r'(\d+(?:\.\d+)?)\s*(kb|mb|bp)',clause,re.I)
            if rng:qual['range_bp']=str(int(Decimal(rng[1])*{'kb':1000,'mb':1000000,'bp':1}[rng[2].lower()]))
        if profile['region']:
            genome_claim=re.search(r'(?:查询基因组|query\s+genome)\s*[:：为是]*\s*([A-Za-z0-9_]+)',clause,re.I)
            if genome_claim:
                sub='region:'+json.dumps({**profile['region'],'genome':genome_claim[1].casefold()},sort_keys=True)
            observed=region(clause)
            if observed:
                # Elided genome inherits only the question context; explicit scope is kept.
                scope={**profile['region'],**observed};sub='region:'+json.dumps(scope,sort_keys=True)
        if t==1:
            r=region(clause)
            if r:
                pos=re.search(r'(?:Chr|chromosome)',clause,re.I).start();pol=polarity(clause,pos)
                for k in ['chromosome','start_bp','end_bp']:add(sub,k,r[k],pol=pol)
            else:
                for rel,p in [('chromosome',r'(?:Chr|染色体|chromosome)\s*0*(\d+)'),('start_bp',r'(?:起始(?:位置)?|起点|start(?:\s+position)?)\s*(?:为|是|:|：|is)?\s*(\d[\d,]*)'),('end_bp',r'(?:终止(?:位置)?|终点|end(?:\s+position)?)\s*(?:为|是|:|：|is)?\s*(\d[\d,]*)')]:
                    for m in matches(p,clause):add(sub,rel,f'Chr{int(m[1]):02d}' if rel=='chromosome' else str(int(m[1].replace(',',''))),pol=polarity(clause,m.start()))
        elif t==2:
            for m in matches(r'正链|负链|正向|负向|(?<!\w)[+-](?!\w)|\b(?:positive|plus|forward|negative|minus|reverse)\s+strand\b',clause):
                val='+' if m.group().lower() in ['正链','正向','+','positive strand','plus strand','forward strand'] else '-'
                if polarity(clause,m.start())=='negative':val='-' if val=='+' else '+'
                add(sub,'strand',val)
        elif t in {4,5,6}:
            for m in matches(URL,clause):add(sub,'sequence_resource',m.group().rstrip('.,。'),{'sequence_kind':{4:'DNA',5:'CDS',6:'protein'}[t]},polarity(clause,m.start()))
        elif t==9:
            for m in matches(OGI,clause):add(sub,'member_of_ogi',m.group().casefold(),pol=polarity(clause,m.start()))
        elif t==11:
            ann=profile['annotation']
            if not ann:reviews.append('reference_function_missing');continue
            compact=lambda s:re.sub(r'\s+','',s).casefold()
            if compact(ann) in compact(clause):
                pos=clause.casefold().find(ann.casefold());pos=max(pos,0)
                acc=ids(r'UniProtKB/Swiss-Prot:\s*[A-Z0-9]+',clause)
                aq={} if not acc or acc==profile['annotation_accessions'] else {'conflicting_accession':','.join(acc)}
                add(sub,'functional_annotation',ann.casefold(),aq,polarity(clause,pos))
            elif re.search(r'功能|注释|function|annotation',clause,re.I):
                acc=ids(r'UniProtKB/Swiss-Prot:\s*[A-Z0-9]+',clause)
                raw_ann=re.search(r'(?:注释(?:是|为)|功能(?:是|为)|annotation\s*(?:is|:)|function\s*(?:is|:))\s*(.+)',clause,re.I)
                if raw_ann and acc and acc!=profile['annotation_accessions']:
                    add(sub,'functional_annotation',raw_ann[1].strip().casefold(),{'conflicting_accession':','.join(acc)},polarity(clause,raw_ann.start(1)))
                else:reviews.append('function_paraphrase: '+clause)
        elif t==12:
            for tissue,p in [('leaf',r'叶|\bleaf\b|\bleaves\b'),('root',r'根|\broot\b|\broots\b'),('young_ear',r'幼穗|\byoung\s+ear\b|\bpanicle\b')]:
                expression=r'(?:'+p+r')[^,，;；。\n]{0,35}?(?:为|是|:|：|\bis\b|\bof\b)\s*(\d+(?:\.\d+)?)'
                for m in matches(expression,clause):add(sub,'expression',numeric(m[1]),{'tissue':tissue},attribute_polarity(clause,m.start(1)))
                missing=r'(?:'+p+r')[^,，;；。\n]{0,25}(?:暂无|无数据|没有数据|\bunavailable\b|\bnot available\b|\bno data\b)'
                for m in matches(missing,clause):add(sub,'expression','unavailable',{'tissue':tissue})
            if re.search(r'茎|\bstem\b|幼苗|\bseedling\b',clause,re.I):reviews.append('unverified_tissue_or_stage_claim: '+clause)
        elif t==20:
            os=matches(OGI,clause)
            for m in os:add(sub,'member_of_ogi',m.group().casefold(),pol=polarity(clause,m.start()))
            for n in quantity(clause):
                ogis=ids(OGI,clause) or ids(OGI,profile['ground_truth'])
                if len(ogis)!=1:reviews.append('ambiguous_count_group: '+clause)
                else:add(sub,'ogi_member_count',str(n),{'ogi':ogis[0]},polarity(clause,len(clause)))
        elif t in {27,28}:
            if not gold:
                for unknown in re.findall(r'\b([A-Z]{3})\b\s*(?:类型|[:：=]\s*\d)',clause):
                    if unknown not in {'DEL','INS','TRA','INV','OTH'}:reviews.append('unsupported_SV_category: '+unknown)
            types=r'DEL|INS|TRA|INV|OTH|缺失|插入|易位|倒位|其他|deletion|insertion|translocation|inversion|other'
            ps=[r'(\d+)\s*个\s*(?:类型为)?\s*('+types+r')',r'\b('+types+r')\b\s*(?:[:：=]|\bis\b|类型(?:数量)?为)\s*(\d+)']
            for i,p in enumerate(ps):
                for m in matches(p,clause):
                    n,v=(m[1],m[2]) if i==0 else (m[2],m[1]);v=ALIASES.get(v.lower(),v.upper())
                    if not gold and t==27 and not profile['stats_complete'] and v not in profile.get('known_sv_types',[]):reviews.append('unverified_SV_type_count: '+v+'='+n)
                    else:add(sub,'sv_count',str(int(n)),{'sv_type':v},polarity(clause,m.start()))
            if not gold and t==27 and not profile['stats_complete'] and re.search(r'(?:共|有|存在|全部|只有).*\d+\s*(?:种|类)|all.*four|only.*four',clause,re.I):reviews.append('unverified_statistics_completeness')
        elif t in LIST_TYPES or t in {25,26}:
            pattern=MUTANT if t==7 else SV if 21<=t<=26 else TE if t==29 else GENE
            member_matches=matches(pattern,clause)
            wrong_relation=bool(re.search(r'(?<![A-Za-z])(?:RBH|SBH)(?![A-Za-z])|\bhomologous\s+to\b',clause,re.I))
            if wrong_relation and not gold:reviews.append('unverified_or_wrong_gene_relation: '+clause)
            rel={3:'has_transcript',7:'associated_mutant',8:'associated_gene',10:'has_gene',13:'contains_gene',14:'neighbor',15:'neighbor',16:'neighbor',17:'neighbor',18:'neighbor',19:'neighbor',21:'associated_sv',22:'associated_sv',23:'contains_sv',24:'contains_sv',25:'selected_max_sv',26:'selected_max_sv',29:'te_annotation_category'}[t]
            if wrong_relation and not gold:rel='asserted_homology'
            if t==10:
                os=ids(OGI,clause)
                if len(os)==1:sub=os[0]
                elif len(os)>1:reviews.append('multiple_OGI_subjects: '+clause)
            for m in member_matches:
                obj=m.group().casefold()
                if obj==sub:continue
                add(sub,rel,obj,qual,polarity(clause,m.start()))
            if t in {23,24}:
                sv_mentions=matches(SV,clause)
                for i,sv_match in enumerate(sv_mentions):
                    block=clause[sv_match.end():sv_mentions[i+1].start() if i+1<len(sv_mentions) else len(clause)]
                    for attr,pattern_attr in [('query_genome',r'(?:查询基因组|query\s+genome)\s*(?:为|不是|并非|是|:|：|is)?\s*([A-Za-z0-9_]+)'),('reference_genome',r'(?:参考基因组|reference\s+genome)\s*(?:为|不是|并非|是|:|：|is)?\s*([A-Za-z0-9_]+)')]:
                        for a in matches(pattern_attr,block):add(sv_match.group().casefold(),attr,a[1].casefold(),pol=attribute_polarity(block,a.start(1)))
            if t in {21,22,23,24,25,26}:
                sv_mentions=matches(SV,clause)
                for i,sv_match in enumerate(sv_mentions):
                    block=clause[sv_match.end():sv_mentions[i+1].start() if i+1<len(sv_mentions) else len(clause)]
                    encoded=re.search(r'_(DEL|INS|TRA|INV|OTH)\d+',sv_match.group(),re.I)[1].upper()
                    for declared in matches(r'类型\s*(?:为|是|:|：)?\s*(DEL|INS|TRA|INV|OTH)',block):
                        if declared[1].upper()!=encoded:add(sv_match.group().casefold(),'conflicting_sv_type',declared[1].upper())
            if t==29:
                known={m.group().casefold() for m in matches(TE,clause)}|set(ids(SV,clause))
                for token in matches(r'\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b',clause):
                    if token.group().casefold() not in known:add(sub,'te_annotation_category',token.group().casefold(),qual,polarity(clause,token.start()))
            # SV attributes are subject-bound, never inferred from arbitrary name components.
            if t in {25,26}:
                objs=ids(SV,clause)
                if len(objs)==1:
                    obj=objs[0]
                    for rel_attr,p in [('length_bp',r'(?:长度(?:为|是)?|length(?:\s+is|\s+of)?)\s*[:：=]?\s*(\d[\d,]*)'),('query_genome',r'(?:查询基因组|query\s+genome)\s*(?:为|不是|并非|是|:|：|is)?\s*([A-Za-z0-9_]+)'),('reference_genome',r'(?:参考基因组|reference\s+genome)\s*(?:为|不是|并非|是|:|：|is)?\s*([A-Za-z0-9_]+)')]:
                        for m in matches(p,clause):add(obj,rel_attr,str(int(m[1].replace(',',''))) if rel_attr=='length_bp' else m[1].casefold(),pol=attribute_polarity(clause,m.start(1)))
                elif not objs and re.search(r'长度|length|参考基因组|查询基因组',clause,re.I):
                    obj=selection_subject(profile,sub,qual)
                    for rel_attr,pattern_attr in [('length_bp',r'(?:长度(?:为|是)?|length(?:\s+is|\s+of)?)\s*[:：=]?\s*(\d[\d,]*)'),('query_genome',r'(?:查询基因组|query\s+genome)\s*(?:为|是|:|：|is)\s*([A-Za-z0-9_]+)'),('reference_genome',r'(?:参考基因组|reference\s+genome)\s*(?:为|是|:|：|is)\s*([A-Za-z0-9_]+)')]:
                        for a in matches(pattern_attr,clause):add(obj,rel_attr,str(int(a[1].replace(',',''))) if rel_attr=='length_bp' else a[1].casefold(),pol=attribute_polarity(clause,a.start(1)))
                elif objs and re.search(r'长度|length|参考基因组|查询基因组',clause,re.I):reviews.append('ambiguous_SV_attribute_subject: '+clause)
            qs=quantity(clause)
            counts.extend((n,clause) for n in qs)
            if qs:recognized[0]=True
        if not gold and t not in LIST_TYPES|{20,27,28} and quantity(clause):reviews.append('unverified_noncore_quantity: '+clause)
        if not gold and t!=11 and re.search(r'功能|注释是|\bfunction\b|\bannotation\b',clause,re.I):reviews.append('unverified_noncore_function_claim: '+clause)
        if not gold and t==11 and len(re.findall(r'功能|注释是|\bfunction\b|\bannotation\b',clause,re.I))>1:reviews.append('multiple_function_assertions: '+clause)
        # No automatic acceptance of biological mechanisms or newly asserted relations.
        if not gold and re.search(r'已被证明|控制|抗旱|耐盐|调控|\bcontrols?\b|\bproven\b|\bregulates?\b',clause,re.I):reviews.append('unverified_extra_claim: '+clause)
        if not gold and not recognized[0] and not presentation_clause(clause):
            reviews.append('unparsed_assertion: '+clause)
    if not gold and t in LIST_TYPES:
        known=profile.get('list_count')
        positive={f.object for f in facts if f.polarity=='positive' and f.relation in {'has_transcript','associated_mutant','associated_gene','has_gene','contains_gene','neighbor','associated_sv','contains_sv','te_annotation_category'}}
        for n,clause in counts:
            if known is not None and n!=known:
                complete_claim=bool(re.search(r'共|总数|全部|完整|\btotal\b|\ball\b',clause,re.I))
                if not (complete_claim and n==len(positive) and positive):
                    add(profile['subject'],'conflicting_count',n)
    if not gold and not facts and text.strip() and not reviews and not re.search(r'无法|不知道|不确定|未查询|没有相关|no relevant|cannot|unknown|假设|如果|例如|是否',text,re.I):
        reviews.append('unsupported_answer_format: '+text)
    return facts,sorted(set(reviews))


def build_profile(row, sample_id=None):
    p=profile_context(row,sample_id)
    facts,issues=extract(p,row['ground_truth'],gold=True)
    if p['type'] in LIST_TYPES:
        p['member_set_complete']=True
        p['list_count']=len({f.object for f in facts if f.relation in {'has_transcript','associated_mutant','associated_gene','has_gene','contains_gene','neighbor','associated_sv','contains_sv','te_annotation_category'}})
        declared=quantity(row['ground_truth'])
        if declared and any(n!=p['list_count'] for n in declared):issues.append('Gold count/list mismatch')
    p['known_sv_types']=sorted({dict(f.qualifiers)['sv_type'] for f in facts if f.relation=='sv_count'})
    p['required_facts']=[f.record() for f in sorted(facts,key=repr)]
    p['profile_status']='valid' if facts and not issues else 'reference_review'
    p['profile_issues']=issues or ([] if facts else ['no reference facts extracted'])
    p['profile_sha256']=digest(json.dumps(p,ensure_ascii=False,sort_keys=True))
    return p


def validate_profile(profile):
    value={k:v for k,v in profile.items() if k!='profile_sha256'}
    if digest(json.dumps(value,ensure_ascii=False,sort_keys=True))!=profile['profile_sha256']:
        raise ValueError('Frozen profile was modified')
    if profile['question_sha256']!=digest(profile['question']) or profile['gold_sha256']!=digest(profile['ground_truth']):
        raise ValueError('Frozen question/Gold was modified')


def partition_reviews(profile,reviews,actual):
    """Unknown background is audited; ambiguity in task assertions still blocks."""
    kept=[];audit=[];t=profile['type']
    core_markers={1:r'(?:Chr\d|起始|终止|起点|终点|start|end).{0,20}\d',2:r'正链|负链|strand\s*[:=]\s*(?:positive|negative|[+-])',
                  11:r'注释(?:是|为)|功能(?:是|为)|annotation\s*(?:is|:)|function\s*(?:is|:)',
                  12:r'(?:叶|根|幼穗|leaf|root|panicle).{0,35}(?:表达量|value|is).{0,8}\d'}
    always={'retraction_scope','ambiguous_direction','multiple_OGI_subjects','unverified_SV_type_count',
            'unverified_statistics_completeness','unsupported_SV_category','ambiguous_count_group'}
    for reason in reviews:
        kind,_,span=reason.partition(':')
        if kind=='unverified_statistics_completeness' and not any(f.relation=='sv_count' for f in actual):audit.append(reason);continue
        if kind in always:kept.append(reason);continue
        if kind=='ambiguous_SV_attribute_subject':
            concrete=bool(re.search(r'(?:长度|length)\s*(?:为|是|:|：|is)?\s*\d|(?:查询基因组|参考基因组|reference genome|query genome)\s*(?:为|是|:|：|is)\s*[A-Za-z0-9_]+',span,re.I))
            if concrete and not re.search(r'需要|例如|方法|建议|定义|格式|通常|可能|文件|指定|选择',span):kept.append(reason)
            else:audit.append(reason)
            continue
        if kind=='function_paraphrase':
            # An explicit alternative annotation is still unresolved, not discarded.
            if re.search(core_markers[11],span,re.I):kept.append(reason)
            else:audit.append(reason)
            continue
        if kind=='unverified_or_wrong_gene_relation':kept.append(reason);continue
        if kind=='unparsed_assertion':
            # Missing parser coverage for a concrete task value is not an FN guess.
            concrete=bool(re.search(core_markers.get(t,r'(?!)'),span,re.I))
            navigation=bool(re.search(r'查看|点击|访问|搜索|请|建议|需要|方法|输入|通常|例如|定义|属性|写出|页面|格式|比值|阶段',span))
            if concrete and not navigation:kept.append(reason)
            else:audit.append(reason)
            continue
        # Background functionality, prose, advice and unknown unrelated fields are
        # outside the predefined task facts, and never count as positive evidence.
        audit.append(reason)
    return sorted(set(kept)),sorted(set(audit))


def score(profile, answer, error=''):
    """One matching result, two independently defined metrics. No Accuracy->F1 mapping."""
    validate_profile(profile)
    prepared=prepare_answer(answer)
    if prepared['answer_preprocessing_status']!='ok':
        return {'accuracy':None,'structured_fact_f1':None,'status':'preprocessing_review','review_reasons':['malformed_think']}
    if profile['profile_status']!='valid':
        return {'accuracy':None,'structured_fact_f1':None,'status':'reference_review','review_reasons':profile['profile_issues']}
    text=prepared['final_answer'];expected={record_fact(f) for f in profile['required_facts']}
    try:
        actual,reviews=(set(),[]) if generation_failed(text,error) else extract(profile,text)
    except ParseReview as exc:
        return {'accuracy':None,'structured_fact_f1':None,'status':'prediction_review','review_reasons':[str(exc)]}
    reviews,supplementary=partition_reviews(profile,reviews,actual)
    extracted=set(actual);verified_supplements=set()
    if profile.get('member_set_complete'):
        groups={}
        for f in expected:
            if f.relation in MEMBER_RELATIONS:groups.setdefault((f.subject,f.relation,f.qualifiers),set()).add(f.object)
        for f in extracted:
            key=(f.subject,f.relation,f.qualifiers)
            if f.polarity=='negative' and key in groups and f.object not in groups[key]:
                verified_supplements.add(f)
        actual-=verified_supplements
    # A query-defined selected object can be referenced without naming its ID.
    # Explicitly wrong IDs retain their original subjects and cannot borrow matches.
    if profile['type'] in {25,26}:
        selected={f.object for f in expected if f.relation=='selected_max_sv'}
        attrs={'length_bp','query_genome','reference_genome'}
        def alias(f):
            return Fact.make(selection_subject(profile),f.relation,f.object,dict(f.qualifiers),f.polarity) if f.relation in attrs and f.subject in selected else f
        expected={alias(f) for f in expected};actual={alias(f) for f in actual}
    tp=len(expected & actual);fp=len(actual-expected);fn=len(expected-actual)
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.
    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
    return {'accuracy':None if reviews else int(fp==0 and fn==0),
            'structured_fact_precision':None if reviews else precision,'structured_fact_recall':None if reviews else recall,
            'structured_fact_f1':None if reviews else f1,'tp':tp,'fp':fp,'fn':fn,
            'provisional_known_fact_f1':f1,'status':'prediction_review' if reviews else 'scored',
            'review_reasons':reviews,'supplementary_audit':supplementary,'reference_facts':[f.record() for f in sorted(expected,key=repr)],
            'prediction_facts':[f.record() for f in sorted(extracted,key=repr)],
            'verified_noncore_supplements':[f.record() for f in sorted(verified_supplements,key=repr)],
            'profile_sha256':profile['profile_sha256'],'scoring_version':VERSION,'final_answer':text}
