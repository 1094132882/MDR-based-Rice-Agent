#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔌 MDR Schema Exporter - 真·动态获取 MDR 元数据

从 Neo4j 数据库动态获取 MDR (Metadata Registry) 规则，包括：
- DEC (数据元概念): Gene ID, Strand, Chromosome 等
- VD (值域): 每个 DEC 的可允许值列表
- MPS (映射): 别名到标准值的映射

⚠️ 重要：
- 使用 config.py 的端口配置（默认 7689）
- 连接成功时打印 "🔌 [MDR] Successfully connected to Neo4j"
- 连接失败时打印 "⚠️ [MDR] Connection Failed! Fallback to static"

Neo4j MDR 节点结构：
- 数据元概念 (DEC): 概念定义
- 数据元: 具体数据元素  
- 值域 (VD): 值域定义
- 值域组: 值域分组
- 可允许值 (PEV): 允许的值列表
- 值含义 (VLM): 值的含义说明

@author: jingwen.wu
@Time: 2025/12
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 确保能导入 config
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入统一配置
from methods.s_cot_raps.config import Config


def get_neo4j_connection():
    """
    获取 Neo4j 连接（使用 Config 配置）
    
    Returns:
        Neo4jGraph 实例，失败返回 None
    """
    # 从 Config 获取配置
    uri = Config.NEO4J_URI
    username = Config.NEO4J_USERNAME
    password = Config.NEO4J_PASSWORD
    
    print(f"🔌 [MDR] Connecting to Neo4j: {uri}")
    
    try:
        # 优先使用 langchain_community
        try:
            from langchain_community.graphs import Neo4jGraph
        except ImportError:
            from langchain_neo4j import Neo4jGraph
        
        graph = Neo4jGraph(
            url=uri, 
            username=username, 
            password=password, 
            refresh_schema=False
        )
        
        # 测试连接是否有效
        graph.query("RETURN 1 as test")
        print(f"🔌 [MDR] Successfully connected to Neo4j (Dynamic Schema Loaded)")
        return graph
        
    except Exception as e:
        print(f"⚠️ [MDR] Connection Failed! Fallback to static JSON.")
        print(f"   Error: {e}")
        print(f"   URI: {uri}")
        return None


class MDRSchemaExporter:
    """
    MDR Schema 导出器
    
    从 Neo4j 数据库动态获取 MDR 元数据。
    当 Neo4j 不可用时，自动回退到静态 Schema。
    
    Usage:
        exporter = MDRSchemaExporter()
        schema = exporter.export_all()
        
        # 获取特定工具的约束
        constraints = exporter.get_constraints_for_tool("gene_basic_info")
    """
    
    def __init__(self, graph=None):
        """
        初始化导出器
        
        Args:
            graph: Neo4j 连接对象（可选，不传则自动连接）
        """
        self.graph = graph or get_neo4j_connection()
        self._cache = {}
        self._use_static_fallback = self.graph is None
        
        if self._use_static_fallback:
            print("   Using static fallback schema")
        else:
            print(f"   Dynamic mode enabled, URI: {Config.NEO4J_URI}")
    
    def export_all(self) -> Dict[str, Any]:
        """
        导出完整的 MDR Schema
        
        Returns:
            {
                "DEC": ["Gene ID", "Strand", ...],
                "VD": {
                    "Strand": ["+", "-"],
                    "Chromosome": ["Chr01", ..., "Chr12"],
                    ...
                },
                "MPS": {
                    "正链": "+",
                    "负链": "-",
                    ...
                },
                "Tools": {...},
                "_source": "dynamic" | "static_fallback"
            }
        """
        if self._cache:
            return self._cache
        
        # 如果 Neo4j 不可用，使用静态回退
        if self._use_static_fallback:
            return self._get_static_fallback_schema()
        
        try:
            schema = {
                "DEC": self._export_dec_list(),
                "VD": self._export_value_domains(),
                "MPS": self._export_mappings(),
                "Tools": self._get_tool_definitions(),
                "DataElements": self._export_data_elements(),
                "_source": "dynamic"
            }
            print(f"✓ [MDR] Schema exported: {len(schema['DEC'])} DECs, {len(schema['VD'])} VDs")
        except Exception as e:
            print(f"⚠️ [MDR] Failed to export from Neo4j: {e}")
            print("   Falling back to static schema...")
            return self._get_static_fallback_schema()
        
        self._cache = schema
        return schema
    
    def _get_static_fallback_schema(self) -> Dict[str, Any]:
        """静态回退 Schema（当 Neo4j 不可用时）"""
        return {
            "DEC": ["Gene ID", "Gene Strand", "Chromosome", "Position", "OGI", "Function", "Expression", "Mutant", "SV", "TE"],
            "VD": {
                "Stand": ["+", "-"],  # 注意：数据库中的命名
                "Strand": ["+", "-"],  # 别名
                "Chromosome": [f"Chr{i:02d}" for i in range(1, 13)],
                "SV_Type": ["DEL", "INS", "TRA", "INV", "OTH"],
                "TE_Type": ["long_terminal_repeat", "Gypsy_LTR_retrotransposon", "Copia_LTR_retrotransposon", "repeat_region"],
                "Accession": ["G46", "Y3551", "Azucena", "Nipponbare", "IR64", "MH63", "ZS97", "DHX2", "R9311"]
            },
            "MPS": {
                "正链": "+", "负链": "-", "正向": "+", "反向": "-",
                "缺失": "DEL", "插入": "INS", "易位": "TRA", "倒位": "INV",
                "上游": "upstream", "下游": "downstream",
                "叶": "leaf", "根": "root", "幼穗": "young_ear", "茎": "stem"
            },
            "Tools": self._get_tool_definitions(),
            "DataElements": {},
            "_source": "static_fallback"
        }
    
    def _export_dec_list(self) -> List[str]:
        """导出数据元概念 (DEC) 列表"""
        result = self.graph.query("""
            MATCH (dec:`数据元概念`)
            RETURN dec.name AS name, dec.identifier AS id, dec.describe AS desc
            ORDER BY dec.identifier
        """)
        return [r['name'] for r in result if r['name']]
    
    def _export_value_domains(self) -> Dict[str, List[str]]:
        """
        导出值域 (VD) 字典
        
        结构: { "Strand": ["+", "-"], "Chromosome": ["Chr01", ...] }
        """
        vd_dict = {}
        
        # 1. 从 MDR 节点获取可枚举的值域
        # 路径: 值域 -> 值域组 -> 可允许值
        try:
            result = self.graph.query("""
                MATCH (vd:`值域`)-[:组]->(vdg:`值域组`)-[:可允许值]->(pv:`可允许值`)
                RETURN vd.name AS vd_name, collect(DISTINCT pv.name) AS values
            """)
            for r in result:
                if r['vd_name'] and r['values']:
                    vd_dict[r['vd_name']] = r['values']
        except Exception as e:
            print(f"   Warning: MDR VD query failed: {e}")
        
        # 2. 从实际数据节点获取值域（补充）
        # 染色体
        try:
            chrom_result = self.graph.query("""
                MATCH (c:Chromosome)
                WHERE c.name STARTS WITH 'Chr' AND SIZE(c.name) = 5
                RETURN DISTINCT c.name AS name
                ORDER BY c.name
            """)
            chromosomes = [r['name'] for r in chrom_result if r['name']]
            if chromosomes:
                vd_dict['Chromosome'] = chromosomes
        except:
            pass
        
        # 品种名 (Accession)
        try:
            acc_result = self.graph.query("""
                MATCH (a:Accession)
                RETURN DISTINCT a.name AS name
                ORDER BY a.name
            """)
            accessions = [r['name'] for r in acc_result if r['name']]
            if accessions:
                vd_dict['Accession'] = accessions
        except:
            pass
        
        # SV 类型
        try:
            sv_result = self.graph.query("""
                MATCH (sv:Structural_Variations)
                RETURN DISTINCT sv.SVTYPE AS svtype
                LIMIT 10
            """)
            sv_types = [r['svtype'] for r in sv_result if r['svtype']]
            if sv_types:
                vd_dict['SV_Type'] = list(set(sv_types))
        except:
            pass
        
        # TE 类型
        try:
            te_result = self.graph.query("""
                MATCH (te:TE)
                RETURN DISTINCT te.type AS te_type
                LIMIT 20
            """)
            te_types = [r['te_type'] for r in te_result if r['te_type']]
            if te_types:
                vd_dict['TE_Type'] = list(set(te_types))
        except:
            pass
        
        return vd_dict
    
    def _export_mappings(self) -> Dict[str, str]:
        """
        导出别名映射 (MPS)
        
        从数据库获取完整的 可允许值 -> 值含义 映射
        结构: { "正链描述": "+", "负链描述": "-", ... }
        """
        mps = {}
        
        # 1. 从 MDR 节点获取值含义映射（完整版）
        try:
            result = self.graph.query("""
                MATCH (pv:`可允许值`)-[:值含义]->(vm:`值含义`)
                RETURN pv.name AS canonical, vm.name AS meaning
            """)
            for r in result:
                if r['canonical'] and r['meaning']:
                    # 值含义（描述）-> 可允许值（标准值）
                    meaning = r['meaning']
                    canonical = r['canonical']
                    mps[meaning] = canonical
                    
                    # 提取简短映射（如从长描述中提取关键词）
                    # 注意：必须检查 canonical 值来确定正确的映射
                    if canonical == '+':
                        mps['正链'] = '+'
                        mps['正向'] = '+'
                    elif canonical == '-':
                        mps['负链'] = '-'
                        mps['反向'] = '-'
                    elif canonical == 'TRA':
                        mps['易位'] = 'TRA'
                    elif canonical == 'C':
                        mps['核心'] = 'C'
                        mps['核心基因'] = 'C'
                    elif canonical == 'D':
                        mps['非核心'] = 'D'
                        mps['非核心基因'] = 'D'
                    elif canonical == 'S':
                        mps['特定'] = 'S'
                        mps['特定基因'] = 'S'
                        
            print(f"   Loaded {len(mps)} MPS mappings from database")
        except Exception as e:
            print(f"   Warning: MDR MPS query failed: {e}")
        
        # 2. 添加常见的中文别名映射（补充）
        chinese_mappings = {
            # 链方向（确保有）
            "正链": "+", "负链": "-",
            "正向": "+", "反向": "-",
            "forward": "+", "reverse": "-",
            "plus": "+", "minus": "-",
            # 染色体
            "一号染色体": "Chr01", "二号染色体": "Chr02", "三号染色体": "Chr03", 
            "四号染色体": "Chr04", "五号染色体": "Chr05", "六号染色体": "Chr06",
            "七号染色体": "Chr07", "八号染色体": "Chr08", "九号染色体": "Chr09",
            "十号染色体": "Chr10", "十一号染色体": "Chr11", "十二号染色体": "Chr12",
            "一号": "01", "二号": "02", "三号": "03", "四号": "04",
            "五号": "05", "六号": "06", "七号": "07", "八号": "08",
            "九号": "09", "十号": "10", "十一号": "11", "十二号": "12",
            # SV 类型
            "缺失": "DEL", "插入": "INS", "易位": "TRA", "倒位": "INV", "其他": "OTH",
            "deletion": "DEL", "insertion": "INS", "translocation": "TRA", "inversion": "INV",
            # OGI Class
            "核心基因": "C", "非核心基因": "D", "特定基因": "S",
            # 同源关系
            "互为最佳匹配": "RBH", "单向最佳匹配": "SBH",
            # 组织
            "叶": "leaf", "根": "root", "幼穗": "young_ear", "茎": "stem",
            "叶片": "leaf", "根部": "root", "穗": "panicle",
            # 方向
            "上游": "upstream", "下游": "downstream",
        }
        
        # 用补充映射更新（不覆盖数据库映射）
        for k, v in chinese_mappings.items():
            if k not in mps:
                mps[k] = v
        
        return mps
    
    def _export_data_elements(self) -> Dict[str, Dict[str, Any]]:
        """
        导出数据元详情
        
        结构: { "Gene Strand": {"vd": "Stand", "dec": "Gene Strand", ...} }
        """
        try:
            result = self.graph.query("""
                MATCH (de:`数据元`)-[:值域]->(vd:`值域`)
                OPTIONAL MATCH (de)-[:数据元概念]->(dec:`数据元概念`)
                RETURN de.name AS de_name, de.identifier AS de_id,
                       vd.name AS vd_name, vd.indefinite AS vd_type,
                       dec.name AS dec_name
            """)
            
            elements = {}
            for r in result:
                if r['de_name']:
                    elements[r['de_name']] = {
                        "identifier": r['de_id'],
                        "value_domain": r['vd_name'],
                        "vd_type": r['vd_type'],  # "不可枚举值" 或 null
                        "dec": r['dec_name']
                    }
            return elements
        except:
            return {}
    
    def _get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        获取工具定义（与数据元的映射关系）
        
        这部分是静态定义，描述每个工具需要的输入/输出字段
        """
        return {
            "gene_basic_info": {
                "in": ["gene_name"],
                "out": ["Gene", "Chromosome", "Position", "Strand", "Transcripts", "URL"],
                "vd_constraints": {
                    "Strand": "Stand",
                    "Chromosome": "Chromosome"
                },
                "description": "查询基因基本信息（位置、链、转录本、序列链接）"
            },
            "gene_function": {
                "in": ["gene_name"],
                "out": ["Gene", "Function"],
                "description": "查询基因功能注释"
            },
            "gene_locator": {
                "in": ["accession", "chromosome", "start", "end"],
                "out": ["Genes", "Region", "gene_count"],
                "vd_constraints": {
                    "Accession": "Accession",
                    "Chromosome": "Chromosome"
                },
                "description": "查询某品种某染色体某区域内的基因"
            },
            "gene_mutant_info": {
                "in": ["gene_name", "mutant_id"],
                "out": ["Gene", "Mutants", "Mutant", "Genes", "mutant_count"],
                "description": "查询基因突变体信息或突变体关联的基因（双向）"
            },
            "ogi_info": {
                "in": ["gene_name", "ogi_id"],
                "out": ["Gene", "OGI", "Genes", "gene_count"],
                "vd_constraints": {
                    "OGI": "OGI ID"
                },
                "description": "查询OGI同源基因索引信息"
            },
            "adjacent_genes": {
                "in": ["gene_name", "direction", "distance", "k"],
                "out": ["TargetGene", "Neighbors", "Direction", "neighbor_count"],
                "description": "查询基因的上下游邻近基因"
            },
            "homologous_gene_and_expression": {
                "in": ["gene_name"],
                "out": ["Gene", "Expression", "leaf", "root", "panicle", "young_ear", "stem"],
                "vd_constraints": {
                    "Expression": "Gene Expression"
                },
                "description": "查询基因同源信息和表达量"
            },
            "structural_variation_link": {
                "in": ["sv_name"],
                "out": ["SV", "TE_Annotations"],
                "vd_constraints": {
                    "TE_Type": "Transposable Elements Type"
                },
                "description": "查询结构变异关联的转座元件"
            },
            "structural_variation_locator": {
                "in": ["gene_name", "accession", "chromosome", "start", "end", "sv_type"],
                "out": ["Gene", "SVs", "sv_count", "Region", "longest_sv"],
                "vd_constraints": {
                    "SV_Type": "Structural Variation Type",
                    "Accession": "Accession"
                },
                "description": "查询某基因或某区域内的结构变异"
            }
        }
    
    def get_vd_for_field(self, field_name: str) -> Optional[List[str]]:
        """
        获取指定字段的值域
        
        Args:
            field_name: 字段名（如 "Strand", "Chromosome"）
        
        Returns:
            可允许值列表，如 ["+", "-"]
        """
        schema = self.export_all()
        return schema.get("VD", {}).get(field_name)
    
    def get_constraints_for_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        获取指定工具的所有约束
        
        Args:
            tool_name: 工具名（如 "gene_basic_info"）
        
        Returns:
            {
                "vd_constraints": {"Strand": ["+", "-"], ...},
                "mps": {"正链": "+", ...},
                "required_fields": ["Gene"],
                ...
            }
        """
        schema = self.export_all()
        tool_def = schema.get("Tools", {}).get(tool_name, {})
        
        # 获取该工具相关的值域约束
        vd_constraints = {}
        for field, vd_name in tool_def.get("vd_constraints", {}).items():
            values = schema.get("VD", {}).get(vd_name) or schema.get("VD", {}).get(field)
            if values:
                vd_constraints[field] = values
        
        return {
            "tool": tool_name,
            "description": tool_def.get("description", ""),
            "input_fields": tool_def.get("in", []),
            "output_fields": tool_def.get("out", []),
            "vd_constraints": vd_constraints,
            "mps": schema.get("MPS", {})
        }


# ============== 单例模式 ==============
_exporter_instance = None


def get_mdr_schema(force_refresh: bool = False) -> Dict[str, Any]:
    """
    获取 MDR Schema（单例）
    
    Args:
        force_refresh: 是否强制刷新缓存
    
    Returns:
        完整的 MDR Schema 字典
    """
    global _exporter_instance
    
    if _exporter_instance is None or force_refresh:
        _exporter_instance = MDRSchemaExporter()
    
    return _exporter_instance.export_all()


def get_tool_constraints(tool_name: str) -> Dict[str, Any]:
    """
    获取工具约束（便捷函数）
    
    Args:
        tool_name: 工具名
    
    Returns:
        工具约束字典
    """
    global _exporter_instance
    
    if _exporter_instance is None:
        _exporter_instance = MDRSchemaExporter()
    
    return _exporter_instance.get_constraints_for_tool(tool_name)


# ============== 便捷函数：load_mdr_schema ==============
def load_mdr_schema() -> Dict[str, Any]:
    """
    加载 MDR Schema（供 mdr_adapter.py 调用）
    
    这是主要的入口函数，会：
    1. 尝试从 Neo4j 动态加载
    2. 失败时回退到静态 Schema
    3. 打印清晰的连接状态日志
    
    Returns:
        MDR Schema 字典
    """
    return get_mdr_schema(force_refresh=True)


if __name__ == "__main__":
    # 测试导出
    print("=" * 60)
    print("🔌 MDR Schema Export Test")
    print("=" * 60)
    
    # 打印配置
    Config.print_config()
    
    print("\n=== Exporting MDR Schema ===\n")
    exporter = MDRSchemaExporter()
    schema = exporter.export_all()
    
    print(f"\n📊 Schema Source: {schema.get('_source', 'unknown')}")
    
    print(f"\nDEC ({len(schema['DEC'])} items):")
    for dec in schema['DEC'][:10]:
        print(f"  - {dec}")
    if len(schema['DEC']) > 10:
        print(f"  ... and {len(schema['DEC']) - 10} more")
    
    print(f"\nVD ({len(schema['VD'])} domains):")
    for vd_name, values in list(schema['VD'].items())[:5]:
        print(f"  - {vd_name}: {values[:5]}{'...' if len(values) > 5 else ''}")
    
    print(f"\nMPS ({len(schema['MPS'])} mappings):")
    for alias, canonical in list(schema['MPS'].items())[:10]:
        print(f"  - {alias} -> {canonical}")
    
    print("\n=== Tool Constraints Test ===\n")
    constraints = exporter.get_constraints_for_tool("gene_basic_info")
    print(f"gene_basic_info constraints:")
    print(f"  VD: {constraints['vd_constraints']}")
    print(f"  MPS (sample): {list(constraints['mps'].items())[:5]}")
