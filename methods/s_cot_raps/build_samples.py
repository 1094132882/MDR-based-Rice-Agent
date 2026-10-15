#!/usr/bin/env python3
import csv, re, argparse, pathlib, sys

TYPE2TOOL = {
    "type1":"gene_locator",       # 定位：ChrXX:start-end, strand
    "type2":"genebasicinfoquery", # 链：正/负
    "type3":"genebasicinfoquery", # 转录本列表
    "type4":"genebasicinfoquery", # 基因 DNA 序列（这里先用基因ID作命中片段）
    "type5":"genebasicinfoquery", # CDS 序列（同上）
    "type6":"genebasicinfoquery", # 蛋白序列（同上）
    "type7":"genemutantinfoquery",
    "type8":"genemutantinfoquery",
    "type9":"ogiinfoquery",
    "type10":"ogiinfoquery",
    "type11":"genefunctionquery",
    "type12":"homologousgeneandexpressionquery",
    "type13":"adjacentgenesquery",
    "type14":"adjacentgenesquery",
    "type15":"adjacentgenesquery",
    "type16":"adjacentgenesquery",
    "type17":"adjacentgenesquery",
    "type18":"adjacentgenesquery",
    "type19":"adjacentgenesquery",
    "type20":"ogiinfoquery",
    "type21":"structuralvariationlocatorquery",
    "type22":"structuralvariationlocatorquery",
    "type23":"structuralvariationlocatorquery",
    "type24":"structuralvariationlocatorquery",
    "type25":"structuralvariationlocatorquery",
    "type26":"structuralvariationlocatorquery",
    "type27":"structuralvariationlocatorquery",
    "type28":"structuralvariationlocatorquery",
    "type29":"structuralvariationlinkquery",
}

chr_pos_pat = re.compile(r'Chr\d{2}:\d+-\d+')
ogi_pat     = re.compile(r'OGI:\d{8}')

def gene_id_guess(s: str) -> str:
    # 从中文答案里尽量捞出像 Os... / LOC_Os... / OGI:... / TMG... 等标识
    m = re.search(r'(LOC_Os\d+g\d+|Os[A-Za-z0-9_\.]+|OGI:\d{8}|TMG\d+\.\d+|R9311C\d+g\d+|[A-Z]{2,}\d+_[A-Za-z0-9_\.]+)', s)
    return m.group(1) if m else ''

def gold_from_truth(split, truth):
    # 针对不同题型抽“最稳命中的关键片段”
    if split == 'type1':
        m = chr_pos_pat.search(truth)
        return m.group(0) if m else gene_id_guess(truth)
    if split == 'type2':
        return '位于正链' if '正链' in truth else ('位于负链' if '负链' in truth else gene_id_guess(truth))
    if split == 'type3':
        # 抓第一个转录本编号（*.Txx）
        m = re.search(r'([A-Za-z0-9_\.]+\.T\d+)', truth)
        return m.group(1) if m else gene_id_guess(truth)
    if split in ('type4','type5','type6'):
        # 序列类：先用基因ID命中（后面接入真实工具再换成更严格数值）
        g = gene_id_guess(truth)
        return g if g else 'DNA序列可以通过点击'
    if split in ('type7','type8'):
        # 突变体：抓第一个材料编号
        m = re.search(r'(\d{2}[A-Z]{2,}\d+)', truth)
        return m.group(1) if m else gene_id_guess(truth)
    if split in ('type9','type10','type20'):
        m = ogi_pat.search(truth)
        return m.group(0) if m else gene_id_guess(truth)
    if split == 'type11':
        m = re.search(r'(UniProtKB/Swiss-Prot:[A-Z0-9]+)', truth)
        return m.group(1) if m else '注释'
    if split == 'type12':
        # 表达量：先用“叶中的表达量”为命中片段，后续再严
        return '叶中的表达量为'
    if split in ('type13','type14','type15','type16','type17','type18','type19'):
        # 区间/邻近：先命中“共有X个基因”或“最近的上游/下游基因是”
        m = re.search(r'共有\d+个基因', truth)
        return m.group(0) if m else ('最近的上游基因' if '上游' in truth else ('最近的下游基因' if '下游' in truth else gene_id_guess(truth)))
    if split in ('type21','type22','type23','type24','type25','type26','type27','type28'):
        # SV结果常含“结构变异名”“类型：DEL/INS/TRA/INV”
        m = re.search(r'类型：([A-Z]{3})', truth)
        return f'类型：{m.group(1)}' if m else '结构变异'
    if split == 'type29':
        return '关联的装作元件' if '装作元件' in truth else '转座'
    # 兜底
    return gene_id_guess(truth) or truth.strip()[:24]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='fin', required=True, help='原始 dataset.csv 路径（含 question, ground_truth, split）')
    ap.add_argument('--out', dest='fout', required=True, help='输出 samples_150.csv')
    ap.add_argument('--dev', dest='dev', default='', help='可选：额外输出 dev 子集，如 methods/s_cot_raps/samples_dev20.csv')
    args = ap.parse_args()

    rows = []
    with open(args.fin, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)

    out_rows = []
    for i, r in enumerate(rows, start=1):
        q = r.get('question','').strip()
        gt = r.get('ground_truth','').strip()
        sp = r.get('split','').strip()
        tool = TYPE2TOOL.get(sp, 'genebasicinfoquery')
        gold = gold_from_truth(sp, gt)
        out_rows.append({
            'id': f'q{i:03d}',
            'question': q,
            'tool': tool,
            'gold_contains': gold,
            'split': sp
        })

    # 写全量
    pathlib.Path(args.fout).parent.mkdir(parents=True, exist_ok=True)
    with open(args.fout, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['id','question','tool','gold_contains','split'])
        w.writeheader(); w.writerows(out_rows)

    # 写 dev（如果指定了）
    if args.dev:
        n = min(20, len(out_rows))
        with open(args.dev, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['id','question','tool','gold_contains','split'])
            w.writeheader(); w.writerows(out_rows[:n])

    print(f'Wrote {len(out_rows)} rows -> {args.fout}')
    if args.dev:
        print(f'Wrote dev -> {args.dev}')

if __name__ == '__main__':
    main()