"""Lossless assertion-oriented formatting adapters; never substitute Gold values."""
import json,re


def normalize_forms(text):
    text=re.sub(r'(?m)^\s*(?:-{3,}|\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?)\s*$','',text)
    text=re.sub(r'(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|\d+[.)、]\s+)','',text)
    text=re.sub(r'染色体\s*[:：]\s*(\d+)',lambda m:'Chr'+m[1],text)
    text=re.sub(r'第?(\d+)号染色体',lambda m:'Chr'+m[1],text)
    for old,new in [('起始位点','起始位置'),('起始坐标','起始位置'),('起始位置为','起始位置为'),('终止位点','终止位置'),('终止坐标','终止位置'),('结束位置','终止位置')]:text=text.replace(old,new)
    text=re.sub(r'(?:物理)?坐标范围从\s*(\d[\d,]*)\s*(?:到|至)\s*(\d[\d,]*)',r'起始位置为\1，终止位置为\2',text)
    text=re.sub(r'(起始位置|终止位置|起点|终点)\s*(?:\([^)]*\))?\s*[:：]\s*(?:约|approximately\s*)?\s*(\d{1,3}(?:[ ,]\d{3})+|\d+)',lambda m:m[1]+':'+m[2].replace(' ',''),text,flags=re.I)
    text=re.sub(r'(叶|根|幼穗)(?:组织)?(?:中)?(?:的)?表达量[^,，。\n()]{0,12}\((\d+(?:\.\d+)?)\)',r'\1表达量为\2',text)
    text=re.sub(r'(叶|根|幼穗)(?:组织)?(?:中)?(?:的)?(?:表达量)?(?:最高|最低|中等|相对较低|较高|较低|为|是)?\((\d+(?:\.\d+)?)\)',r'\1表达量为\2',text)
    return text


def mask_examples(text):
    """Explicit hypothetical sections persist across tables/fences until a new heading."""
    out=[];masked=[];active=False
    for line in text.splitlines():
        heading=bool(re.match(r'^\s*#{1,6}\s',line))
        start=bool(re.search(r'示例结果|结果示例|示例.*假设|模拟结果|假设.*如下|假设分析|查询结果.*[（(]假设|example results|hypothetical results',line,re.I))
        if heading and active and not start:active=False
        if re.search(r'实际(?:查询)?结果|实际答案|最终答案',line):active=False
        if start:active=True
        if active:masked.append(line)
        else:out.append(line)
    return '\n'.join(out),masked


def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate_json_key:'+key)
        result[key]=value
    return result


def json_lines(value,t):
    """Project only declared fields; unknown fields remain visible for audit."""
    if isinstance(value,list):return [line for v in value for line in json_lines(v,t)]
    if not isinstance(value,dict):return [str(value)] if value is not None else []
    d={str(k).lower().split('.')[-1]:v for k,v in value.items()}
    out=[]
    for key in ['result','results','data']:
        if key in d:out.extend(json_lines(d.pop(key),t))
    # query/question is a request echo, not an asserted answer.
    d.pop('query',None);d.pop('question',None)
    def take(*keys):
        for key in keys:
            if key in d:return d.pop(key)
        return None
    gene=take('gene','gene_id','gene_name') if t in {1,2,4,5,6,9,11,12,20} else take('gene','gene_id')
    sv=take('sv_name','sv','structural_variation')
    prefix=('基因'+str(gene)+'，') if gene else ''
    if sv:prefix='结构变异'+str(sv)+'，'
    chr_=take('chromosome','chr');start=take('start_pos','start_position','start');end=take('end_pos','end_position','end')
    if chr_ is not None:out.append(prefix+'染色体:'+str(chr_).replace('Chr','').replace('chr',''))
    if start is not None:out.append(prefix+'起始位置:'+str(start))
    if end is not None:out.append(prefix+'终止位置:'+str(end))
    strand=take('strand');
    if strand is not None:out.append(prefix+str(strand))
    url=take('gene_url','url','dna_seq','cds_seq','protein_seq')
    if url is not None:out.append(prefix+str(url))
    annotation=take('function','annotation','function_annotation')
    if annotation is not None:out.append(prefix+'注释是'+str(annotation))
    expression=take('expression')
    if isinstance(expression,dict):
        for k,v in expression.items():d[k.lower()]=v
    for names,label in [(['leaf','leaf_value'],'叶'),(['root','root_value'],'根'),(['young_ear','young_ear_value','panicle'],'幼穗')]:
        for k in names:
            if k in d:
                v=d.pop(k);out.append(prefix+label+('表达数据暂无' if v is None or str(v).lower() in ['-','null','none','unavailable'] else '表达量为'+str(v)))
    ogi=take('ogi');
    if ogi is not None:out.append(prefix+'属于'+str(ogi))
    count=take('sv_count','member_count','gene_count','mrna_count','count');kind=take('sv_type','svtype','type')
    if t in {27,28} and count is not None and kind is not None:
        scope='查询基因组:'+str(d['query_genome'])+'，' if 'query_genome' in d else ''
        out.append(scope+str(count)+'个'+str(kind)+'类型的结构变异')
    else:
        if count is not None:out.append(prefix+(str(ogi)+'，' if ogi else '')+'共有'+str(count)+'个')
        if kind is not None:out.append(prefix+'类型:'+str(kind))
    length=take('sv_length','svlength','length')
    if length is not None:out.append(prefix+'长度:'+str(length))
    for k,label in [('query_genome','查询基因组'),('reference_genome','参考基因组')]:
        if k in d:out.append(prefix+label+':'+str(d.pop(k)))
    for k in ['gene_name','genes','gene_names','members','transcripts','mrna','mutants','mutant_name','svs','te_type','te_annotations','annotations']:
        if k in d:
            v=d.pop(k);vs=v if isinstance(v,list) else [v]
            for x in vs:out.extend(json_lines(x,t) if isinstance(x,dict) else [prefix+'成员:'+str(x)])
    for k,v in d.items():out.append('附加JSON字段 '+k+':'+json.dumps(v,ensure_ascii=False))
    return out


def adapt(profile,text):
    text,masked=mask_examples(text);audit=[{'kind':'nonasserted_example','text':'\n'.join(masked)}] if masked else []
    t=profile['type']
    # Decode complete payloads/fences only. No brace guessing or winner selection.
    raw=text.strip();fences=list(re.finditer(r'```(?:json)?\s*\n(.*?)```',text,re.S|re.I))
    if raw.startswith(('{','[')):
        try:text='\n'.join(json_lines(json.loads(raw,object_pairs_hook=no_duplicates),t))
        except json.JSONDecodeError:pass
        except ValueError as e:raise ValueError(str(e))
    elif fences:
        for m in reversed(fences):
            try:replacement='\n'.join(json_lines(json.loads(m[1],object_pairs_hook=no_duplicates),t))
            except json.JSONDecodeError:continue
            except ValueError as e:raise ValueError(str(e))
            text=text[:m.start()]+replacement+text[m.end():]
    text=normalize_forms(text).replace('。','。\n')
    from .structured_facts_v3 import SV,ids
    out=[];current_sv=None;current_type=None
    for line in text.splitlines():
        # Table row -> explicit property/value or member record.
        if line.strip().startswith('|'):
            cells=[x.strip() for x in line.strip().strip('|').split('|')]
            if len(cells)>=2:
                label,value=cells[:2]
                if t==12 and label in ['叶','根','幼穗','leaf','root','panicle']:
                    line=label+('表达数据暂无' if value in ['-','暂无','N/A'] else '表达量为'+value)
                elif t in {27,28}:
                    m=re.search(r'\b(DEL|INS|TRA|INV|OTH)\b',label,re.I)
                    if m and re.fullmatch(r'\d+',value):line=m[1]+':'+value
                elif t==1 and re.search(r'染色体|起始|终止|start|end',label,re.I):line=label+':'+value
        svs=ids(SV,line)
        if len(svs)==1:current_sv=svs[0]
        if t in {23,24,25,26} and current_sv and not svs and re.search(r'查询基因组|参考基因组|长度|query genome|reference genome|length',line,re.I):
            line='结构变异'+current_sv+'，'+line
        if t in {27,28}:
            typ=re.search(r'\b(DEL|INS|TRA|INV|OTH)\b',line,re.I)
            if typ:current_type=typ[1].upper()
            n=re.search(r'(?:数量|计数|count)\s*[:：]\s*(\d+)',line,re.I)
            if n and current_type:line=current_type+':'+n[1]
            line=re.sub(r'\((DEL|INS|TRA|INV|OTH)\)\s*[:：]\s*(\d+)',r'\1:\2',line,flags=re.I)
        # Drop formatting artifacts; narrative is kept for separate audit.
        if line.strip() in ['```','```json']:continue
        out.append(line)
    return normalize_forms('\n'.join(out)),audit
