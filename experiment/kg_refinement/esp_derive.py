#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP Derive — Expected Structural Patterns from MDR

从 MDR 和本体中导出硬约束，作为图谱构建的规范依据。

核心定义：
1. ONTOLOGY_SCHEMA: 所有合法的 (source_type, relation, target_type) 三元组 + 基数 κ
2. FILE_TYPE_SCHEMA: 每种文件类型的列→关系映射（Column→DE→DEC→r 链路）
3. VALIDATION_RULES: 跨字段/跨边一致性约束
4. REQUIRED_RELATIONS: 每种实体类型的必需关系（κ=exactly_one）

设计原则：
- 所有约束来源明确（MDR 硬约束 vs 统计软约束）
- 字段到关系的确定性来自注册映射，不是统计，不是 LLM

@author: jingwen.wu
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any
import re


# ============================================================
# 1. 基数约束枚举
# ============================================================

class Cardinality(Enum):
    """
    关系基数约束（MDR 硬约束）
    
    - EXACTLY_ONE: 必须有且仅有一个（如 Gene→chromosome_no→Chromosome）
    - AT_LEAST_ONE: 至少一个（如 Gene→type→Accession，理论上只属于一个品种）
    - ZERO_OR_MORE: 可以没有，也可以有多个（如 Gene→has_a_function→Function）
    """
    EXACTLY_ONE = "exactly_one"
    AT_LEAST_ONE = "at_least_one"
    ZERO_OR_MORE = "zero_or_more"


# ============================================================
# 2. 本体关系定义
# ============================================================

@dataclass(frozen=True)
class OntologyRelation:
    """
    本体中一条合法的关系定义
    
    Attributes:
        source_type: 源节点类型
        relation: 关系类型名称
        target_type: 目标节点类型
        cardinality: 基数约束
        description: 关系描述
    """
    source_type: str
    relation: str
    target_type: str
    cardinality: Cardinality
    description: str = ""


# ============================================================
# 3. 完整本体 Schema（来自 Neo4j 实际图谱结构）
# ============================================================

# 所有合法的 (source_type, relation, target_type, κ) 四元组
# 来源：schema_audit.json 中的 gene_edges_sample + sv_edges_sample + MDR 注册
ONTOLOGY_SCHEMA: List[OntologyRelation] = [
    # ── Gene 的关系 ──────────────────────────────────────────
    # 基本属性（κ=exactly_one: 每个基因必须有且仅有一个）
    OntologyRelation("Gene", "chromosome_no", "Chromosome", Cardinality.EXACTLY_ONE,
                     "基因所在染色体"),
    OntologyRelation("Gene", "start_pos", "Position", Cardinality.EXACTLY_ONE,
                     "基因起始位置"),
    OntologyRelation("Gene", "end_pos", "Position", Cardinality.EXACTLY_ONE,
                     "基因终止位置"),
    OntologyRelation("Gene", "strand_info", "Strand", Cardinality.EXACTLY_ONE,
                     "基因链方向(+/-)"),
    OntologyRelation("Gene", "type", "Accession", Cardinality.EXACTLY_ONE,
                     "基因所属品种/登录号"),

    # 功能与注释（κ=zero_or_more: 可以没有，也可以有多个）
    OntologyRelation("Gene", "has_a_function", "Function", Cardinality.ZERO_OR_MORE,
                     "基因功能注释"),
    OntologyRelation("Gene", "has_a_mutant", "Mutant", Cardinality.ZERO_OR_MORE,
                     "基因关联的突变体"),
    OntologyRelation("Gene", "has_a_transcript", "mRNA", Cardinality.ZERO_OR_MORE,
                     "基因的转录本"),
    OntologyRelation("Gene", "measures_gene_expression", "Expression", Cardinality.ZERO_OR_MORE,
                     "基因表达量"),

    # 同源关系（κ=zero_or_more: 双向，可以有多个同源基因）
    OntologyRelation("Gene", "RBH", "Gene", Cardinality.ZERO_OR_MORE,
                     "互为最佳匹配同源基因"),
    OntologyRelation("Gene", "SBH", "Gene", Cardinality.ZERO_OR_MORE,
                     "单向最佳匹配同源基因"),

    # 结构变异关联
    OntologyRelation("Gene", "in_this_region", "Structural_Variations", Cardinality.ZERO_OR_MORE,
                     "基因区域内的结构变异"),

    # ── OGI 的关系 ──────────────────────────────────────────
    OntologyRelation("OGI", "has_a_gene", "Gene", Cardinality.ZERO_OR_MORE,
                     "OGI索引包含的基因"),

    # ── Structural_Variations 的关系 ────────────────────────
    OntologyRelation("Structural_Variations", "chromosome_no", "Chromosome", Cardinality.EXACTLY_ONE,
                     "结构变异所在染色体"),
    OntologyRelation("Structural_Variations", "query_start_pos", "Position", Cardinality.EXACTLY_ONE,
                     "查询基因组起始位置"),
    OntologyRelation("Structural_Variations", "query_end_pos", "Position", Cardinality.EXACTLY_ONE,
                     "查询基因组终止位置"),
    OntologyRelation("Structural_Variations", "reference_start_pos", "Position", Cardinality.EXACTLY_ONE,
                     "参考基因组起始位置"),
    OntologyRelation("Structural_Variations", "reference_end_pos", "Position", Cardinality.EXACTLY_ONE,
                     "参考基因组终止位置"),
    OntologyRelation("Structural_Variations", "query_genome", "Accession", Cardinality.EXACTLY_ONE,
                     "查询基因组品种"),
    OntologyRelation("Structural_Variations", "reference_genome", "Accession", Cardinality.EXACTLY_ONE,
                     "参考基因组品种"),
    OntologyRelation("Structural_Variations", "in_this_region", "Gene", Cardinality.ZERO_OR_MORE,
                     "结构变异所在区域的基因"),

    # ── TE 的关系 ───────────────────────────────────────────
    OntologyRelation("TE", "contain", "Structural_Variations", Cardinality.ZERO_OR_MORE,
                     "转座元件包含的结构变异"),
]


def get_ontology_lookup() -> Dict[Tuple[str, str], OntologyRelation]:
    """
    构建 (source_type, relation) → OntologyRelation 的查找表
    
    Returns:
        查找字典，key=(source_type, relation)
    """
    lookup = {}
    for rel in ONTOLOGY_SCHEMA:
        lookup[(rel.source_type, rel.relation)] = rel
    return lookup


def get_required_relations(entity_type: str) -> List[OntologyRelation]:
    """
    获取某实体类型的必需关系（κ=EXACTLY_ONE 或 AT_LEAST_ONE）
    
    这些是 MDR 硬约束：如果缺少，则构成 required_missing 缺口。
    
    Args:
        entity_type: 实体类型（如 "Gene", "Structural_Variations"）
    
    Returns:
        必需关系列表
    """
    return [
        rel for rel in ONTOLOGY_SCHEMA
        if rel.source_type == entity_type
        and rel.cardinality in (Cardinality.EXACTLY_ONE, Cardinality.AT_LEAST_ONE)
    ]


def get_optional_relations(entity_type: str) -> List[OntologyRelation]:
    """
    获取某实体类型的可选关系（κ=ZERO_OR_MORE）
    
    这些是统计上常见但非必需的关系：不影响质量分数，只影响补全排序。
    
    Args:
        entity_type: 实体类型
    
    Returns:
        可选关系列表
    """
    return [
        rel for rel in ONTOLOGY_SCHEMA
        if rel.source_type == entity_type
        and rel.cardinality == Cardinality.ZERO_OR_MORE
    ]


def is_legal_triple(source_type: str, relation: str, target_type: str) -> bool:
    """
    检查三元组 (source_type, relation, target_type) 是否在本体中合法
    
    ValidateMDR Layer 1 (Schema Legality) 的核心判断。
    
    Args:
        source_type: 源节点类型
        relation: 关系类型
        target_type: 目标节点类型
    
    Returns:
        True 如果合法
    """
    for rel in ONTOLOGY_SCHEMA:
        if (rel.source_type == source_type
                and rel.relation == relation
                and rel.target_type == target_type):
            return True
    return False


def get_cardinality(source_type: str, relation: str) -> Optional[Cardinality]:
    """
    查询关系的基数约束
    
    Args:
        source_type: 源节点类型
        relation: 关系类型
    
    Returns:
        基数枚举值，不存在则返回 None
    """
    lookup = get_ontology_lookup()
    rel = lookup.get((source_type, relation))
    return rel.cardinality if rel else None


def get_range_type(relation: str, source_type: str = None) -> Optional[str]:
    """
    查询关系的目标类型（Range Type）
    
    用于 type-aware Resolve: KG.Resolve(value, expected_type)
    其中 expected_type = get_range_type(relation)
    
    Args:
        relation: 关系类型
        source_type: 源节点类型（可选，用于消歧）
    
    Returns:
        目标节点类型字符串
    """
    for rel in ONTOLOGY_SCHEMA:
        if rel.relation == relation:
            if source_type is None or rel.source_type == source_type:
                return rel.target_type
    return None


# ============================================================
# 4. 文件类型 Schema — Column→DE→DEC→r 确定性映射
# ============================================================

@dataclass
class ColumnMapping:
    """
    文件列到关系的确定性映射
    
    链路: Column(DataSet.Table.Column) → DataElement → DEC(OC, P) → relation r
    
    Attributes:
        column_index: 列索引（0-based，用于无列头的文件如 BED）
        column_name: 列名（用于有列头的文件如 CSV）
        data_element: 对应的数据元名称
        relation: 映射到的关系类型
        target_type: 目标节点类型
        is_entity_key: 是否是实体主键（如 gene_name 是 Gene 的主键）
        entity_type: 如果是主键，标注实体类型
    """
    column_index: Optional[int] = None
    column_name: Optional[str] = None
    data_element: str = ""
    relation: str = ""
    target_type: str = ""
    is_entity_key: bool = False
    entity_type: str = ""


# 每种文件类型的列→关系映射
# 来源: 生信文件格式标准(BED/VCF) + MDR 注册(DataElement 节点)
FILE_TYPE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    # ── BED 文件：基因基本信息 ─────────────────────────────
    # 标准 BED6 格式: chrom, start, end, name, score, strand
    "bed_gene": {
        "description": "基因基本信息 BED 文件",
        "primary_entity": "Gene",
        "accession_source": "filename",  # 品种名从文件名推断
        "columns": [
            ColumnMapping(column_index=0, column_name="chrom",
                          data_element="Chromosome Number", relation="chromosome_no",
                          target_type="Chromosome"),
            ColumnMapping(column_index=1, column_name="start",
                          data_element="Start Position", relation="start_pos",
                          target_type="Position"),
            ColumnMapping(column_index=2, column_name="end",
                          data_element="End Position", relation="end_pos",
                          target_type="Position"),
            ColumnMapping(column_index=3, column_name="name",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_index=5, column_name="strand",
                          data_element="Gene Strand", relation="strand_info",
                          target_type="Strand"),
        ],
        "allowed_relations": {
            "chromosome_no", "start_pos", "end_pos", "strand_info", "type",
            "has_a_transcript",
        },
    },

    # ── FPKM 文件：基因表达量 ─────────────────────────────
    "fpkm_expression": {
        "description": "基因表达量 FPKM 文件",
        "primary_entity": "Gene",
        "accession_source": "filename",
        "columns": [
            ColumnMapping(column_name="gene_name",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_name="leaf_value",
                          data_element="Gene Expression", relation="measures_gene_expression",
                          target_type="Expression"),
            ColumnMapping(column_name="root_value",
                          data_element="Gene Expression", relation="measures_gene_expression",
                          target_type="Expression"),
            ColumnMapping(column_name="young_ear_value",
                          data_element="Gene Expression", relation="measures_gene_expression",
                          target_type="Expression"),
        ],
        "allowed_relations": {
            "measures_gene_expression",
        },
    },

    # ── RBH 文件：互为最佳匹配同源关系 ──────────────────────
    "rbh_homolog": {
        "description": "RBH 互为最佳匹配同源基因",
        "primary_entity": "Gene",
        "accession_source": "filename",  # 两个品种从文件名推断
        "columns": [
            ColumnMapping(column_index=0, column_name="query_gene",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_index=1, column_name="subject_gene",
                          data_element="Gene ID", relation="RBH",
                          target_type="Gene"),
        ],
        "allowed_relations": {
            "RBH",
        },
    },

    # ── SBH 文件：单向最佳匹配同源关系 ──────────────────────
    "sbh_homolog": {
        "description": "SBH 单向最佳匹配同源基因",
        "primary_entity": "Gene",
        "accession_source": "filename",
        "columns": [
            ColumnMapping(column_index=0, column_name="query_gene",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_index=1, column_name="subject_gene",
                          data_element="Gene ID", relation="SBH",
                          target_type="Gene"),
        ],
        "allowed_relations": {
            "SBH",
        },
    },

    # ── VCF-SV 文件：结构变异 ─────────────────────────────
    "vcf_sv": {
        "description": "结构变异 VCF 文件",
        "primary_entity": "Structural_Variations",
        "accession_source": "filename",
        "columns": [
            ColumnMapping(column_name="CHROM",
                          data_element="Chromosome Number", relation="chromosome_no",
                          target_type="Chromosome"),
            ColumnMapping(column_name="POS",
                          data_element="Start Position", relation="query_start_pos",
                          target_type="Position"),
            ColumnMapping(column_name="ID",
                          data_element="SV ID", relation="",
                          target_type="", is_entity_key=True,
                          entity_type="Structural_Variations"),
            ColumnMapping(column_name="SVTYPE",
                          data_element="Structural Variation Type", relation="",
                          target_type=""),  # 属性，非关系
            ColumnMapping(column_name="SVLENGTH",
                          data_element="Length", relation="",
                          target_type=""),  # 属性，非关系
        ],
        "allowed_relations": {
            "chromosome_no", "query_start_pos", "query_end_pos",
            "reference_start_pos", "reference_end_pos",
            "query_genome", "reference_genome", "in_this_region",
        },
    },

    # ── 功能注释文件 ──────────────────────────────────────
    "function_annotation": {
        "description": "基因功能注释文件",
        "primary_entity": "Gene",
        "accession_source": "none",  # 功能注释不区分品种
        "columns": [
            ColumnMapping(column_name="gene_name",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_name="function",
                          data_element="Protein Function", relation="has_a_function",
                          target_type="Function"),
        ],
        "allowed_relations": {
            "has_a_function",
        },
    },

    # ── 突变体信息文件 ────────────────────────────────────
    "mutant_info": {
        "description": "基因突变体信息文件",
        "primary_entity": "Gene",
        "accession_source": "none",
        "columns": [
            ColumnMapping(column_name="gene_name",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_name="mutant_id",
                          data_element="Mutant ID", relation="has_a_mutant",
                          target_type="Mutant"),
        ],
        "allowed_relations": {
            "has_a_mutant",
        },
    },

    # ── OGI 信息文件 ──────────────────────────────────────
    "ogi_index": {
        "description": "OGI 同源基因索引文件",
        "primary_entity": "OGI",
        "accession_source": "none",
        "columns": [
            ColumnMapping(column_name="ogi_id",
                          data_element="OGI ID", relation="",
                          target_type="", is_entity_key=True, entity_type="OGI"),
            ColumnMapping(column_name="gene_name",
                          data_element="Gene ID", relation="has_a_gene",
                          target_type="Gene"),
            ColumnMapping(column_name="score",
                          data_element="OGI Score", relation="",
                          target_type=""),  # 属性，非关系
        ],
        "allowed_relations": {
            "has_a_gene",
        },
    },

    # ── 转录本信息文件 ────────────────────────────────────
    "transcript_info": {
        "description": "基因转录本信息文件",
        "primary_entity": "Gene",
        "accession_source": "filename",
        "columns": [
            ColumnMapping(column_name="gene_name",
                          data_element="Gene ID", relation="",
                          target_type="", is_entity_key=True, entity_type="Gene"),
            ColumnMapping(column_name="transcript_id",
                          data_element="Transcript Name", relation="has_a_transcript",
                          target_type="mRNA"),
        ],
        "allowed_relations": {
            "has_a_transcript",
        },
    },
}


def get_file_type_schema(file_type: str) -> Optional[Dict[str, Any]]:
    """
    获取文件类型的 schema 定义
    
    Args:
        file_type: 文件类型标识（如 "bed_gene", "fpkm_expression"）
    
    Returns:
        Schema 字典，不存在返回 None
    """
    return FILE_TYPE_SCHEMAS.get(file_type)


def get_column_mapping(file_type: str, column_name: str = None,
                       column_index: int = None) -> Optional[ColumnMapping]:
    """
    查找文件某列的映射关系
    
    这是 InferRelationType 的确定性链路:
    Column(DataSet.Table.Column) → DataElement → DEC → relation r
    
    Args:
        file_type: 文件类型
        column_name: 列名（优先）
        column_index: 列索引（备选）
    
    Returns:
        ColumnMapping 对象
    """
    schema = FILE_TYPE_SCHEMAS.get(file_type)
    if not schema:
        return None

    for col in schema.get("columns", []):
        if column_name and col.column_name == column_name:
            return col
        if column_index is not None and col.column_index == column_index:
            return col
    return None


def is_allowed_relation_in_file_type(file_type: str, relation: str) -> bool:
    """
    检查某关系类型在该文件类型的数据源 schema 中是否被允许
    
    ValidateMDR Layer 1 的子域约束:
    子域允许性由 DataSet/Table 的 schema 注册项给出。
    
    Args:
        file_type: 文件类型
        relation: 关系类型
    
    Returns:
        True 如果允许
    """
    schema = FILE_TYPE_SCHEMAS.get(file_type)
    if not schema:
        return True  # 未知文件类型不做限制
    return relation in schema.get("allowed_relations", set())


# ============================================================
# 5. 值域验证规则（VD + Pattern）
# ============================================================

# 实体类型的命名模式（正则）— 用于 type-aware Resolve
ENTITY_PATTERNS: Dict[str, List[str]] = {
    "Gene": [
        r"^LOC_Os\d{2}g\d+$",          # MSU 格式: LOC_Os01g12345
        r"^Os\d{2}g\d+$",               # RAP 格式: Os01g0123400
        r"^Oglab_\d+$",                 # Ogla 格式
        r"^TMG\d+$",                    # TM 格式
        r"^R\d+C\d+g\d+$",             # R 格式
        r"^22NB[A-Z]\d+$",             # Nipponbare 突变体相关
    ],
    "Chromosome": [
        r"^Chr\d{2}$",                  # Chr01-Chr12
    ],
    "Position": [
        r"^\d+$",                       # 纯数字（基因组坐标）
    ],
    "Strand": [
        r"^[+-]$",                      # + 或 -
    ],
    "OGI": [
        r"^OGI:\d{8}$",                # OGI:00000001
    ],
    "Structural_Variations": [
        r"^[A-Za-z0-9]+_[A-Za-z0-9]+_(DEL|INS|TRA|INV|OTH)\d+$",
    ],
    "Mutant": [
        r"^22NB[A-Z]\d+$",
    ],
    "mRNA": [
        r"^LOC_Os\d{2}g\d+\.\d+$",     # LOC_Os01g12345.1
        r"^Os\d{2}g\d+\.\d+$",         # Os01g0123400.1
    ],
}


def matches_entity_pattern(value: str, entity_type: str) -> bool:
    """
    检查值是否匹配某实体类型的命名模式
    
    Args:
        value: 值字符串
        entity_type: 实体类型
    
    Returns:
        True 如果匹配
    """
    patterns = ENTITY_PATTERNS.get(entity_type, [])
    for pat in patterns:
        if re.match(pat, str(value)):
            return True
    return False


# ============================================================
# 6. 跨字段/跨边一致性约束 (Consistency Legality)
# ============================================================

@dataclass
class ConsistencyRule:
    """
    一致性验证规则
    
    Attributes:
        name: 规则名称
        entity_type: 适用的实体类型
        description: 规则描述
        check_fn_name: 检查函数名（在 graph_constructor 中实现）
    """
    name: str
    entity_type: str
    description: str
    check_fn_name: str


# Layer 3 一致性规则定义
CONSISTENCY_RULES: List[ConsistencyRule] = [
    ConsistencyRule(
        name="position_order",
        entity_type="Gene",
        description="start_pos 必须小于 end_pos",
        check_fn_name="check_position_order",
    ),
    ConsistencyRule(
        name="gene_chromosome_prefix",
        entity_type="Gene",
        description="Gene 名中的染色体编号应与 chromosome_no 一致 "
                    "(如 LOC_Os03g... 应在 Chr03)",
        check_fn_name="check_gene_chromosome_prefix",
    ),
    ConsistencyRule(
        name="sv_position_order",
        entity_type="Structural_Variations",
        description="query_start_pos 必须小于 query_end_pos",
        check_fn_name="check_sv_position_order",
    ),
    ConsistencyRule(
        name="sv_genome_different",
        entity_type="Structural_Variations",
        description="query_genome 和 reference_genome 不应相同",
        check_fn_name="check_sv_genome_different",
    ),
]


def get_consistency_rules(entity_type: str) -> List[ConsistencyRule]:
    """
    获取某实体类型适用的一致性规则
    
    Args:
        entity_type: 实体类型
    
    Returns:
        规则列表
    """
    return [r for r in CONSISTENCY_RULES if r.entity_type == entity_type]


# ============================================================
# 7. 强键 / 弱键 定义
# ============================================================

# 强键: 唯一标识，可用于精确检索
STRONG_KEYS: Dict[str, List[str]] = {
    "Gene": ["name"],              # LOC_Os01g12345 是唯一标识
    "Chromosome": ["name"],        # Chr01 是唯一标识
    "OGI": ["name"],               # OGI:00000001 是唯一标识
    "Mutant": ["name"],            # 突变体 ID 是唯一标识
    "mRNA": ["name"],              # 转录本名称是唯一标识
    "Structural_Variations": ["name"],  # SV 名称是唯一标识
    "Accession": ["name"],         # 品种名是唯一标识
}

# 弱键: 不唯一，只能用于过滤/分桶
WEAK_KEYS: Dict[str, List[str]] = {
    "Gene": ["chromosome_no"],     # 同一染色体上有成千上万个基因
    "Position": ["name"],          # 位置值可能重复（不同基因组坐标系）
    "Strand": ["name"],            # 只有 +/- 两个值
    "Expression": ["leaf_value"],  # 表达值不是唯一标识
    "Function": ["name"],          # 功能描述可能相同
}


def get_strong_key_fields(entity_type: str) -> List[str]:
    """获取实体类型的强键字段"""
    return STRONG_KEYS.get(entity_type, [])


def get_weak_key_fields(entity_type: str) -> List[str]:
    """获取实体类型的弱键字段"""
    return WEAK_KEYS.get(entity_type, [])


# ============================================================
# 8. 辅助: 汇总 ESP 报告
# ============================================================

def derive_esp_report() -> Dict[str, Any]:
    """
    生成完整的 Expected Structural Pattern 报告
    
    Returns:
        {
            "entity_types": [...],
            "relation_count": int,
            "required_relations_by_type": {...},
            "optional_relations_by_type": {...},
            "file_types": [...],
            "consistency_rules": [...],
        }
    """
    entity_types = sorted(set(
        [r.source_type for r in ONTOLOGY_SCHEMA]
        + [r.target_type for r in ONTOLOGY_SCHEMA]
    ))

    required_by_type = {}
    optional_by_type = {}
    for et in entity_types:
        req = get_required_relations(et)
        opt = get_optional_relations(et)
        if req:
            required_by_type[et] = [
                f"{r.relation} -> {r.target_type} ({r.cardinality.value})"
                for r in req
            ]
        if opt:
            optional_by_type[et] = [
                f"{r.relation} -> {r.target_type}"
                for r in opt
            ]

    return {
        "entity_types": entity_types,
        "relation_count": len(ONTOLOGY_SCHEMA),
        "required_relations_by_type": required_by_type,
        "optional_relations_by_type": optional_by_type,
        "file_types": list(FILE_TYPE_SCHEMAS.keys()),
        "consistency_rules": [
            {"name": r.name, "entity_type": r.entity_type, "desc": r.description}
            for r in CONSISTENCY_RULES
        ],
    }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("ESP Derive — Expected Structural Patterns")
    print("=" * 60)

    report = derive_esp_report()

    print(f"\nEntity Types ({len(report['entity_types'])}):")
    for et in report["entity_types"]:
        print(f"  - {et}")

    print(f"\nTotal Relations: {report['relation_count']}")

    print("\nRequired Relations (MDR Hard Constraints):")
    for et, rels in report["required_relations_by_type"].items():
        print(f"  {et}:")
        for r in rels:
            print(f"    - {r}")

    print("\nOptional Relations (Statistical):")
    for et, rels in report["optional_relations_by_type"].items():
        print(f"  {et}:")
        for r in rels:
            print(f"    - {r}")

    print(f"\nFile Types ({len(report['file_types'])}):")
    for ft in report["file_types"]:
        schema = FILE_TYPE_SCHEMAS[ft]
        print(f"  - {ft}: {schema['description']}")

    print(f"\nConsistency Rules ({len(report['consistency_rules'])}):")
    for rule in report["consistency_rules"]:
        print(f"  - [{rule['entity_type']}] {rule['name']}: {rule['desc']}")

    print("\n--- Sample: Gene required relations ---")
    for rel in get_required_relations("Gene"):
        print(f"  {rel.source_type} --[{rel.relation}]--> {rel.target_type}"
              f"  (κ={rel.cardinality.value})")

    print("\n--- Sample: InferRelationType for bed_gene ---")
    for col in FILE_TYPE_SCHEMAS["bed_gene"]["columns"]:
        key_marker = " [PRIMARY KEY]" if col.is_entity_key else ""
        print(f"  col[{col.column_index}] {col.column_name}"
              f" → DE:{col.data_element} → r:{col.relation or 'N/A'}"
              f" → {col.target_type or 'N/A'}{key_marker}")
