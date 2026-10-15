#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graph-Centric Incremental KG Constructor (Algorithm 2)

图谱中心的增量知识图谱构建算法。

核心思想:
    图谱是跨文件的共享状态机（实体注册表 + 关系记忆）。
    处理新文件时先查图谱（这个实体已经有什么），再决定能补什么。

算法流程:
    for each data_file d_t:
        E_t = ExtractEntities(d_t, M)
        for ei in E_t:
            ei_node = KG.Resolve(ei.value, ei.type)         # 图谱实体解析
            context  = KG.GetContext(ei_node, M)             # 图谱上下文获取
            for (field, value) in d_t.FieldsFor(ei):
                r = InferRelationType(field, file_type, M)   # 确定性映射
                ej = KG.Resolve(value, RangeType(r))         # type-aware
                if conflict? → MarkConflict                  # 基数感知
                if ValidateMDR(ei, r, ej, M, context):       # 三层验证
                    KG.Add(ei, r, ej)

设计原则:
    1. Type-aware Resolve: 避免跨类型误合并
    2. Cardinality-aware Conflict: κ=exactly_one 才是冲突
    3. Hard vs Soft Gaps: required_missing 来自 MDR 硬约束
    4. 确定性字段映射: Column→DE→DEC→r, 不是猜测
    5. 子域约束显式来源: DataSet/Table schema 注册
    6. 冲突是检测能力: conflict_detected 衡量检测能力

@author: jingwen.wu
"""
import re
import logging
import time
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

# 路径设置：把 kg_refinement 目录加入 sys.path，直接导入同目录模块
# 这样完全绕开 experiment 包的初始化（避免 tools/__init__.py 的循环导入）
_THIS_DIR = str(Path(__file__).resolve().parent)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from esp_derive import (
    Cardinality,
    OntologyRelation,
    ONTOLOGY_SCHEMA,
    FILE_TYPE_SCHEMAS,
    ENTITY_PATTERNS,
    CONSISTENCY_RULES,
    get_ontology_lookup,
    get_required_relations,
    get_optional_relations,
    is_legal_triple,
    get_cardinality,
    get_range_type,
    get_column_mapping,
    get_file_type_schema,
    is_allowed_relation_in_file_type,
    matches_entity_pattern,
    get_strong_key_fields,
    get_consistency_rules,
)

logger = logging.getLogger(__name__)


# ============================================================
# 1. 数据结构
# ============================================================

@dataclass
class KGNode:
    """
    知识图谱中的节点
    
    Attributes:
        node_id: 唯一标识 (自动生成: "{type}::{value}")
        entity_type: 实体类型 (Gene, Chromosome, etc.)
        value: 主键值 (LOC_Os01g12345, Chr01, etc.)
        properties: 额外属性 (如 SVTYPE, score 等)
        source_files: 创建/更新该节点的来源文件列表
        relation_count: 该节点已有的关系数量（用于 Resolve 多候选打平局）
    """
    node_id: str
    entity_type: str
    value: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_files: List[str] = field(default_factory=list)
    relation_count: int = 0


@dataclass
class KGEdge:
    """
    知识图谱中的边
    
    Attributes:
        source_id: 源节点 ID
        relation: 关系类型
        target_id: 目标节点 ID
        source_file: 来源文件
        timestamp: 写入时间
    """
    source_id: str
    relation: str
    target_id: str
    source_file: str = ""
    timestamp: float = 0.0


@dataclass
class Conflict:
    """
    冲突记录
    
    单值关系(κ=exactly_one)的两个不同目标构成冲突。
    冲突不是"错误"，是"系统检测到数据源不一致"。
    
    Attributes:
        entity_id: 实体节点 ID
        relation: 冲突的关系类型
        existing_target_id: 已有目标节点 ID
        new_target_id: 新的目标节点 ID
        existing_source: 已有边的来源文件
        new_source: 新边的来源文件
    """
    entity_id: str
    relation: str
    existing_target_id: str
    new_target_id: str
    existing_source: str = ""
    new_source: str = ""


@dataclass
class EntityContext:
    """
    图谱上下文 — KG.GetContext() 的返回值
    
    Attributes:
        existing_rels: 已有的关系 {relation: [target_id, ...]}
        required_missing: MDR 硬约束要求但尚缺的关系列表 (影响质量分数)
        optional_candidates: 统计上常见但非必需的关系列表 (只影响补全排序)
        subdomain: 所属子域 (来源文件类型)
    """
    existing_rels: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    required_missing: List[str] = field(default_factory=list)
    optional_candidates: List[str] = field(default_factory=list)
    subdomain: str = ""


@dataclass
class ValidationResult:
    """
    ValidateMDR 的验证结果
    
    Attributes:
        passed: 是否通过
        layer: 失败在哪一层 (0=通过, 1=schema, 2=value, 3=consistency)
        reason: 失败原因描述
    """
    passed: bool
    layer: int = 0
    reason: str = ""


@dataclass
class DataRecord:
    """
    一条数据记录（从文件中提取）
    
    Attributes:
        entity_key: 实体主键值 (如 "LOC_Os01g12345")
        entity_type: 实体类型 (如 "Gene")
        fields: 字段值列表 [(field_name, value), ...]
        file_type: 来源文件类型
        file_name: 来源文件名
        accession: 品种名 (从文件名推断，可选)
    """
    entity_key: str
    entity_type: str
    fields: List[Tuple[str, str]]
    file_type: str
    file_name: str = ""
    accession: str = ""


# ============================================================
# 2. InMemoryKG — 内存知识图谱
# ============================================================

class InMemoryKG:
    """
    内存知识图谱 — Algorithm 2 的中心数据结构
    
    提供四个核心能力:
    1. Resolve: type-aware 实体解析
    2. GetContext: 上下文获取 (已有关系 + 缺口检测)
    3. Add: 写入新边
    4. MarkConflict: 冲突标记
    """

    def __init__(self):
        # 节点存储: node_id → KGNode
        self.nodes: Dict[str, KGNode] = {}
        # 边存储: [(source_id, relation, target_id, source_file)]
        self.edges: List[KGEdge] = []
        # 边索引: source_id → [KGEdge, ...]
        self._edge_index: Dict[str, List[KGEdge]] = defaultdict(list)
        # 冲突队列
        self.conflicts: List[Conflict] = []
        # 重复警告
        self.duplicate_warnings: List[Dict[str, str]] = []
        # 统计
        self.stats = {
            "resolve_hit": 0,       # Resolve 命中已有节点的次数
            "resolve_miss": 0,      # Resolve 创建新节点的次数
            "edges_added": 0,       # 成功写入的边数
            "edges_skipped_dup": 0, # 因完全重复跳过的边数
            "edges_skipped_conflict": 0,  # 因冲突跳过的边数
            "validation_passed": 0, # 验证通过数
            "validation_failed_l1": 0,  # Layer 1 失败数
            "validation_failed_l2": 0,  # Layer 2 失败数
            "validation_failed_l3": 0,  # Layer 3 失败数
        }

    # ── Resolve: type-aware 实体解析 ─────────────────────────

    def resolve(self, value: str, expected_type: str,
                source_file: str = "") -> KGNode:
        """
        Type-aware 实体解析
        
        在 KG 中查找 (type, primary_key) 匹配的节点。
        找到 → 返回已有节点。
        找不到 → 创建新节点，注册进 KG。
        
        设计原则:
        - type-aware: 避免跨类型误合并
        - 唯一键策略: (type, value) 精确匹配
        - 多候选时选关系数最多的节点
        
        Args:
            value: 实体值 (如 "LOC_Os01g12345", "Chr01")
            expected_type: 期望的实体类型
            source_file: 来源文件名
        
        Returns:
            KGNode 对象
        """
        node_id = f"{expected_type}::{value}"

        if node_id in self.nodes:
            # 命中: 返回已有节点
            node = self.nodes[node_id]
            if source_file and source_file not in node.source_files:
                node.source_files.append(source_file)
            self.stats["resolve_hit"] += 1
            return node

        # 未命中: 创建新节点
        node = KGNode(
            node_id=node_id,
            entity_type=expected_type,
            value=value,
            source_files=[source_file] if source_file else [],
        )
        self.nodes[node_id] = node
        self.stats["resolve_miss"] += 1
        return node

    # ── GetContext: 上下文获取 ─────────────────────────────────

    def get_context(self, node: KGNode) -> EntityContext:
        """
        获取节点的图谱上下文
        
        核心能力:
        1. 已有关系列表 (用于冲突检测和重复跳过)
        2. 缺口检测: required_missing (MDR 硬约束缺失)
        3. 可选候选: optional_candidates (统计上常见但非必需)
        
        设计原则:
        - required_missing 来自 MDR 硬约束 (κ=EXACTLY_ONE / AT_LEAST_ONE)
        - optional_candidates 来自统计 (κ=ZERO_OR_MORE)
        - 统计不变规范
        
        Args:
            node: 要查询的节点
        
        Returns:
            EntityContext 对象
        """
        ctx = EntityContext()

        # 1. 收集已有关系
        for edge in self._edge_index.get(node.node_id, []):
            ctx.existing_rels[edge.relation].append(edge.target_id)

        # 2. 计算 required_missing (MDR 硬约束)
        required = get_required_relations(node.entity_type)
        for rel in required:
            if rel.relation not in ctx.existing_rels:
                ctx.required_missing.append(rel.relation)

        # 3. 计算 optional_candidates (统计上常见)
        optional = get_optional_relations(node.entity_type)
        for rel in optional:
            if rel.relation not in ctx.existing_rels:
                ctx.optional_candidates.append(rel.relation)

        return ctx

    # ── Add: 写入边 ───────────────────────────────────────────

    def add_edge(self, source: KGNode, relation: str,
                 target: KGNode, source_file: str = "") -> bool:
        """
        向 KG 写入一条边
        
        Args:
            source: 源节点
            relation: 关系类型
            target: 目标节点
            source_file: 来源文件
        
        Returns:
            True 如果成功写入
        """
        edge = KGEdge(
            source_id=source.node_id,
            relation=relation,
            target_id=target.node_id,
            source_file=source_file,
            timestamp=time.time(),
        )
        self.edges.append(edge)
        self._edge_index[source.node_id].append(edge)

        # 更新节点的关系计数
        source.relation_count += 1
        target.relation_count += 1

        self.stats["edges_added"] += 1
        return True

    # ── MarkConflict: 冲突标记 ─────────────────────────────────

    def mark_conflict(self, entity: KGNode, relation: str,
                      existing_target_id: str, new_target_id: str,
                      existing_source: str = "", new_source: str = ""):
        """
        标记一个冲突 (κ=exactly_one 的关系指向不同目标)
        
        冲突进入审计队列，不静默覆盖也不静默丢弃。
        
        Args:
            entity: 实体节点
            relation: 冲突的关系类型
            existing_target_id: 已有目标
            new_target_id: 新目标
            existing_source: 已有边的来源文件
            new_source: 新边的来源文件
        """
        conflict = Conflict(
            entity_id=entity.node_id,
            relation=relation,
            existing_target_id=existing_target_id,
            new_target_id=new_target_id,
            existing_source=existing_source,
            new_source=new_source,
        )
        self.conflicts.append(conflict)
        self.stats["edges_skipped_conflict"] += 1

    # ── 查询辅助 ──────────────────────────────────────────────

    def has_edge(self, source_id: str, relation: str, target_id: str) -> bool:
        """检查特定边是否已存在"""
        for edge in self._edge_index.get(source_id, []):
            if edge.relation == relation and edge.target_id == target_id:
                return True
        return False

    def get_edges_by_relation(self, source_id: str, relation: str) -> List[KGEdge]:
        """获取某节点某关系类型的所有边"""
        return [
            e for e in self._edge_index.get(source_id, [])
            if e.relation == relation
        ]

    def node_count(self) -> int:
        """节点总数"""
        return len(self.nodes)

    def edge_count(self) -> int:
        """边总数"""
        return len(self.edges)


# ============================================================
# 3. InferRelationType — 确定性字段→关系映射
# ============================================================

def infer_relation_type(field_name: str, file_type: str,
                        field_index: int = None) -> Optional[Tuple[str, str]]:
    """
    确定性推断字段到关系类型的映射
    
    链路: Column(DataSet.Table.Column) → DataElement → DEC(OC, P) → relation r
    
    来源:
    1. 文件格式标准 (BED col2 → start_pos, VCF CHROM → chromosome_no)
    2. MDR 注册 (DataElement 节点)
    都不行 → return None (不猜)
    
    Args:
        field_name: 字段名/列名
        file_type: 文件类型标识
        field_index: 列索引 (用于无列头的文件如 BED)
    
    Returns:
        (relation, target_type) 元组，或 None
    """
    # 优先: 按列名查找
    mapping = get_column_mapping(file_type, column_name=field_name)
    if mapping and mapping.relation:
        return (mapping.relation, mapping.target_type)

    # 其次: 按列索引查找 (无列头文件)
    if field_index is not None:
        mapping = get_column_mapping(file_type, column_index=field_index)
        if mapping and mapping.relation:
            return (mapping.relation, mapping.target_type)

    # 都不行 → 不猜
    return None


# ============================================================
# 4. ValidateMDR — 三层验证
# ============================================================

class MDRValidator:
    """
    MDR 三层验证器
    
    Layer 1: Schema Legality (模式合法性)
        - (ei.type, r, ej.type) 在本体中合法
        - 该 file_type 的注册 schema 允许这种 DEC
    
    Layer 2: Value Legality (值合法性)
        - ej.value 在 VD 允许范围内
        - 格式匹配 MPS/正则
    
    Layer 3: Consistency Legality (一致性合法性)
        - start_pos < end_pos
        - Gene 名前缀与 Chromosome 编号一致
        - 利用 context.existing_rels 交叉验证
    """

    def __init__(self, vd: Dict[str, list] = None, mps: Dict[str, str] = None):
        """
        初始化验证器
        
        Args:
            vd: 值域字典 {"Strand": ["+", "-"], ...}
            mps: 别名映射 {"正链": "+", ...}
        """
        self.vd = vd or {}
        self.mps = mps or {}

    def validate(self, source: KGNode, relation: str, target: KGNode,
                 context: EntityContext, file_type: str = "") -> ValidationResult:
        """
        执行三层验证
        
        Args:
            source: 源节点
            relation: 关系类型
            target: 目标节点
            context: 源节点的上下文
            file_type: 来源文件类型
        
        Returns:
            ValidationResult
        """
        # Layer 1: Schema Legality
        result = self._check_schema_legality(source, relation, target, file_type)
        if not result.passed:
            return result

        # Layer 2: Value Legality
        result = self._check_value_legality(target)
        if not result.passed:
            return result

        # Layer 3: Consistency Legality
        result = self._check_consistency(source, relation, target, context)
        if not result.passed:
            return result

        return ValidationResult(passed=True, layer=0)

    def _check_schema_legality(self, source: KGNode, relation: str,
                               target: KGNode, file_type: str) -> ValidationResult:
        """
        Layer 1: 模式合法性
        
        检查:
        1. (source.type, relation, target.type) 在本体中合法
        2. 该 file_type 的 schema 允许这种关系
        """
        # 1a. 本体合法性
        if not is_legal_triple(source.entity_type, relation, target.entity_type):
            return ValidationResult(
                passed=False, layer=1,
                reason=f"Triple ({source.entity_type}, {relation}, "
                       f"{target.entity_type}) not in ontology"
            )

        # 1b. 文件类型子域约束
        if file_type and not is_allowed_relation_in_file_type(file_type, relation):
            return ValidationResult(
                passed=False, layer=1,
                reason=f"Relation '{relation}' not allowed in file type '{file_type}'"
            )

        return ValidationResult(passed=True)

    def _check_value_legality(self, target: KGNode) -> ValidationResult:
        """
        Layer 2: 值合法性
        
        检查:
        1. 目标值在 VD 允许范围内
        2. 格式匹配实体类型的命名模式
        """
        entity_type = target.entity_type
        value = target.value

        # 2a. 检查可枚举值域 (Strand, SV_Type 等)
        vd_key = self._get_vd_key_for_type(entity_type)
        if vd_key and vd_key in self.vd:
            allowed = self.vd[vd_key]
            # 先检查原值
            if value in allowed:
                pass  # OK
            # 再检查别名映射后的值
            elif self.mps.get(value, value) in allowed:
                pass  # OK after normalization
            else:
                return ValidationResult(
                    passed=False, layer=2,
                    reason=f"Value '{value}' not in VD[{vd_key}]: "
                           f"{allowed[:5]}{'...' if len(allowed) > 5 else ''}"
                )

        # 2b. 检查命名模式 (Pattern)
        if entity_type in ENTITY_PATTERNS:
            if not matches_entity_pattern(value, entity_type):
                # Position 类型的纯数字不需要严格模式匹配
                if entity_type == "Position" and value.isdigit():
                    pass  # OK
                # Function/Expression 没有严格模式
                elif entity_type in ("Function", "Expression", "TE"):
                    pass  # OK
                else:
                    return ValidationResult(
                        passed=False, layer=2,
                        reason=f"Value '{value}' doesn't match any pattern "
                               f"for type '{entity_type}'"
                    )

        return ValidationResult(passed=True)

    def _check_consistency(self, source: KGNode, relation: str,
                           target: KGNode, context: EntityContext) -> ValidationResult:
        """
        Layer 3: 一致性合法性
        
        利用 context.existing_rels 做跨字段/跨边验证。
        """
        rules = get_consistency_rules(source.entity_type)

        for rule in rules:
            if rule.check_fn_name == "check_position_order":
                result = self._check_position_order(
                    source, relation, target, context)
                if not result.passed:
                    return result

            elif rule.check_fn_name == "check_gene_chromosome_prefix":
                result = self._check_gene_chromosome_prefix(
                    source, relation, target, context)
                if not result.passed:
                    return result

            elif rule.check_fn_name == "check_sv_position_order":
                result = self._check_sv_position_order(
                    source, relation, target, context)
                if not result.passed:
                    return result

            elif rule.check_fn_name == "check_sv_genome_different":
                result = self._check_sv_genome_different(
                    source, relation, target, context)
                if not result.passed:
                    return result

        return ValidationResult(passed=True)

    # ── Layer 3 具体规则实现 ──────────────────────────────────

    def _check_position_order(self, source: KGNode, relation: str,
                              target: KGNode,
                              context: EntityContext) -> ValidationResult:
        """Gene: start_pos 必须小于 end_pos"""
        if relation == "end_pos" and "start_pos" in context.existing_rels:
            start_id = context.existing_rels["start_pos"][0]
            # 从 node_id 提取值: "Position::12345" → "12345"
            start_val = start_id.split("::")[-1] if "::" in start_id else ""
            end_val = target.value
            try:
                if int(start_val) >= int(end_val):
                    return ValidationResult(
                        passed=False, layer=3,
                        reason=f"start_pos({start_val}) >= end_pos({end_val})"
                    )
            except (ValueError, TypeError):
                pass  # 非数字无法比较，跳过

        if relation == "start_pos" and "end_pos" in context.existing_rels:
            end_id = context.existing_rels["end_pos"][0]
            end_val = end_id.split("::")[-1] if "::" in end_id else ""
            start_val = target.value
            try:
                if int(start_val) >= int(end_val):
                    return ValidationResult(
                        passed=False, layer=3,
                        reason=f"start_pos({start_val}) >= end_pos({end_val})"
                    )
            except (ValueError, TypeError):
                pass

        return ValidationResult(passed=True)

    def _check_gene_chromosome_prefix(self, source: KGNode, relation: str,
                                      target: KGNode,
                                      context: EntityContext) -> ValidationResult:
        """Gene 名中的染色体编号应与 chromosome_no 一致"""
        if relation != "chromosome_no":
            return ValidationResult(passed=True)

        gene_name = source.value
        chrom_name = target.value

        # 从 Gene 名提取预期染色体编号
        # LOC_Os03g12345 → 03 → Chr03
        match = re.match(r"(?:LOC_)?Os(\d{2})g", gene_name)
        if match:
            expected_num = match.group(1)
            expected_chrom = f"Chr{expected_num}"
            if chrom_name != expected_chrom:
                return ValidationResult(
                    passed=False, layer=3,
                    reason=f"Gene '{gene_name}' suggests {expected_chrom}, "
                           f"but chromosome is '{chrom_name}'"
                )

        return ValidationResult(passed=True)

    def _check_sv_position_order(self, source: KGNode, relation: str,
                                 target: KGNode,
                                 context: EntityContext) -> ValidationResult:
        """SV: query_start_pos < query_end_pos"""
        if relation == "query_end_pos" and "query_start_pos" in context.existing_rels:
            start_id = context.existing_rels["query_start_pos"][0]
            start_val = start_id.split("::")[-1] if "::" in start_id else ""
            end_val = target.value
            try:
                if int(start_val) >= int(end_val):
                    return ValidationResult(
                        passed=False, layer=3,
                        reason=f"query_start({start_val}) >= query_end({end_val})"
                    )
            except (ValueError, TypeError):
                pass

        return ValidationResult(passed=True)

    def _check_sv_genome_different(self, source: KGNode, relation: str,
                                   target: KGNode,
                                   context: EntityContext) -> ValidationResult:
        """SV: query_genome 和 reference_genome 不应相同"""
        if relation == "reference_genome" and "query_genome" in context.existing_rels:
            query_id = context.existing_rels["query_genome"][0]
            if query_id == target.node_id:
                return ValidationResult(
                    passed=False, layer=3,
                    reason=f"query_genome == reference_genome ({target.value})"
                )

        if relation == "query_genome" and "reference_genome" in context.existing_rels:
            ref_id = context.existing_rels["reference_genome"][0]
            if ref_id == target.node_id:
                return ValidationResult(
                    passed=False, layer=3,
                    reason=f"query_genome == reference_genome ({target.value})"
                )

        return ValidationResult(passed=True)

    # ── 辅助 ──────────────────────────────────────────────────

    @staticmethod
    def _get_vd_key_for_type(entity_type: str) -> Optional[str]:
        """
        实体类型 → 值域键名的映射
        
        只有可枚举类型才有 VD 约束。
        """
        mapping = {
            "Strand": "Strand",
            "Chromosome": "Chromosome",
            "Accession": "Accession",
        }
        return mapping.get(entity_type)


# ============================================================
# 5. IncrementalKGConstructor — 增量构建主循环
# ============================================================

class IncrementalKGConstructor:
    """
    Algorithm 2: Graph-Centric Incremental Construction
    
    增量构建知识图谱的主控类。
    
    Usage:
        constructor = IncrementalKGConstructor(vd=vd_dict, mps=mps_dict)
        
        # 逐批次处理数据
        for batch in data_batches:
            constructor.process_batch(batch, file_type="bed_gene",
                                      file_name="Nipponbare_genes.bed")
        
        # 获取结果
        kg = constructor.kg
        print(f"Nodes: {kg.node_count()}, Edges: {kg.edge_count()}")
        print(f"Conflicts: {len(kg.conflicts)}")
    """

    def __init__(self, vd: Dict[str, list] = None,
                 mps: Dict[str, str] = None,
                 enable_resolve: bool = True,
                 enable_validate: bool = True,
                 enable_gap_detection: bool = True):
        """
        初始化构建器
        
        Args:
            vd: 值域字典 (从 MDR 获取)
            mps: 别名映射 (从 MDR 获取)
            enable_resolve: 是否启用实体解析 (消融实验开关)
            enable_validate: 是否启用 MDR 验证 (消融实验开关)
            enable_gap_detection: 是否启用缺口检测 (消融实验开关)
        """
        self.kg = InMemoryKG()
        self.validator = MDRValidator(vd=vd, mps=mps)
        self.ontology_lookup = get_ontology_lookup()

        # 消融实验开关
        self.enable_resolve = enable_resolve
        self.enable_validate = enable_validate
        self.enable_gap_detection = enable_gap_detection

        # 处理日志
        self.processing_log: List[Dict[str, Any]] = []

        # 已处理的文件列表
        self.processed_files: List[str] = []

    def process_batch(self, records: List[DataRecord],
                      file_type: str, file_name: str = "") -> Dict[str, int]:
        """
        处理一批数据记录 (模拟处理一个文件)
        
        这是 Algorithm 2 主循环的核心。
        
        Args:
            records: 数据记录列表
            file_type: 文件类型
            file_name: 文件名
        
        Returns:
            处理统计 {"entities": N, "edges_added": N, "conflicts": N, ...}
        """
        batch_stats = {
            "entities": 0,
            "edges_added": 0,
            "edges_skipped_dup": 0,
            "edges_skipped_conflict": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "gaps_filled": 0,
        }

        for record in records:
            # ── Step 1: 图谱实体解析 (Type-aware) ──────────
            if self.enable_resolve:
                ei_node = self.kg.resolve(
                    record.entity_key, record.entity_type, file_name)
            else:
                # 消融: no-resolve — 每次创建新节点(不复用)
                node_id = f"{record.entity_type}::{record.entity_key}::{file_name}"
                ei_node = KGNode(
                    node_id=node_id,
                    entity_type=record.entity_type,
                    value=record.entity_key,
                    source_files=[file_name],
                )
                self.kg.nodes[node_id] = ei_node

            batch_stats["entities"] += 1

            # ── Step 2: 图谱上下文获取 ─────────────────────
            context = self.kg.get_context(ei_node)

            # 处理品种关系 (从文件名推断)
            if record.accession:
                self._process_accession(ei_node, record.accession,
                                        file_type, file_name, context)

            # ── Step 3: 字段驱动的关系绑定 ─────────────────
            for field_name, value in record.fields:
                result = self._process_field(
                    ei_node, field_name, value,
                    file_type, file_name, context,
                    batch_stats,
                )

                # 如果成功写入边，刷新上下文
                if result:
                    context = self.kg.get_context(ei_node)

        self.processed_files.append(file_name)
        self.processing_log.append({
            "file_name": file_name,
            "file_type": file_type,
            "record_count": len(records),
            "stats": batch_stats,
        })

        return batch_stats

    def _process_field(self, ei_node: KGNode, field_name: str, value: str,
                       file_type: str, file_name: str,
                       context: EntityContext,
                       stats: Dict[str, int]) -> bool:
        """
        处理单个字段 → 绑定关系 → 验证 → 写入
        
        Returns:
            True 如果成功写入了边
        """
        if not value or str(value).strip() == "":
            return False

        value = str(value).strip()

        # ── Step 3a: 推断关系类型 (确定性映射) ──────────
        inferred = infer_relation_type(field_name, file_type)
        if inferred is None:
            return False

        relation, target_type = inferred

        # ── Step 3b: 解析目标实体 (Type-aware Resolve) ──
        expected_type = target_type or get_range_type(relation, ei_node.entity_type)
        if not expected_type:
            return False

        ej_node = self.kg.resolve(value, expected_type, file_name)

        # ── Step 3c: 基数感知冲突检测 ─────────────────
        kappa = get_cardinality(ei_node.entity_type, relation)

        if kappa == Cardinality.EXACTLY_ONE and relation in context.existing_rels:
            existing_targets = context.existing_rels[relation]
            if ej_node.node_id in existing_targets:
                # 完全重复，跳过
                stats["edges_skipped_dup"] += 1
                self.kg.stats["edges_skipped_dup"] += 1
                return False
            else:
                # 真冲突: 单值关系指向不同目标 → 审计队列
                existing_source = ""
                for edge in self.kg.get_edges_by_relation(
                        ei_node.node_id, relation):
                    existing_source = edge.source_file
                    break

                self.kg.mark_conflict(
                    ei_node, relation,
                    existing_target_id=existing_targets[0],
                    new_target_id=ej_node.node_id,
                    existing_source=existing_source,
                    new_source=file_name,
                )
                stats["edges_skipped_conflict"] += 1
                return False

        # κ=zero_or_more: 检查完全重复
        if kappa == Cardinality.ZERO_OR_MORE:
            if self.kg.has_edge(ei_node.node_id, relation, ej_node.node_id):
                stats["edges_skipped_dup"] += 1
                self.kg.stats["edges_skipped_dup"] += 1
                return False

        # ── Step 3d: MDR 三层验证 ──────────────────────
        if self.enable_validate:
            vresult = self.validator.validate(
                ei_node, relation, ej_node, context, file_type)

            if not vresult.passed:
                stats["validation_failed"] += 1
                if vresult.layer == 1:
                    self.kg.stats["validation_failed_l1"] += 1
                elif vresult.layer == 2:
                    self.kg.stats["validation_failed_l2"] += 1
                elif vresult.layer == 3:
                    self.kg.stats["validation_failed_l3"] += 1

                logger.debug(
                    f"Validation failed L{vresult.layer}: "
                    f"({ei_node.value})-[{relation}]->({ej_node.value}): "
                    f"{vresult.reason}"
                )
                return False

            stats["validation_passed"] += 1
            self.kg.stats["validation_passed"] += 1

        # ── Step 3e: 写入 KG ──────────────────────────
        self.kg.add_edge(ei_node, relation, ej_node, file_name)
        stats["edges_added"] += 1

        # 检查是否填补了缺口
        if self.enable_gap_detection and relation in context.required_missing:
            stats["gaps_filled"] += 1

        return True

    def _process_accession(self, ei_node: KGNode, accession: str,
                           file_type: str, file_name: str,
                           context: EntityContext):
        """
        处理品种关系 (从文件名推断的 Accession)
        """
        # 只有 Gene 和 SV 有品种关系
        if ei_node.entity_type == "Gene":
            relation = "type"
        elif ei_node.entity_type == "Structural_Variations":
            relation = "query_genome"
        else:
            return

        # 检查是否已有品种关系
        kappa = get_cardinality(ei_node.entity_type, relation)
        if kappa == Cardinality.EXACTLY_ONE and relation in context.existing_rels:
            return  # 已有品种关系，不重复添加

        acc_node = self.kg.resolve(accession, "Accession", file_name)

        if self.enable_validate:
            vresult = self.validator.validate(
                ei_node, relation, acc_node, context, file_type)
            if not vresult.passed:
                return

        self.kg.add_edge(ei_node, relation, acc_node, file_name)

    def get_summary(self) -> Dict[str, Any]:
        """
        获取构建摘要
        
        Returns:
            包含节点数、边数、冲突数、验证统计等的字典
        """
        return {
            "nodes": self.kg.node_count(),
            "edges": self.kg.edge_count(),
            "conflicts": len(self.kg.conflicts),
            "duplicate_warnings": len(self.kg.duplicate_warnings),
            "processed_files": len(self.processed_files),
            "stats": dict(self.kg.stats),
            "processing_log": self.processing_log,
        }


# ============================================================
# 6. BaselineConstructor — Algorithm 1 (对照组)
# ============================================================

class BaselineConstructor:
    """
    Algorithm 1: 原论文的离线构建方法 (对照组)
    
    特点:
    - 文件独立处理 (无跨文件共享状态)
    - 没有 Resolve (同一实体在不同文件中创建为不同节点)
    - 没有 GetContext (不检测缺口、不做冲突检测)
    - 没有 ValidateMDR (不做三层验证)
    - 关系来自数据字段 + Rel 查表
    """

    def __init__(self):
        self.kg = InMemoryKG()
        self.processed_files: List[str] = []
        self.processing_log: List[Dict[str, Any]] = []

    def process_batch(self, records: List[DataRecord],
                      file_type: str, file_name: str = "") -> Dict[str, int]:
        """
        Algorithm 1 的处理方式: 文件独立，无共享状态
        """
        stats = {
            "entities": 0,
            "edges_added": 0,
            "edges_skipped_dup": 0,
            "edges_skipped_conflict": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "gaps_filled": 0,
        }

        for record in records:
            # 不做 Resolve: 每个文件独立创建节点
            node_id = f"{record.entity_type}::{record.entity_key}::{file_name}"
            ei_node = KGNode(
                node_id=node_id,
                entity_type=record.entity_type,
                value=record.entity_key,
                source_files=[file_name],
            )
            self.kg.nodes[node_id] = ei_node
            stats["entities"] += 1

            # 品种关系
            if record.accession:
                acc_id = f"Accession::{record.accession}::{file_name}"
                acc_node = KGNode(
                    node_id=acc_id,
                    entity_type="Accession",
                    value=record.accession,
                    source_files=[file_name],
                )
                self.kg.nodes[acc_id] = acc_node

                if record.entity_type == "Gene":
                    self.kg.add_edge(ei_node, "type", acc_node, file_name)
                    stats["edges_added"] += 1

            # 处理字段
            for field_name, value in record.fields:
                if not value or str(value).strip() == "":
                    continue

                value = str(value).strip()

                inferred = infer_relation_type(field_name, file_type)
                if inferred is None:
                    continue

                relation, target_type = inferred
                expected_type = target_type or get_range_type(
                    relation, record.entity_type)
                if not expected_type:
                    continue

                # 不做 Resolve: 独立创建目标节点
                target_id = f"{expected_type}::{value}::{file_name}"
                ej_node = KGNode(
                    node_id=target_id,
                    entity_type=expected_type,
                    value=value,
                    source_files=[file_name],
                )
                self.kg.nodes[target_id] = ej_node

                # 不做 ValidateMDR: 直接写入
                self.kg.add_edge(ei_node, relation, ej_node, file_name)
                stats["edges_added"] += 1

        self.processed_files.append(file_name)
        self.processing_log.append({
            "file_name": file_name,
            "file_type": file_type,
            "record_count": len(records),
            "stats": stats,
        })

        return stats

    def get_summary(self) -> Dict[str, Any]:
        """获取构建摘要"""
        return {
            "nodes": self.kg.node_count(),
            "edges": self.kg.edge_count(),
            "conflicts": len(self.kg.conflicts),
            "processed_files": len(self.processed_files),
            "stats": dict(self.kg.stats),
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("Graph-Centric Incremental KG Constructor — Unit Test")
    print("=" * 60)

    # 模拟 VD 和 MPS
    test_vd = {
        "Strand": ["+", "-"],
        "Chromosome": [f"Chr{i:02d}" for i in range(1, 13)],
        "Accession": ["Nipponbare", "9311", "MH63"],
    }
    test_mps = {"正链": "+", "负链": "-"}

    # ── 测试 Algorithm 2 ──────────────────────────────────
    print("\n--- Algorithm 2 (Graph-Centric) ---\n")
    constructor = IncrementalKGConstructor(vd=test_vd, mps=test_mps)

    # Batch 1: BED 文件 (基因基本信息)
    batch1 = [
        DataRecord(
            entity_key="LOC_Os01g12345",
            entity_type="Gene",
            fields=[
                ("chrom", "Chr01"),
                ("start", "1000"),
                ("end", "5000"),
                ("strand", "+"),
            ],
            file_type="bed_gene",
            file_name="Nipponbare_genes.bed",
            accession="Nipponbare",
        ),
        DataRecord(
            entity_key="LOC_Os03g67890",
            entity_type="Gene",
            fields=[
                ("chrom", "Chr03"),
                ("start", "20000"),
                ("end", "25000"),
                ("strand", "-"),
            ],
            file_type="bed_gene",
            file_name="Nipponbare_genes.bed",
            accession="Nipponbare",
        ),
    ]

    stats1 = constructor.process_batch(batch1, "bed_gene", "Nipponbare_genes.bed")
    print(f"Batch 1 (BED): {stats1}")

    # Batch 2: 表达量文件 (同一个基因在不同文件中出现)
    batch2 = [
        DataRecord(
            entity_key="LOC_Os01g12345",  # 同一个基因！
            entity_type="Gene",
            fields=[
                ("leaf_value", "Expression_leaf_LOC_Os01g12345"),
            ],
            file_type="fpkm_expression",
            file_name="Nipponbare_fpkm.csv",
            accession="Nipponbare",
        ),
    ]

    stats2 = constructor.process_batch(batch2, "fpkm_expression", "Nipponbare_fpkm.csv")
    print(f"Batch 2 (FPKM): {stats2}")

    # Batch 3: RBH 同源关系 (跨品种链接)
    batch3 = [
        DataRecord(
            entity_key="LOC_Os01g12345",  # Nipponbare 基因
            entity_type="Gene",
            fields=[
                ("subject_gene", "R01C01g00123"),  # 9311 基因
            ],
            file_type="rbh_homolog",
            file_name="Nipponbare_vs_9311_RBH.txt",
            accession="",
        ),
    ]

    stats3 = constructor.process_batch(batch3, "rbh_homolog", "Nipponbare_vs_9311_RBH.txt")
    print(f"Batch 3 (RBH): {stats3}")

    # 汇总
    summary = constructor.get_summary()
    print(f"\n=== Algorithm 2 Summary ===")
    print(f"Nodes: {summary['nodes']}")
    print(f"Edges: {summary['edges']}")
    print(f"Conflicts: {summary['conflicts']}")
    print(f"Resolve hits: {summary['stats']['resolve_hit']}")
    print(f"Resolve misses: {summary['stats']['resolve_miss']}")

    # 验证: LOC_Os01g12345 应该只有一个节点 (Resolve 合并)
    gene_node = constructor.kg.nodes.get("Gene::LOC_Os01g12345")
    if gene_node:
        print(f"\nGene LOC_Os01g12345:")
        print(f"  Sources: {gene_node.source_files}")
        print(f"  Relations: {gene_node.relation_count}")
        ctx = constructor.kg.get_context(gene_node)
        print(f"  Existing rels: {dict(ctx.existing_rels)}")
        print(f"  Required missing: {ctx.required_missing}")
        print(f"  Optional candidates: {ctx.optional_candidates}")

    # ── 测试 Algorithm 1 (Baseline) ──────────────────────
    print("\n\n--- Algorithm 1 (Baseline) ---\n")
    baseline = BaselineConstructor()

    baseline.process_batch(batch1, "bed_gene", "Nipponbare_genes.bed")
    baseline.process_batch(batch2, "fpkm_expression", "Nipponbare_fpkm.csv")
    baseline.process_batch(batch3, "rbh_homolog", "Nipponbare_vs_9311_RBH.txt")

    b_summary = baseline.get_summary()
    print(f"=== Algorithm 1 Summary ===")
    print(f"Nodes: {b_summary['nodes']}")
    print(f"Edges: {b_summary['edges']}")
    print(f"Conflicts: {b_summary['conflicts']}")

    # 对比
    print(f"\n=== Comparison ===")
    print(f"{'Metric':<25} {'Algo 1':>10} {'Algo 2':>10} {'Delta':>10}")
    print("-" * 55)
    print(f"{'Nodes':<25} {b_summary['nodes']:>10} {summary['nodes']:>10} "
          f"{summary['nodes'] - b_summary['nodes']:>+10}")
    print(f"{'Edges':<25} {b_summary['edges']:>10} {summary['edges']:>10} "
          f"{summary['edges'] - b_summary['edges']:>+10}")
    print(f"{'Conflicts detected':<25} {b_summary['conflicts']:>10} "
          f"{summary['conflicts']:>10} "
          f"{summary['conflicts'] - b_summary['conflicts']:>+10}")
    print(f"{'Entity dedup':<25} {'N/A':>10} "
          f"{summary['stats']['resolve_hit']:>10}")
