#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, pandas as pd
from pathlib import Path

SRC = Path("methods/s_cot_raps/data/dataset.csv")
DST = Path("methods/s_cot_raps/samples_all.csv")

# 1) 读入更鲁棒：engine='python' 可容忍少量不规则行
raw = pd.read_csv(SRC, engine="python")

# 2) type -> 我们的9类工具映射（尽量聚合到论文里的9个“工具”）
#   可以根据你 schema 的 Tools 键名调整（保持三处一致：samples、ALLOWED_KEYS、mdr_schema.json）
MAP = {
    # 基因定位/上下游/邻近 都并入 gene_locator / adjacentgenesquery
    "type1":  "gene_locator",                       # 物理坐标
    "type13": "gene_locator",                       # 区域基因列表
    "type14": "adjacentgenesquery",                 # 上游邻近
    "type15": "adjacentgenesquery",                 # 下游邻近
    "type16": "adjacentgenesquery",                 # 最近上游
    "type17": "adjacentgenesquery",                 # 最近下游
    "type18": "adjacentgenesquery",                 # 上游前N
    "type19": "adjacentgenesquery",                 # 下游前N

    # 基因基础信息/转录本/链性/功能/表达
    "type2":  "genebasicinfoquery",                 # 链方向
    "type3":  "genebasicinfoquery",                 # 转录本
    "type11": "genefunctionquery",                  # 功能注释
    "type12": "homologousgeneandexpressionquery",   # 表达量

    # OGI 相关
    "type9":  "ogiinfoquery",                       # gene -> OGI
    "type10": "ogiinfoquery",                       # OGI -> genes
    "type20": "ogiinfoquery",                       # OGI 计数

    # 突变体
    "type7":  "genemutantinfoquery",                # gene -> mutants
    "type8":  "genemutantinfoquery",                # mutant -> genes

    # 结构变异 定位/统计
    "type21": "structuralvariationlocatorquery",    # gene 区域 SV
    "type22": "structuralvariationlocatorquery",    # SV 子类型过滤
    "type23": "structuralvariationlocatorquery",    # 指定区间 SV
    "type24": "structuralvariationlocatorquery",    # 指定类型+区间 SV
    "type25": "structuralvariationlocatorquery",    # 最长 SV
    "type26": "structuralvariationlocatorquery",    # 最长(类型)
    "type27": "structuralvariationlocatorquery",    # 分类统计
    "type28": "structuralvariationlocatorquery",    # 单类计数

    # SV ↔ TE 关联
    "type29": "structuralvariationlinkquery",       # TE 注释
}

def to_gold_contains(gt: str) -> str:
    """从 ground_truth 中提取用于 EM 的关键片段；不足的用空串。"""
    if not isinstance(gt, str): return ""
    keys = []

    # 常见关键模式
    for pat in [
        r"Chr(?:0[1-9]|1[0-2]):\d+-\d+",  # 染色体坐标
        r"OGI:\d{8}",                     # OGI 号
        r"LOC_Os[0-9a-zA-Z_\.]+",         # 常见基因名
        r"\bOs[0-9A-Za-z_\.]+",           # 其他品种基因名
    ]:
        m = re.search(pat, gt)
        if m: keys.append(m.group(0))

    # 如果是“列出多个基因/突变体”，抓两个代表名做 contains
    many = re.findall(r"\b[0-9A-Za-z_\.]+", gt)
    if many:
        keys.extend(many[:2])

    # 去重
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k); out.append(k)
    return ";".join(out[:4])  # 最多取 4 个关键片段

# 3) 规范化为 runner 需要的四列
rows = []
for i, r in raw.iterrows():
    q = str(r.get("question", "")).strip()
    gt = str(r.get("ground_truth", "")).strip()
    sp = str(r.get("split", "")).strip()
    tool = MAP.get(sp, "genebasicinfoquery")  # 兜底
    rows.append({
        "id": f"q{(i+1):03d}",
        "tool": tool,
        "question": q,
        "gold_contains": to_gold_contains(gt),
    })

df = pd.DataFrame(rows, columns=["id","tool","question","gold_contains"])
DST.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(DST, index=False, encoding="utf-8")
print(f"OK -> {DST}  ({len(df)} rows)")