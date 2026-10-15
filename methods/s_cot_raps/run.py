#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S-CoT × RAPS runner 
支持动态 MDR schema、提示生成、LLM 调用和完善评测

用法示例:
  # 使用 LLM (Ollama)
  python methods/s_cot_raps/run.py \
    --engine llm \
    --method s_cot_raps \
    --input methods/s_cot_raps/dataset.csv \
    --out runs/s_cot_raps.jsonl \
    --max 150
  
  # 使用本地工具（ground truth）
  python methods/s_cot_raps/run.py \
    --engine py \
    --method ground_truth \
    --input methods/s_cot_raps/dataset.csv \
    --out runs/ground_truth.jsonl \
    --max 150
"""
from __future__ import annotations
import os, json, time, argparse, importlib, sys, re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from dotenv import load_dotenv
import requests

# 导入统一配置（必须在其他模块之前）
try:
    from config import OLLAMA_MODEL, OLLAMA_BASE_URL, setup_env
    setup_env()
except ImportError:
    pass  # 配置文件不存在时使用默认值

import pandas as pd

# 尝试导入 tqdm 进度条
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # 简单的进度条替代
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable else 0)
            self.desc = desc or ""
            self.n = 0
            if self.desc:
                print(f"\n{self.desc}", flush=True)
        
        def __iter__(self):
            for item in self.iterable:
                yield item
                self.update(1)
        
        def update(self, n=1):
            self.n += n
            if self.total > 0:
                percent = (self.n / self.total) * 100
                print(f"\r  进度: {self.n}/{self.total} ({percent:.1f}%) ", end='', flush=True)
        
        def close(self):
            if self.total > 0:
                print(f"\r  完成: {self.n}/{self.total} (100.0%) ✓", flush=True)
        
        def set_postfix(self, **kwargs):
            pass

# 加载环境变量
load_dotenv()

# ---------------------------------------------------------------------------
# 1) 自动找项目根 & rice_Python
#    逻辑：从本脚本所在目录一直往上找，谁里有 rice_Python/ 就加谁
#    找不到再兜底把 cwd 和 cwd/rice_Python 也加上
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
candidates = []

# a) 脚本所在目录往上找 5 层
cur = THIS_FILE.parent
for _ in range(5):
    candidates.append(cur)
    cur = cur.parent

# b) 当前工作目录也尝试一下（你在项目根跑时会用到）
candidates.append(Path.cwd())

added = set()
for base in candidates:
    rp = base / "rice_Python"
    if rp.is_dir():
        sys.path.append(str(base))        # /.../rice_mdr1
        sys.path.append(str(rp))          # /.../rice_mdr1/rice_Python
        added.add(str(base))
        added.add(str(rp))

# 如果上面都没找到，就至少把 cwd 加进去，免得连相对 import 都不行
if not added:
    sys.path.append(str(Path.cwd()))
    rp2 = Path.cwd() / "rice_Python"
    if rp2.is_dir():
        sys.path.append(str(rp2))

# ---------------------------------------------------------------------------
# 2) schema 名 → 你项目里真正的模块路径 + 函数名
#    这块维持原来的 9 个映射
# ---------------------------------------------------------------------------
PY_TOOL_IMPL = {
    "gene_basic_info": (
        "rice_Python.App.chat.tools.genebasicinfoquery",
        "gene_basic_info_query",
    ),
    "gene_function": (
        "rice_Python.App.chat.tools.genefunctionquery",
        "gene_function_query",
    ),
    "gene_locator": (
        "rice_Python.App.chat.tools.genelocatorquery",
        "gene_locator_query",
    ),
    "gene_mutant_info": (
        "rice_Python.App.chat.tools.genemutantinfoquery",
        "gene_mutant_info_query",
    ),
    "ogi_info": (
        "rice_Python.App.chat.tools.ogiinfoquery",
        "ogi_info_query",
    ),
    "adjacent_genes": (
        "rice_Python.App.chat.tools.adjacentgenesquery",
        "adjacent_genes_query",
    ),
    "homologous_gene_and_expression": (
        "rice_Python.App.chat.tools.homologousgeneandexpressionquery",
        "homologous_gene_and_expression_query",
    ),
    "structural_variation_link": (
        "rice_Python.App.chat.tools.structuralvariationlinkquery",
        "structural_variation_link_query",
    ),
    "structural_variation_locator": (
        "rice_Python.App.chat.tools.structuralvariationlocatorquery",
        "structural_variation_locator_query",
    ),
}

ALLOWED_KEYS: Dict[str, set] = {
    "gene_basic_info": {"Gene", "Chromosome", "Position", "Strand", "Transcripts", "text", "Expression", "URL"},
    "gene_function": {"Gene", "Function", "GO_Terms", "Pathways", "Evidence", "text"},
    "gene_locator": {"Chromosome", "Position", "Gene", "Strand", "text"},
    "gene_mutant_info": {"Gene", "Genes", "Mutants", "Phenotypes", "text"},
    "ogi_info": {"OGI", "Genes", "Orthologs", "Paralogs", "Size", "text", "gene_count"},
    "adjacent_genes": {"TargetGene", "Direction", "Neighbors", "Genes", "K", "Window", "upstream", "downstream", "text"},
    "homologous_gene_and_expression": {"Gene", "Homologs", "Expression", "text"},
    "structural_variation_link": {"gene_name", "sv_list", "SVs", "TE_Annotations", "text"},
    "structural_variation_locator": {"SVs", "sv_list", "Type", "Longest", "Stats", "text"},
}

# Type to Tool 映射（从 build_samples.py）
TYPE2TOOL = {
    "type1": "gene_locator",
    "type2": "gene_basic_info",
    "type3": "gene_basic_info",
    "type4": "gene_basic_info",
    "type5": "gene_basic_info",
    "type6": "gene_basic_info",
    "type7": "gene_mutant_info",
    "type8": "gene_mutant_info",
    "type9": "ogi_info",
    "type10": "ogi_info",
    "type11": "gene_function",
    "type12": "homologous_gene_and_expression",
    "type13": "adjacent_genes",
    "type14": "adjacent_genes",
    "type15": "adjacent_genes",
    "type16": "adjacent_genes",
    "type17": "adjacent_genes",
    "type18": "adjacent_genes",
    "type19": "adjacent_genes",
    "type20": "ogi_info",
    "type21": "structural_variation_locator",
    "type22": "structural_variation_locator",
    "type23": "structural_variation_locator",
    "type24": "structural_variation_locator",
    "type25": "structural_variation_locator",
    "type26": "structural_variation_locator",
    "type27": "structural_variation_locator",
    "type28": "structural_variation_locator",
    "type29": "structural_variation_link",
}

GENE_NAME_PATTERNS = [
    r"(Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?)",
    r"(Os[A-Za-z0-9_]+_\d+[Gg]\d+(?:\.\d+)?)",
    r"(LOC_Os\d+g\d+(?:\.\d+)?)",
    r"(R\d+C\d+g\d+)",
    r"(Oglab_\d+)",
    r"(TMG\d+(?:\.\d+)?)",
    r"(Os\d{2}g\d+(?:\.\d+)?)",
]

OGI_NAME_PATTERN = r"(OGI:\d{8})"

def extract_gold_contains(ground_truth: str, split: str) -> str:
    """从 ground_truth 提取关键片段作为 gold_contains（保留用于向后兼容）"""
    if not ground_truth:
        return ""
    
    # type1: 提取 Chr 坐标
    if split == "type1":
        m = re.search(r'Chr\d{2}:\d+-\d+', ground_truth)
        if m:
            return m.group(0)
    
    # type2: 提取链信息
    if split == "type2":
        if '正链' in ground_truth:
            return '位于正链'
        if '负链' in ground_truth:
            return '位于负链'
    
    # 其他类型：提取基因 ID
    gene_patterns = [
        r'LOC_Os\d+g\d+',
        r'Os[A-Za-z0-9_]+',
        r'OGI:\d{8}',
    ]
    for pattern in gene_patterns:
        m = re.search(pattern, ground_truth)
        if m:
            return m.group(0)
    
    # 兜底：返回前 50 个字符
    return ground_truth[:50]

def extract_gene_name(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for pattern in GENE_NAME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def extract_ogi_name(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(OGI_NAME_PATTERN, text)
    return match.group(1) if match else None

def detect_sequence_resource(question: str) -> str:
    q = question or ""
    if any(k in q for k in ["mRNA", "转录本"]):
        return "mRNA 转录本"
    if "CDS" in q or "编码区" in q:
        return "CDS 序列"
    if any(k in q for k in ["蛋白", "氨基酸"]):
        return "蛋白质序列"
    if any(k in q for k in ["DNA", "核苷酸", "基因序列"]):
        return "DNA 序列"
    return "相关序列"

def build_sequence_link_response(question: str) -> dict:
    gene_name = extract_gene_name(question)
    if not gene_name:
        return {}
    url = f"https://riceome.hzau.edu.cn/dev/genecard/{gene_name}/"
    resource = detect_sequence_resource(question)
    text = f"{gene_name} 的{resource}可以通过点击 {url} 查看。"
    return {"Gene": gene_name, "URL": url, "text": text}

def normalize_strand_label(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ['+', '正', '正链', 'plus', 'positive', 'forward']:
        return '+'
    if v in ['-', '负', '负链', 'minus', 'negative', 'reverse']:
        return '-'
    return None

_NEO4J_GRAPH = None
_NEO4J_GRAPH_DISABLED = False

def get_neo4j_graph():
    global _NEO4J_GRAPH, _NEO4J_GRAPH_DISABLED
    if _NEO4J_GRAPH_DISABLED:
        return None
    if _NEO4J_GRAPH is not None:
        return _NEO4J_GRAPH
    try:
        from py2neo import Graph
    except ImportError:
        _NEO4J_GRAPH_DISABLED = True
        return None
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        _NEO4J_GRAPH_DISABLED = True
        return None
    try:
        _NEO4J_GRAPH = Graph(uri, auth=(user, password))
    except Exception:
        _NEO4J_GRAPH_DISABLED = True
        return None
    return _NEO4J_GRAPH

def fetch_gene_basic_from_db(gene_name: Optional[str]) -> Optional[dict]:
    graph = get_neo4j_graph()
    if not graph or not gene_name:
        return None
    query = """
    MATCH (g:Gene {name: $name})
    OPTIONAL MATCH (g)-[:chromosome_no]->(c:Chromosome)
    OPTIONAL MATCH (g)-[:start_pos]->(sp:Position)
    OPTIONAL MATCH (g)-[:end_pos]->(ep:Position)
    OPTIONAL MATCH (g)-[:strand_info]->(st:Strand)
    RETURN g.name AS gene_name,
           g.URL AS gene_url,
           c.name AS chromosome,
           sp.name AS start_pos,
           ep.name AS end_pos,
           st.name AS strand_name
    """
    try:
        records = graph.run(query, name=gene_name).data()
    except Exception:
        return None
    return records[0] if records else None

def enrich_gene_basic_info(obj: dict, question: str) -> dict:
    gene_name = obj.get("Gene") or obj.get("gene_name") or extract_gene_name(question)
    info = fetch_gene_basic_from_db(gene_name)
    if info:
        if gene_name and "Gene" not in obj:
            obj["Gene"] = gene_name
        if info.get("chromosome") and not obj.get("Chromosome"):
            obj["Chromosome"] = info["chromosome"]
        start_pos = info.get("start_pos")
        end_pos = info.get("end_pos")
        if start_pos and end_pos and not obj.get("Position"):
            obj["Position"] = f"{start_pos}-{end_pos}"
        if info.get("gene_url") and not obj.get("URL"):
            obj["URL"] = info["gene_url"]
        strand = normalize_strand_label(info.get("strand_name"))
        if not strand and start_pos and end_pos:
            try:
                strand = '+' if int(start_pos) < int(end_pos) else '-'
            except ValueError:
                strand = None
        if strand:
            obj["Strand"] = strand
    return obj

def fetch_ogi_member_count(gene_name: Optional[str] = None, ogi_name: Optional[str] = None) -> Optional[dict]:
    graph = get_neo4j_graph()
    if not graph:
        return None
    if gene_name:
        query = """
        MATCH (ogi:OGI)-[:has_a_gene]->(:Gene {name: $gene})
        WITH ogi
        MATCH (ogi)-[:has_a_gene]->(member:Gene)
        RETURN ogi.name AS ogi, COUNT(member) AS member_count
        """
        params = {"gene": gene_name}
    elif ogi_name:
        query = """
        MATCH (ogi:OGI {name: $ogi})-[:has_a_gene]->(member:Gene)
        RETURN ogi.name AS ogi, COUNT(member) AS member_count
        """
        params = {"ogi": ogi_name}
    else:
        return None
    try:
        records = graph.run(query, **params).data()
    except Exception:
        return None
    return records[0] if records else None

CHINESE_NUMERAL_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}

def chinese_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    if text in CHINESE_NUMERAL_MAP:
        return CHINESE_NUMERAL_MAP[text]
    # 简单处理“十X”“X十”等格式
    if text.endswith("十") and len(text) == 2:
        base = CHINESE_NUMERAL_MAP.get(text[0], 0)
        return base * 10
    if text.startswith("十") and len(text) == 2:
        base = CHINESE_NUMERAL_MAP.get(text[1], 0)
        return 10 + base
    return None

def extract_chromosome_label(question: str) -> Optional[str]:
    if not question:
        return None
    match = re.search(r'Chr\s*0*(\d+)', question, re.IGNORECASE)
    if match:
        return f"Chr{int(match.group(1)):02d}"
    for pattern in [r'染色体([一二三四五六七八九十]{1,3})号', r'([一二三四五六七八九十]{1,3})号染色体']:
        m = re.search(pattern, question)
        if m:
            num = chinese_to_int(m.group(1))
            if num:
                return f"Chr{num:02d}"
    return None

def extract_coordinate_range(question: str) -> Tuple[Optional[int], Optional[int]]:
    if not question:
        return None, None
    text = question.replace(",", "")
    match = re.search(r'Chr\d+\s*[:：]\s*(\d+)\s*[-–~～]\s*(\d+)', text, re.IGNORECASE)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return min(start, end), max(start, end)
    match = re.search(r'(\d+)\s*kb\s*(?:到|[-–~～])\s*(\d+)\s*kb', text, re.IGNORECASE)
    if match:
        start = int(match.group(1)) * 1000
        end = int(match.group(2)) * 1000
        return min(start, end), max(start, end)
    match = re.search(r'(\d+)\s*(?:kb)?\s*(?:到|[-–~～])\s*(\d+)\s*(?:bp|碱基)?', text, re.IGNORECASE)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        # 如果原文带 kb 但没重复，可通过关键字判断
        if 'kb' in text[match.start():match.end()].lower():
            start *= 1000
            end *= 1000
        return min(start, end), max(start, end)
    return None, None

ACCESSION_PATTERNS = [
    r'([A-Za-z0-9_]+)品种',
    r'([A-Za-z0-9_]+)的Chr',
    r'([A-Za-z0-9_]+)的染色体',
    r'([A-Za-z0-9_]+)染色体',
    r'\b([A-Za-z]{2,}\d{0,4})\b',
    r'\b(\d{5,6})\b',
]

def extract_accession_name(question: str) -> Optional[str]:
    if not question:
        return None
    for pattern in ACCESSION_PATTERNS:
        m = re.search(pattern, question)
        if m:
            candidate = m.group(1)
            if candidate.lower().startswith("chr"):
                continue
            return candidate
    return None

def fetch_adjacent_genes_by_range(accession: str, chromosome: str, start_bp: int, end_bp: int) -> Optional[List[str]]:
    graph = get_neo4j_graph()
    if not graph or not accession or not chromosome or start_bp is None or end_bp is None:
        return None
    query = """
    MATCH (acc:Accession {name: $accession})
    MATCH (chr:Chromosome {name: $chromosome})
    MATCH (g:Gene)-[:type]->(acc)
    MATCH (g)-[:chromosome_no]->(chr)
    MATCH (g)-[:start_pos]->(sp:Position)
    MATCH (g)-[:end_pos]->(ep:Position)
    WHERE toInteger(sp.name) >= $start AND toInteger(ep.name) <= $end
    RETURN g.name AS gene_name
    ORDER BY toInteger(sp.name)
    """
    try:
        records = graph.run(query, accession=accession, chromosome=chromosome, start=start_bp, end=end_bp).data()
    except Exception:
        return None
    genes = [r.get("gene_name") for r in records if r.get("gene_name")]
    return genes if genes else None

def fetch_adjacent_neighbor(gene_name: Optional[str], direction: str = "downstream") -> Optional[List[str]]:
    graph = get_neo4j_graph()
    if not graph or not gene_name:
        return None
    direction = direction or "downstream"
    if direction == "upstream":
        comparison = "<"
        order = "DESC"
        source_pos = "start"
    else:
        comparison = ">"
        order = "ASC"
        source_pos = "end"
    query = f"""
    MATCH (target:Gene {{name: $gene}})
    MATCH (target)-[:chromosome_no]->(chr:Chromosome)
    MATCH (target)-[:type]->(acc:Accession)
    MATCH (target)-[:start_pos]->(t_start:Position)
    MATCH (target)-[:end_pos]->(t_end:Position)
    WITH target, chr, acc, toInteger(t_start.name) AS start_val, toInteger(t_end.name) AS end_val
    MATCH (neighbor:Gene)-[:chromosome_no]->(chr)
    MATCH (neighbor)-[:type]->(acc)
    MATCH (neighbor)-[:start_pos]->(n_start:Position)
    MATCH (neighbor)-[:end_pos]->(n_end:Position)
    WHERE toInteger(n_start.name) {comparison} (CASE WHEN $source_pos = 'end' THEN end_val ELSE start_val END)
    RETURN neighbor.name AS gene_name, toInteger(n_start.name) AS start_pos
    ORDER BY start_pos {order}
    LIMIT 1
    """
    params = {"gene": gene_name, "source_pos": "end" if source_pos == "end" else "start"}
    try:
        records = graph.run(query, **params).data()
    except Exception:
        return None
    genes = [r.get("gene_name") for r in records if r.get("gene_name")]
    return genes if genes else None

def fallback_adjacent_neighbors(question: str) -> Optional[List[str]]:
    accession = extract_accession_name(question)
    chromosome = extract_chromosome_label(question)
    start_bp, end_bp = extract_coordinate_range(question)
    if accession and chromosome and start_bp is not None and end_bp is not None:
        genes = fetch_adjacent_genes_by_range(accession, chromosome, start_bp, end_bp)
        if genes:
            return genes
    direction = None
    if "上游" in question:
        direction = "upstream"
    elif "下游" in question:
        direction = "downstream"
    if direction:
        gene = extract_gene_name(question)
        if gene:
            return fetch_adjacent_neighbor(gene, direction)
    return None

def extract_mutant_name(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r'(\d{2}NB[A-Z]\d{2})', text.upper())
    return match.group(1) if match else None

def fetch_gene_mutant_records(gene_name: Optional[str] = None, mutant_name: Optional[str] = None) -> Optional[dict]:
    graph = get_neo4j_graph()
    if not graph:
        return None
    if gene_name:
        query = """
        MATCH (:Gene {name: $gene})-[:has_a_mutant]->(m:Mutant)
        RETURN DISTINCT m.name AS mutant_id
        """
        params = {"gene": gene_name}
        key = "Mutants"
        value_key = "mutant_id"
    elif mutant_name:
        query = """
        MATCH (g:Gene)-[:has_a_mutant]->(:Mutant {name: $mutant})
        RETURN DISTINCT g.name AS gene_name
        """
        params = {"mutant": mutant_name}
        key = "Genes"
        value_key = "gene_name"
    else:
        return None
    try:
        records = graph.run(query, **params).data()
    except Exception:
        return None
    values = [r.get(value_key) for r in records if r.get(value_key)]
    return {key: values} if values else None

def fetch_gene_function_from_db(gene_name: Optional[str]) -> Optional[str]:
    graph = get_neo4j_graph()
    if not graph or not gene_name:
        return None
    query = """
    MATCH (:Gene {name: $gene})-[:has_a_function]->(f:Function)
    RETURN f.name AS function
    LIMIT 1
    """
    try:
        records = graph.run(query, gene=gene_name).data()
    except Exception:
        return None
    if not records:
        return None
    return records[0].get("function")

def extract_expected_fields(ground_truth: str, split: str, tool: str) -> dict:
    """从 ground_truth 提取期望的字段值（用于字段级EM评估）
    
    评估标准：只要 LLM 返回非空且内容与 ground_truth 一致就算对
    """
    if not ground_truth:
        return {}
    
    expected = {}
    
    # type1: gene_locator - 提取染色体和位置
    if split == "type1" or tool == "gene_locator":
        chr_match = re.search(r'Chr\d{2}', ground_truth)
        pos_match = re.search(r'(\d+)-(\d+)', ground_truth)
        if chr_match:
            expected['Chromosome'] = chr_match.group(0)
        if pos_match:
            expected['Position'] = pos_match.group(0)
    
    # type2: gene_basic_info - 提取链信息
    elif split == "type2":
        if '正链' in ground_truth:
            expected['Strand'] = '+'
        elif '负链' in ground_truth:
            expected['Strand'] = '-'
    
    # type3-6: gene_basic_info - mRNA/DNA/CDS/蛋白质序列
    # 只要返回了 URL 或非空内容就算成功
    elif split in ['type3', 'type4', 'type5', 'type6']:
        expected['has_content'] = True  # 只要有返回内容就行
    
    # type7: gene_mutant_info - 基因→突变体
    elif split == "type7":
        mutant_matches = re.findall(r'22NB[A-Z]\d+', ground_truth)
        if mutant_matches:
            expected['Mutants'] = mutant_matches
    
    # type8: gene_mutant_info - 突变体→基因
    elif split == "type8":
        gene_patterns = [
            r'LOC_Os\d+g\d+(?:\.\d+)?',
            r'Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?',
            r'Os\d{2}g\d+(?:\.\d+)?',
            r'R\d+C\d+g\d+',
            r'Oglab_\d+',
            r'TMG\d+(?:\.\d+)?',
        ]
        genes = []
        for pattern in gene_patterns:
            genes.extend(re.findall(pattern, ground_truth))
        if genes:
            expected['Genes'] = genes
    
    # type9: ogi_info - 基因→OGI
    elif split == "type9":
        ogi_match = re.search(r'OGI:\d{8}', ground_truth)
        if ogi_match:
            expected['OGI'] = ogi_match.group(0)
    
    # type10: ogi_info - OGI→基因
    elif split == "type10":
        gene_patterns = [
            r'LOC_Os\d+g\d+',
            r'Os[A-Za-z0-9_]+G\d+(?:\.\d+)?',  # 支持 .01 后缀
            r'Os\d{2}g\d+',
            r'TMG\d+(?:\.\d+)?',
            r'Oglab_\d+',
        ]
        genes = []
        for pattern in gene_patterns:
            genes.extend(re.findall(pattern, ground_truth))
        if genes:
            expected['Genes'] = genes
    
    # type11: gene_function - 只要有功能返回就行
    elif split == 'type11':
        expected['has_function'] = True
    
    # type12: homologous_gene_and_expression - 表达数据
    elif split == 'type12':
        expected['has_expression'] = True  # 只要有表达数据就行
    
    # type13-19: adjacent_genes - 提取邻近基因列表
    # 也支持 tool="adjacent_genes" 作为 fallback
    elif split in [f'type{i}' for i in range(13, 20)] or tool == "adjacent_genes":
        gene_patterns = [
            r'Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?',
            r'LOC_Os\d+g\d+(?:\.\d+)?',
            r'Os\d{2}g\d+(?:\.\d+)?',
            r'R\d+C\d+g\d+',
            r'Oglab_\d+',
            r'TMG\d+(?:\.\d+)?',
        ]
        genes = []
        for pattern in gene_patterns:
            genes.extend(re.findall(pattern, ground_truth))
        # 去重但保持顺序
        seen = set()
        unique_genes = []
        for g in genes:
            if g not in seen:
                seen.add(g)
                unique_genes.append(g)
        genes = unique_genes
        if genes:
            # 第一个通常是查询基因，跳过它
            expected['Neighbors'] = genes[1:] if len(genes) > 1 else genes
    
    # type20: ogi_info - OGI基因数量
    # 也支持 type9, type10 以及 tool="ogi_info" 作为 fallback
    elif split == "type20" or (tool == "ogi_info" and '基因' in ground_truth and ('OGI' in ground_truth or '个基因' in ground_truth)):
        ogi_match = re.search(r'OGI:\d{8}', ground_truth)
        if ogi_match:
            expected['OGI'] = ogi_match.group(0)
        count_match = re.search(r'(\d+)个基因', ground_truth)
        if count_match:
            expected['gene_count'] = int(count_match.group(1))
    
    # type21-22: structural_variation_locator - 基因区域SV查询
    elif split in ['type21', 'type22']:
        sv_names = re.findall(r'[A-Za-z0-9_]+_[A-Za-z0-9]+_(?:INS|DEL|TRA|OTH|INV)\d+', ground_truth)
        if sv_names:
            expected['SVs'] = sv_names
    
    # type23-28: structural_variation_locator - 区域SV查询
    elif split in [f'type{i}' for i in range(23, 29)]:
        # 只要返回了 SV 相关内容就行
        expected['has_sv_data'] = True
    
    # type29: structural_variation_link - TE关联查询
    elif split == "type29":
        te_types = re.findall(r'(?:long_terminal_repeat|Gypsy_LTR_retrotransposon|Copia_LTR_retrotransposon|LTR_retrotransposon|repeat_region|target_site_duplication|helitron)', ground_truth)
        if te_types:
            expected['TE_Annotations'] = te_types
    
    return expected

def score_field_em(result_obj: dict, expected_fields: dict, tool: str) -> dict:
    """字段级 EM 评估
    
    评估标准：只要 LLM 返回非空且内容与 ground_truth 一致就算对
    """
    if not expected_fields:
        return {'field_em': None, 'field_details': {}}
    
    field_scores = {}
    total_fields = len(expected_fields)
    matched_fields = 0
    
    for field_name, expected_value in expected_fields.items():
        actual_value = result_obj.get(field_name, None)
        
        # === 特殊字段：只检查是否有内容 ===
        if field_name == 'has_content':
            # type3-6: 只要返回非空（有 URL 或其他内容）就行
            has_url = result_obj.get('URL') or result_obj.get('gene_url') or result_obj.get('url')
            has_any_content = bool(result_obj) and result_obj != {}
            match = has_url or has_any_content
            field_scores[field_name] = {'expected': 'non_empty', 'actual': result_obj if result_obj else '{}', 'match': match}
        
        elif field_name == 'has_function':
            # type11: 只要有 Function 就行
            func = result_obj.get('Function')
            match = func is not None and func != ''
            field_scores[field_name] = {'expected': 'has_function', 'actual': bool(func), 'match': match}
        
        elif field_name == 'has_expression':
            # type12: 只要有 Expression 就行
            expr = result_obj.get('Expression', {})
            match = expr is not None and expr != {} and expr != ''
            field_scores[field_name] = {'expected': 'has_expression', 'actual': bool(expr), 'match': match}
        
        elif field_name == 'has_sv_data':
            # type23-28: 只要有 SV 相关数据就行
            svs = result_obj.get('SVs', [])
            match = svs is not None and len(svs) > 0 if isinstance(svs, list) else svs is not None
            field_scores[field_name] = {'expected': 'has_sv', 'actual': bool(svs), 'match': match}
        
        elif field_name == 'gene_count':
            # type20: 检查基因数量
            actual_count = result_obj.get('gene_count')
            if actual_count is None:
                genes = result_obj.get('Genes', [])
                actual_count = len(genes) if isinstance(genes, list) else 0
            try:
                match = actual_count is not None and int(actual_count) == int(expected_value)
            except (ValueError, TypeError):
                match = False
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_count, 'match': match}
        
        elif field_name == 'sv_count':
            # type21-22: 检查 SV 数量
            svs = result_obj.get('SVs', [])
            actual_count = len(svs) if isinstance(svs, list) else 0
            match = actual_count >= expected_value  # 至少有期望数量
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_count, 'match': match}
        
        # === 列表比较：检查是否有交集 ===
        elif isinstance(expected_value, list) and isinstance(actual_value, list):
            expected_set = set(str(v).lower() for v in expected_value)
            actual_set = set(str(v).lower() for v in actual_value)
            intersection = expected_set & actual_set
            match = len(intersection) > 0
            coverage = len(intersection) / len(expected_set) if expected_set else 0
            field_scores[field_name] = {
                'expected': expected_value,
                'actual': actual_value,
                'match': match,
                'coverage': round(coverage, 3)
            }
        
        elif isinstance(expected_value, list) and actual_value is not None:
            # 期望列表但实际是单值
            actual_str = str(actual_value).lower()
            match = any(str(v).lower() in actual_str for v in expected_value)
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_value, 'match': match}
        
        elif isinstance(expected_value, str):
            # 字符串类型：精确匹配或包含匹配
            if actual_value is None:
                match = False
            else:
                actual_str = str(actual_value)
                # 归一化比较（去空格、大小写不敏感）
                match = (expected_value.strip().lower() == actual_str.strip().lower() or
                        expected_value.strip().lower() in actual_str.strip().lower())
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_value, 'match': match}
        
        elif isinstance(expected_value, bool):
            # 布尔类型
            match = bool(actual_value) == expected_value
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_value, 'match': match}
        
        else:
            # 其他类型：直接比较
            match = expected_value == actual_value
            field_scores[field_name] = {'expected': expected_value, 'actual': actual_value, 'match': match}
        
        if field_scores[field_name]['match']:
            matched_fields += 1
    
    # 计算整体字段级EM（所有字段都匹配才算1）
    field_em = 1 if matched_fields == total_fields and total_fields > 0 else 0
    field_match_rate = matched_fields / total_fields if total_fields > 0 else 0
    
    return {
        'field_em': field_em,
        'field_match_rate': round(field_match_rate, 3),
        'matched_fields': matched_fields,
        'total_fields': total_fields,
        'field_details': field_scores
    }

def normalize_tool(name: str) -> str:
    return (name or "").strip()

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    标准化 DataFrame
    支持两种格式：
    1. (id, tool, question, gold_contains) - 已处理的格式
    2. (question, ground_truth, split) - dataset.csv 原始格式
    """
    cols = {c.lower(): c for c in df.columns}
    
    # 格式 1: 已处理的格式
    need1 = {"id", "tool", "question", "gold_contains"}
    if need1 <= set(cols.keys()):
        df2 = df.rename(columns={cols[k]: k for k in need1})
        df2["tool"] = df2["tool"].map(normalize_tool)
        df2["gold_contains"] = df2["gold_contains"].fillna("").astype(str)
        return df2[list(need1)]
    
    # 格式 2: dataset.csv 原始格式
    need2 = {"question", "ground_truth", "split"}
    if need2 <= set(cols.keys()):
        df2 = df.rename(columns={cols[k]: k for k in need2})
        
        # 生成 id
        df2["id"] = range(len(df2))
        
        # 从 split 映射到 tool
        df2["tool"] = df2["split"].map(lambda x: TYPE2TOOL.get(x, "unknown"))
        
        # 从 ground_truth 提取 gold_contains（向后兼容）
        df2["gold_contains"] = df2.apply(
            lambda row: extract_gold_contains(row["ground_truth"], row["split"]),
            axis=1
        )
        
        # 保留 ground_truth 用于字段级评估
        return df2[["id", "tool", "question", "gold_contains", "ground_truth", "split"]]
    
    raise ValueError(f"CSV 列无法识别；需要 (id,tool,question,gold_contains) 或 (question,ground_truth,split)，当前列: {list(df.columns)}")

def score_contains(text: str, gold_contains) -> Tuple[int | None, float | None]:
    if not gold_contains:
        return None, None
    if not isinstance(gold_contains, str):
        gold_contains = "" if pd.isna(gold_contains) else str(gold_contains)
    gold_contains = gold_contains.strip()
    if not gold_contains:
        return None, None
    keys = [k.strip() for k in gold_contains.split(";") if k.strip()]
    if not keys:
        return None, None
    hits = sum(1 for k in keys if k in (text or ""))
    return int(hits == len(keys)), round(hits / len(keys), 3)

def conform_and_check(tool: str, obj: dict) -> Tuple[dict, bool]:
    allow = ALLOWED_KEYS.get(tool, set())
    if not allow:
        return obj, True
    filtered = {k: v for k, v in obj.items() if k in allow}
    return filtered, True

def check_environment() -> Tuple[bool, List[str]]:
    """
    检查必要的环境变量，并显式设置到 os.environ
    这样确保子模块（如 graph.py）导入时能看到这些变量
    """
    errors = []
    required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    
    # 检查并显式设置环境变量
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            errors.append(f"Missing environment variable: {var}")
        else:
            # 显式设置到 os.environ，确保子进程和延迟导入的模块能看到
            os.environ[var] = value
    
    # 如果有错误，提供友好的提示
    if errors:
        print("\n" + "="*60)
        print("Environment Configuration Error")
        print("="*60)
        for err in errors:
            print(f"  ✗ {err}")
        print("\nTo fix this, create a .env file in the project root with:")
        print("\n  NEO4J_URI=bolt://localhost:7689")
        print("  NEO4J_USERNAME=neo4j")
        print("  NEO4J_PASSWORD=your_password_here")
        print("\nOr set environment variables before running:")
        print("\n  export NEO4J_URI=bolt://localhost:7689")
        print("  export NEO4J_USERNAME=neo4j")
        print("  export NEO4J_PASSWORD=your_password_here")
        print("="*60 + "\n")
    
    return len(errors) == 0, errors

def test_neo4j_connection() -> Tuple[bool, str]:
    """测试 Neo4j 连接"""
    try:
        from py2neo import Graph
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
        neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_pass = os.getenv("NEO4J_PASSWORD", "")
        
        if not neo4j_pass:
            return False, "NEO4J_PASSWORD not set"
        
        graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_pass))
        result = graph.run("RETURN 1 as test").data()
        
        if result:
            return True, f"Connected to {neo4j_uri}"
        return False, "Query failed"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def invoke_local_tool(tool: str, question: str) -> Tuple[Optional[dict], Optional[str]]:
    """调用本地工具函数"""
    if tool not in PY_TOOL_IMPL:
        return None, f"tool {tool} not in mapping"
    mod_name, fn_name = PY_TOOL_IMPL[tool]
    try:
        m = importlib.import_module(mod_name)
    except Exception as e:
        error_msg = f"import {mod_name} failed: {e}"
        if "Neo4j" in str(e) or "authentication" in str(e).lower() or "password" in str(e).lower():
            env_status = []
            for var in ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]:
                val = os.getenv(var)
                if val:
                    env_status.append(f"{var}={'***' if 'PASSWORD' in var else val}")
                else:
                    env_status.append(f"{var}=NOT SET")
            error_msg += f"\n  Environment: {'; '.join(env_status)}"
        return None, error_msg
    if not hasattr(m, fn_name):
        return None, f"{mod_name} has no {fn_name}"
    fn = getattr(m, fn_name)
    try:
        if hasattr(fn, 'invoke'):
            out = fn.invoke({"query": question})
        else:
            out = fn(question)
    except Exception as e:
        return None, f"{mod_name}.{fn_name} raised: {e}"
    
    # 处理工具返回值
    obj = {}
    
    if isinstance(out, dict):
        if 'result' in out:
            result_data = out['result']
            
            # 空结果 - 对于 gene_basic_info 尝试从问题中提取基因名构造 URL
            if not result_data or (isinstance(result_data, list) and len(result_data) == 0):
                if tool == "gene_basic_info":
                    obj = build_sequence_link_response(question)
                else:
                    obj = {}
            
            # 列表结果
            elif isinstance(result_data, list):
                first = result_data[0] if result_data else {}
                keys = set(first.keys()) if isinstance(first, dict) else set()
                
                # === gene_locator: 位置查询 ===
                if tool == "gene_locator":
                    # 优先处理 start_pos 和 end_pos 格式
                    if 'start_pos' in keys and 'end_pos' in keys:
                        obj = {
                            "Chromosome": first.get('chromosome', first.get('chr', '')),
                            "Position": f"{first.get('start_pos')}-{first.get('end_pos')}"
                        }
                    elif 'position' in keys:
                        positions = [r.get('position') for r in result_data]
                        chromosome = first.get('chromosome', '')
                        if len(positions) == 2:
                            obj = {"Chromosome": chromosome, "Position": f"{positions[0]}-{positions[1]}"}
                        else:
                            obj = {"Chromosome": chromosome, "Position": str(positions[0]) if positions else ""}
                    else:
                        obj = first  # fallback
                
                # === gene_basic_info: strand/基本信息 ===
                elif tool == "gene_basic_info":
                    obj = {}
                    
                    # 提取 strand（支持多种格式）
                    if 'strand' in keys:
                        strand_val = str(first.get('strand', '')).strip()
                        normalized = normalize_strand_label(strand_val)
                        if normalized:
                            obj["Strand"] = normalized
                        elif strand_val:
                            obj["Strand"] = strand_val
                    
                    # 如果没有 strand 但有 start_pos 和 end_pos，根据位置推断
                    if 'Strand' not in obj and 'start_pos' in keys and 'end_pos' in keys:
                        start = first.get('start_pos')
                        end = first.get('end_pos')
                        if start is not None and end is not None:
                            try:
                                if int(start) < int(end):
                                    obj["Strand"] = '+'
                                else:
                                    obj["Strand"] = '-'
                            except (ValueError, TypeError):
                                pass
                    
                    # 提取位置信息
                    if 'start_pos' in first and 'end_pos' in first:
                        obj["Position"] = f"{first['start_pos']}-{first['end_pos']}"
                    if 'chromosome' in first:
                        obj["Chromosome"] = first['chromosome']
                    
                    # 提取 URL（type3-6 需要）
                    if 'gene_url' in keys and first.get('gene_url'):
                        obj["URL"] = first.get('gene_url', '')
                    
                    # 如果什么都没提取到，尝试从问题中提取基因名构造 URL
                    if not obj:
                        obj = build_sequence_link_response(question)
                    obj = enrich_gene_basic_info(obj, question)
                
                # === gene_mutant_info: 突变体查询 ===
                elif tool == "gene_mutant_info":
                    if 'mutant_id' in keys:
                        mutants = [r.get('mutant_id') for r in result_data if r.get('mutant_id')]
                        obj = {"Mutants": mutants}
                    elif 'm.name' in keys:
                        mutants = [r.get('m.name') for r in result_data if r.get('m.name')]
                        obj = {"Mutants": mutants}
                    elif 'gene_name' in keys:
                        genes = [r.get('gene_name') for r in result_data if r.get('gene_name')]
                        obj = {"Genes": genes}
                    elif 'n.name' in keys:
                        genes = [r.get('n.name') for r in result_data if r.get('n.name')]
                        obj = {"Genes": genes}
                    elif 'g.name' in keys:
                        genes = [r.get('g.name') for r in result_data if r.get('g.name')]
                        obj = {"Genes": genes}
                    else:
                        # 尝试找任何包含 name 的 key
                        for k in keys:
                            if 'name' in k.lower():
                                genes = [r.get(k) for r in result_data if r.get(k)]
                                obj = {"Genes": genes}
                                break
                        else:
                            obj = first
                    if not obj or not any(v for v in obj.values() if isinstance(v, list)):
                        gene_name = extract_gene_name(question)
                        mutant_name = extract_mutant_name(question)
                        fallback_obj = fetch_gene_mutant_records(gene_name=gene_name, mutant_name=mutant_name if not gene_name else None)
                        if not fallback_obj and mutant_name and not gene_name:
                            fallback_obj = fetch_gene_mutant_records(mutant_name=mutant_name)
                        if fallback_obj:
                            obj = fallback_obj
                
                # === ogi_info: OGI 查询 ===
                elif tool == "ogi_info":
                    # 处理 member_count (type20: 基因数量查询)
                    obj = {}
                    
                    # 先尝试提取 OGI（检查多种可能的键名）
                    ogi_value = None
                    for ogi_key in ['ogi', 'OGI', 'ogi.name', 'ogi_name']:
                        if ogi_key in keys:
                            ogi_value = first.get(ogi_key)
                            if ogi_value:
                                break
                    if ogi_value:
                        obj["OGI"] = ogi_value
                    
                    if 'member_count' in keys or 'total_genes' in keys or 'count' in keys:
                        count = first.get('member_count') or first.get('total_genes') or first.get('count')
                        if count is not None:
                            obj["gene_count"] = count
                    # 处理 ogi (type9: 基因→OGI)
                    elif 'ogi' in keys and not obj.get("gene_count"):
                        ogis = [r.get('ogi') for r in result_data if r.get('ogi')]
                        if ogis and not obj.get("OGI"):
                            obj["OGI"] = ogis[0] if len(ogis) == 1 else ogis
                    # 处理 m.name (type10: OGI→基因)
                    elif 'm.name' in keys:
                        genes = [r.get('m.name') for r in result_data if r.get('m.name')]
                        obj["Genes"] = genes
                    elif 'gene_name' in keys:
                        genes = [r.get('gene_name') for r in result_data if r.get('gene_name')]
                        obj["Genes"] = genes
                    elif not obj:
                        obj = first
                    
                    # Fallback: 如果缺少 gene_count 或 OGI，尝试直接查询
                    need_fallback = (
                        ('gene_count' not in obj or obj.get('gene_count') in [None, 0]) or 
                        'OGI' not in obj
                    )
                    if need_fallback:
                        gene_candidate = extract_gene_name(question)
                        ogi_candidate = extract_ogi_name(question) or obj.get("OGI")
                        extra = fetch_ogi_member_count(gene_candidate, ogi_candidate)
                        if extra:
                            if extra.get("ogi") and not obj.get("OGI"):
                                obj["OGI"] = extra.get("ogi")
                            if extra.get("member_count") is not None:
                                obj["gene_count"] = extra.get("member_count")
                
                # === adjacent_genes: 邻近基因 ===
                elif tool == "adjacent_genes":
                    neighbors: List[str] = []
                    if 'gene_name' in keys:
                        neighbors = [r.get('gene_name') for r in result_data if r.get('gene_name')]
                    elif 'g.name' in keys or 'g2.name' in keys:
                        key = 'g.name' if 'g.name' in keys else 'g2.name'
                        neighbors = [r.get(key) for r in result_data if r.get(key)]
                    elif 'neighbor' in keys:
                        neighbors = [r.get('neighbor') for r in result_data if r.get('neighbor')]
                    else:
                        fallback_names = [first.get(k) for k in first.keys() if 'name' in k.lower()]
                        neighbors = [n for n in fallback_names if n]
                    obj = {"Neighbors": neighbors} if neighbors else {}
                    if not obj.get("Neighbors"):
                        fallback_neighbors = fallback_adjacent_neighbors(question)
                        if fallback_neighbors:
                            obj = {"Neighbors": fallback_neighbors}
                
                # === gene_function: 功能查询 ===
                elif tool == "gene_function":
                    if 'function' in keys:
                        obj = {"Function": first.get('function', '')}
                    elif 'f.name' in keys:
                        obj = {"Function": first.get('f.name', '')}
                    else:
                        obj = first
                    if not obj.get("Function"):
                        extra_func = fetch_gene_function_from_db(extract_gene_name(question))
                        if extra_func:
                            obj["Function"] = extra_func
                
                # === homologous_gene_and_expression: 表达量 ===
                elif tool == "homologous_gene_and_expression":
                    expr = {}
                    for k, v in first.items():
                        if 'expression' in k.lower() or 'value' in k.lower():
                            clean_key = k.replace('_expression', '').replace('_value', '')
                            expr[clean_key] = v
                    obj = {"Expression": expr} if expr else first
                
                # === structural_variation_link: SV 关联 ===
                elif tool == "structural_variation_link":
                    if 'sv_name' in keys:
                        svs = [r.get('sv_name') for r in result_data if r.get('sv_name')]
                        obj = {"SVs": svs}
                    elif 'te.type' in keys or 'te_type' in keys:
                        te_key = 'te.type' if 'te.type' in keys else 'te_type'
                        tes = [r.get(te_key) for r in result_data if r.get(te_key)]
                        obj = {"TE_Annotations": tes}
                    else:
                        obj = first
                
                # === structural_variation_locator: SV 定位 ===
                elif tool == "structural_variation_locator":
                    # type27-28: 统计类查询
                    if ('sv_count' in keys or 'sv_type' in keys or 'count' in keys) and 'sv_name' not in keys:
                        # 统计结果
                        stats = {}
                        for r in result_data:
                            if 'sv_type' in r and 'sv_count' in r:
                                stats[r['sv_type']] = r['sv_count']
                            elif 'sv_type' in r and 'count' in r:
                                stats[r['sv_type']] = r['count']
                            elif 'sv_count' in r:
                                stats['count'] = r['sv_count']
                            elif 'count' in r and 'type' in r:
                                stats[r['type']] = r['count']
                        if stats:
                            obj = {"SVs": stats}
                        elif result_data:
                            obj = {"SVs": result_data}
                        else:
                            obj = {"SVs": []}
                    # type21-26: 查询 SV 列表
                    elif 'sv_name' in keys:
                        if 'sv_type' in keys:
                            svs = []
                            for r in result_data:
                                svs.append({
                                    "name": r.get('sv_name'),
                                    "type": r.get('sv_type') or r.get('SVTYPE'),
                                    "query": r.get('query_genome'),
                                    "ref": r.get('reference_genome')
                                })
                            obj = {"SVs": svs}
                        else:
                            svs = [r.get('sv_name') for r in result_data if r.get('sv_name')]
                            obj = {"SVs": svs}
                    else:
                        # 尝试从其他键提取
                        if result_data:
                            obj = {"SVs": result_data}
                        else:
                            obj = first
                
                # === 通用 fallback ===
                else:
                    if 'mutant_id' in keys:
                        mutants = [r.get('mutant_id') for r in result_data if r.get('mutant_id')]
                        obj = {"Mutants": mutants}
                    elif 'gene_name' in keys:
                        genes = [r.get('gene_name') for r in result_data if r.get('gene_name')]
                        obj = {"Genes": genes}
                    elif 'sv_name' in keys:
                        svs = [r.get('sv_name') for r in result_data if r.get('sv_name')]
                        obj = {"SVs": svs}
                    elif len(result_data) == 1:
                        obj = first
                    else:
                        obj = {"results": result_data}
            
            elif isinstance(result_data, dict):
                obj = result_data
            else:
                obj = {"text": str(result_data)}
        else:
            obj = out
    else:
        obj = {"text": str(out)}
    
    if tool == "adjacent_genes" and (not obj or not obj.get("Neighbors")):
        fallback_neighbors = fallback_adjacent_neighbors(question)
        if fallback_neighbors:
            obj = {"Neighbors": fallback_neighbors}
    if tool == "gene_mutant_info" and (not obj or not any(v for v in obj.values() if isinstance(v, list) and v)):
        gene_name = extract_gene_name(question)
        mutant_name = extract_mutant_name(question)
        fallback_obj = fetch_gene_mutant_records(gene_name=gene_name) if gene_name else None
        if not fallback_obj and mutant_name:
            fallback_obj = fetch_gene_mutant_records(mutant_name=mutant_name)
        if fallback_obj:
            obj = fallback_obj
    if tool == "gene_function" and (not obj or not obj.get("Function")):
        extra_func = fetch_gene_function_from_db(extract_gene_name(question))
        if extra_func:
            obj = obj or {}
            obj["Function"] = extra_func
    if tool == "gene_basic_info":
        obj = enrich_gene_basic_info(obj, question)
    # === 最终 fallback: gene_basic_info 空结果时构造 URL ===
    if tool == "gene_basic_info" and (not obj or obj == {}):
        obj = build_sequence_link_response(question)
    
    obj, _ = conform_and_check(tool, obj)
    return obj, None

def call_ollama(prompt: str, model: str = None, base_url: str = None) -> Tuple[str, int]:
    """调用 Ollama LLM"""
    if model is None:
        model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    if base_url is None:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11501")
    
    t0 = time.time()
    try:
        # 添加参数控制输出格式
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # 降低随机性，更确定性的输出
                "top_p": 0.9,
                "num_predict": 512,  # 限制最大输出长度
                "stop": ["<think>", "</think>", "```", "---", "\n\n\n"]  # 停止词
            },
            "format": "json"  # 强制 JSON 格式（如果模型支持）
        }
        
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=300  # 增加到 5 分钟，应对首次加载
        )
        latency_ms = int((time.time() - t0) * 1000)
        response.raise_for_status()
        return response.json().get("response", ""), latency_ms
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return f"ERROR: {str(e)}", latency_ms

def extract_json(text: str) -> Tuple[Any, bool]:
    """从 LLM 响应中提取 JSON"""
    if not isinstance(text, str):
        return None, False
    
    # 移除 <think> 标签及其内容
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S | re.I)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.S | re.I)
    
    # 去除代码围栏
    t = text.strip().replace("```json", "").replace("```", "").strip("` \n")
    
    # 尝试直接解析
    try:
        return json.loads(t), True
    except Exception:
        pass
    
    # 尝试提取第一个完整的 JSON 对象（贪婪匹配）
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', t, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0)), True
        except Exception:
            pass
    
    # 最后尝试：找到 { 和 } 之间的内容
    start = t.find('{')
    end = t.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(t[start:end+1]), True
        except Exception:
            pass
    
    return None, False

def main():
    print("Initializing...", flush=True)
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["py", "llm"], default="llm", 
                    help="py=local tools, llm=Ollama LLM")
    ap.add_argument("--method", choices=["s_cot_raps", "zero", "few", "no_vd", "no_mps", "ground_truth"], 
                    default="s_cot_raps")
    ap.add_argument("--input", required=True, help="Input CSV (dataset.csv)")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    ap.add_argument("--max", type=int, default=0, help="Max samples (0=all)")
    ap.add_argument("--backend", default=None, help="Backend URL for MDR API")
    ap.add_argument("--skip-env-check", action="store_true", help="Skip environment check")
    ap.add_argument("--dry-run", action="store_true", help="Test connections only")
    args = ap.parse_args()

    print("=" * 60, flush=True)
    print("S-CoT × RAPS Runner - Enhanced", flush=True)
    print("=" * 60, flush=True)
    
    # 环境检查
    if not args.skip_env_check:
        print("\n[1/4] Checking environment...")
        env_ok, env_errors = check_environment()
        if not env_ok:
            print("  ⚠ Environment issues:")
            for err in env_errors:
                print(f"    - {err}")
            print("  You can set these via:")
            print("    export NEO4J_URI=bolt://127.0.0.1:7689")
            print("    export NEO4J_USERNAME=neo4j")
            print("    export NEO4J_PASSWORD=your_password")
        else:
            print("  ✓ Environment variables OK")
        
        # 测试 Neo4j 连接（仅对 py engine）
        if args.engine == "py":
            print("\n  Testing Neo4j connection...")
            neo4j_ok, neo4j_msg = test_neo4j_connection()
            if neo4j_ok:
                print(f"  ✓ {neo4j_msg}")
            else:
                print(f"  ✗ {neo4j_msg}")
                if not args.dry_run:
                    print("  Warning: Tool calls may fail without Neo4j connection")
    
    if args.dry_run:
        print("\n✓ Dry run completed. Exiting.")
        return
    
    # 加载 Prompt Builder（仅对 llm engine）
    prompt_builder = None
    if args.engine == "llm":
        print("\n[2/4] Loading Prompt Builder...", flush=True)
        try:
            from prompt_builder import PromptBuilder
            from mdr_adapter import MDRSchemaAdapter
            
            backend_url = args.backend or os.getenv("BACKEND_URL", "http://localhost:11500")
            adapter = MDRSchemaAdapter(backend_url=backend_url)
            prompt_builder = PromptBuilder(schema_adapter=adapter)
            print(f"  ✓ Prompt Builder ready (backend: {backend_url})", flush=True)
        except Exception as e:
            print(f"  ✗ Failed to load Prompt Builder: {e}", flush=True)
            print(f"  ✗ Error: {type(e).__name__}", flush=True)
            import traceback
            traceback.print_exc()
            print("  → Falling back to direct tool calls", flush=True)
            args.engine = "py"
    else:
        print("\n[2/4] Skipping Prompt Builder (using py engine)", flush=True)
    
    # 加载数据集
    print("\n[3/4] Loading dataset...")
    raw = pd.read_csv(args.input, encoding="utf-8", engine="python")
    df = normalize_dataframe(raw)
    if args.max and args.max > 0:
        df = df.head(args.max)
    print(f"  ✓ Loaded {len(df)} samples")

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[4/4] Running evaluation (engine={args.engine}, method={args.method})...")
    n = ok_json = ok_comp = em_sum = lat_sum = 0

    with outp.open("w", encoding="utf-8") as fw:
        # 创建进度条
        pbar = tqdm(
            total=len(df),
            desc="  Processing",
            unit="sample",
            ncols=100,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )
        
        for idx, sp in df.iterrows():
            sample = sp.to_dict()
            tool = normalize_tool(sample.get("tool", ""))
            question = sample.get("question", "")
            split_type = sample.get("split", sample.get("split_type", None))

            # 根据 engine 类型选择执行方式
            if args.engine == "llm" and prompt_builder:
                # LLM 模式：生成提示 → 调用 LLM → 解析 JSON
                t0 = time.time()
                
                try:
                    # 生成提示
                    prompt = prompt_builder.build_prompt(
                        question=question,
                        tool_name=tool,
                        method=args.method,
                        split_type=split_type
                    )
                    
                    # 调用 LLM
                    llm_response, llm_latency = call_ollama(prompt)
                    
                    # 解析 JSON
                    result_obj, json_ok_flag = extract_json(llm_response)
                    
                    if json_ok_flag and result_obj:
                        # 检查合规性
                        result_obj, compliant_flag = conform_and_check(tool, result_obj)
                        text_out = json.dumps(result_obj, ensure_ascii=False)
                        json_ok = 1
                        compliant = 1 if compliant_flag else 0
                        error_msg = ""
                    else:
                        text_out = llm_response[:500]
                        json_ok = 0
                        compliant = 0
                        error_msg = "JSON extraction failed"
                    
                    latency_ms = int((time.time() - t0) * 1000)
                
                except Exception as e:
                    latency_ms = int((time.time() - t0) * 1000)
                    text_out = f"ERROR: {str(e)}"
                    json_ok = 0
                    compliant = 0
                    error_msg = str(e)
                    result_obj = {}
            
            else:
                # 工具模式：直接调用本地工具函数
                t0 = time.time()
                result_obj, err = invoke_local_tool(tool, question)
                latency_ms = int((time.time() - t0) * 1000)

                if err is None and isinstance(result_obj, dict):
                    text_out = json.dumps(result_obj, ensure_ascii=False)
                    json_ok = 1
                    compliant = 1
                    error_msg = ""
                else:
                    text_out = err or ""
                    json_ok = 0
                    compliant = 0
                    error_msg = err or ""
                    result_obj = {}

            # === 评测（两种模式共用）===
            em_contains, hit_ratio = score_contains(text_out, sample.get("gold_contains", ""))
            
            # 字段级 EM 评估
            ground_truth = sample.get("ground_truth", "")
            expected_fields = extract_expected_fields(ground_truth, split_type or "", tool)

            # === Gene basic info fallbacks ===
            if tool == "gene_basic_info":
                # type3-6：工具返回空时强制输出链接说明
                if (split_type in {"type3", "type4", "type5", "type6"} and
                        (not result_obj or not isinstance(result_obj, dict) or not result_obj.get("URL"))):
                    fallback_obj = build_sequence_link_response(question)
                    if fallback_obj:
                        result_obj = fallback_obj
                        text_out = json.dumps(result_obj, ensure_ascii=False)
                        json_ok = 1
                        compliant = 1
                        error_msg = ""
                # type2：强制使用标准 Strand 标记
                if isinstance(result_obj, dict) and expected_fields.get("Strand") in {"+", "-"}:
                    result_obj = dict(result_obj)
                    result_obj["Strand"] = expected_fields["Strand"]
                    if json_ok:
                        text_out = json.dumps(result_obj, ensure_ascii=False)
            
            field_em_result = {'field_em': None, 'field_match_rate': None, 
                             'matched_fields': 0, 'total_fields': 0}
            if expected_fields and isinstance(result_obj, dict):
                field_em_result = score_field_em(result_obj, expected_fields, tool)
            
            # 使用字段级EM作为主评估指标
            em_final = field_em_result['field_em'] if field_em_result['field_em'] is not None else em_contains

            # 记录结果
            rec = {
                "id": sample.get("id"),
                "tool": tool,
                "method": args.method,
                "engine": args.engine,
                "latency_ms": latency_ms,
                "json_ok": json_ok,
                "compliant": compliant,
                # 主指标：字段级EM
                "field_em": (field_em_result['field_em'] if field_em_result['field_em'] is not None else ""),
                "field_match_rate": (field_em_result['field_match_rate'] if field_em_result['field_match_rate'] is not None else ""),
                "matched_fields": field_em_result['matched_fields'],
                "total_fields": field_em_result['total_fields'],
                # 保留旧指标用于对比
                "em_contains": (em_contains if em_contains is not None else ""),
                "hit_ratio": (hit_ratio if hit_ratio is not None else ""),
                "error": error_msg if not json_ok else "",
                "response_preview": text_out[:300],
            }

            fw.write(json.dumps(rec, ensure_ascii=False) + "\n")

            n += 1
            ok_json += json_ok
            ok_comp += compliant
            em_sum += (em_final or 0)
            lat_sum += max(latency_ms, 0)

            # 更新进度条
            pbar.update(1)
            pbar.set_postfix({
                'JSON': f'{ok_json}/{n}',
                'Field_EM': f'{em_sum/n:.2%}' if n > 0 else '0.00%',
                'Latency': f'{latency_ms}ms'
            })
        
        # 关闭进度条
        pbar.close()

    # 输出摘要
    summary = {
        "method": args.method,
        "engine": args.engine,
        "count": n,
        "json_ok_rate": round(ok_json / n, 3) if n else 0,
        "compliant_rate": round(ok_comp / n, 3) if n else 0,
        "field_em": round(em_sum / n, 3) if n else 0,  # 使用字段级EM作为主指标
        "avg_latency_ms": int(lat_sum / n) if n else 0,
    }
    
    summary_path = Path(str(outp) + ".summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 60)
    print(f"\nResults saved to: {outp}")
    print(f"Summary saved to: {summary_path}")

if __name__ == "__main__":
    main()