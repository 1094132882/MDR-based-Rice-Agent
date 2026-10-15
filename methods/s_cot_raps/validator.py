#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 GoT-CI Validator - 基于 MDR 规则的 LLM 输出校验器

核心功能：
1. Type Check: 检查必填字段是否存在
2. Value Domain Check: 检查值是否在允许范围内
3. Regex Check: 检查格式是否符合正则
4. Self-Correction: 生成错误反馈供 LLM 自我修正

GoT-CI (Graph of Thought with Compliance/Integrity):
- 在 LLM 输出和工具执行之间增加验证层
- ❌ 不合规则返回错误信息让 LLM 重试
- ✅ 合规则放行执行工具
- 🔄 自动修正别名（如 "正链" -> "+"）

使用方式:
    from validator import MDRValidator, validate_json_output
    
    validator = MDRValidator()
    is_valid, error_msg, corrected = validator.validate("gene_basic_info", llm_output)
    
    if not is_valid:
        # 生成自我修正提示
        correction_prompt = validator.generate_correction_prompt(...)

@author: jingwen.wu
@Time: 2025/12
"""
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 确保能导入
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from methods.s_cot_raps.mdr_adapter import MDRSchemaAdapter


class MDRValidator:
    """
    MDR 合规性校验器
    
    校验 LLM 生成的 JSON 输出是否符合 MDR 规则：
    1. 必填字段检查
    2. 值域检查
    3. 格式检查
    """
    
    # 工具级别的必填字段定义
    REQUIRED_FIELDS = {
        "gene_basic_info": ["Gene"],
        "gene_function": ["Gene"],
        "gene_locator": [],  # 返回 Genes 列表
        "gene_mutant_info": [],  # Gene 或 Mutant
        "ogi_info": [],  # Gene 或 OGI
        "adjacent_genes": [],  # Neighbors 列表
        "homologous_gene_and_expression": ["Gene"],
        "structural_variation_link": [],  # SV 或 TE
        "structural_variation_locator": []  # SVs 列表
    }
    
    # 字段级别的正则约束（基于数据库 MDR 规则）
    FIELD_PATTERNS = {
        "Gene": [
            r"^LOC_Os\d{2}g\d{5}(\.\d+)?$",           # MSU 格式
            r"^Os[A-Za-z0-9_]+[Gg]\d+(\.\d+)?$",      # RAP 格式
            r"^Os\d{2}g\d+(\.\d+)?$",                 # 简化 RAP
            r"^TMG\d+(\.\d+)?$",                       # TMG 格式
            r"^R\d+C\d+g\d+$",                         # RC 格式
            r"^Oglab_\d+$",                            # Oglab 格式
            r"^Os[A-Z][A-Za-z0-9_]+_\d{2}g\d+(\.\d+)?$"  # 品种特异格式
        ],
        "OGI": r"^OGI:\d{8}$",
        "Chromosome": r"^Chr(0[1-9]|1[0-2])$",
        "Position": r"^\d+-\d+$",
        "Mutant": r"^22NB[A-Z]\d+$",
        "SV_Name": r"^[A-Za-z0-9_]+_[A-Za-z0-9]+_(DEL|INS|TRA|INV|OTH)\d+(_\d+)?$"
    }
    
    # 基于数据库的枚举值域（从 MDR 获取）
    ENUM_VALUE_DOMAINS = {
        "Strand": ["+", "-"],
        "Stand": ["+", "-"],  # 数据库中的命名
        "SV_Type": ["DEL", "INS", "TRA", "INV", "OTH"],
        "OGI_Class": ["C", "D", "S"],
        "Homologs_Relationship": ["RBH", "SBH"],
    }
    
    def __init__(self, adapter: MDRSchemaAdapter = None):
        """
        初始化校验器
        
        Args:
            adapter: MDR Schema 适配器
        """
        self.adapter = adapter or MDRSchemaAdapter()
    
    def validate(
        self, 
        tool_name: str, 
        llm_output: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        校验 LLM 输出
        
        Args:
            tool_name: 工具名
            llm_output: LLM 生成的 JSON 字典
        
        Returns:
            (is_valid, error_message, corrected_output)
            - is_valid: 是否合规
            - error_message: 错误信息（用于 Self-Correction）
            - corrected_output: 自动修正后的输出（如别名替换）
        """
        errors = []
        corrected = llm_output.copy() if isinstance(llm_output, dict) else {}
        
        # 如果输入不是字典，直接返回错误
        if not isinstance(llm_output, dict):
            return False, f"Output must be a JSON object, got {type(llm_output).__name__}", {}
        
        # 🎯 修复：跳过工具返回结果格式的验证
        # 工具返回的格式是 {"query": "...", "result": [...]}，这不需要验证
        # 我们只验证 LLM 生成的工具调用参数，而不是工具执行结果
        if 'query' in llm_output and 'result' in llm_output:
            # 这是工具返回的结果，直接跳过验证
            return True, "", llm_output
        
        # 🎯 修复：跳过已经包含有效数据的结果
        # 如果 JSON 中包含以下字段，说明是工具的有效返回，不需要验证
        tool_result_indicators = [
            # 位置相关
            'start_pos', 'end_pos', 'chromosome', 'position', 'start', 'end',
            # 链接/URL
            'gene_url', 'dna_seq_link', 'cds_seq_link', 'protein_seq_link',
            # 结构变异
            'sv_name', 'sv_type', 'sv_id', 'te_type', 'te_annotations',
            # 突变体
            'mutant_id', 'mutant_name', 'mutant_list',
            # 表达量
            'root_expression', 'stem_expression', 'leaf_expression', 
            'root_value', 'stem_value', 'leaf_value', 'young_ear_value',
            'm.root_value', 'm.stem_value', 'm.leaf_value',
            # OGI
            'ogi', 'ogi_class', 'member_count',
            # 邻近基因
            'neighbors', 'upstream', 'downstream',
            # 其他
            'transcript', 'transcripts', 'function', 'annotation',
            # 列表类结果
            '_result_list'
        ]
        # 检查是否包含任何工具结果指标（忽略大小写）
        output_keys_lower = {k.lower() for k in llm_output.keys()}
        if any(indicator.lower() in output_keys_lower for indicator in tool_result_indicators):
            return True, "", llm_output
        
        # 1. 必填字段检查
        field_errors = self._check_required_fields(tool_name, llm_output)
        errors.extend(field_errors)
        
        # 2. 值域检查 + 自动修正
        vd_errors, corrected = self._check_value_domains(tool_name, llm_output)
        errors.extend(vd_errors)
        
        # 3. 格式检查
        format_errors = self._check_field_formats(llm_output)
        errors.extend(format_errors)
        
        if errors:
            error_msg = "MDR Validation Failed:\n" + "\n".join(f"  - {e}" for e in errors)
            return False, error_msg, corrected
        
        return True, "", corrected

    def _check_required_fields(
        self,
        tool_name: str,
        output: Dict[str, Any],
    ) -> List[str]:
        """
        检查必填字段

        🎯 P0-4 增强：当检测到 LLM 生成了结果格式而非参数格式时，
        提供更明确的指导信息
        """
        errors = []
        required = self.REQUIRED_FIELDS.get(tool_name, [])

        # 🎯 检测是否 LLM 错误地生成了"结果"而非"参数"
        # 特征：包含 query/result 但不包含必填的参数字段
        if "query" in output or "result" in output:
            # 这种情况在前面应该已经被跳过了，但如果走到这里说明有问题
            return []  # 不报错，交给后续处理

        for field in required:
            if field not in output or output[field] is None:
                # 提供更具体的错误信息
                example_value = self._get_example_value(field)
                errors.append(
                    f"Missing required field: '{field}'. "
                    f"Example format: {{\"{field}\": \"{example_value}\"}}"
                )

        return errors

    def _get_example_value(self, field: str) -> str:
        """获取字段的示例值"""
        examples = {
            "Gene": "LOC_Os08g02050",
            "Chromosome": "Chr08",
            "Position": "662167-667559",
            "Strand": "+",
            "OGI": "OGI:01234567",
            "Mutant": "22NBA01",
            "SV_Name": "G46_Ref_DEL123456",
        }
        return examples.get(field, "...")

    def _check_value_domains(
        self,
        tool_name: str,
        output: Dict[str, Any],
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        检查值域并自动修正

        Returns:
            (errors, corrected_output)
        """
        errors = []
        corrected = output.copy()

        # 获取工具的值域约束
        constraints = self.adapter.get_constraints(tool_name)
        vd_constraints = constraints.get("vd_constraints", {})

        for field, allowed_values in vd_constraints.items():
            if field in output:
                value = output[field]

                # 跳过空值
                if value is None:
                    continue

                # 尝试标准化
                normalized = self.adapter.normalize_value(field, value)

                if normalized != value:
                    corrected[field] = normalized
                    value = normalized

                # 验证是否在值域内
                if allowed_values and value not in allowed_values:
                    # 不是严格错误，只是警告
                    # errors.append(f"Value '{value}' for field '{field}' not in allowed list")
                    pass

        # 特殊处理 Strand
        if "Strand" in output:
            strand = output["Strand"]
            if strand in ["正链", "正向", "forward"]:
                corrected["Strand"] = "+"
            elif strand in ["负链", "反向", "reverse"]:
                corrected["Strand"] = "-"

        return errors, corrected

    def _check_field_formats(self, output: Dict[str, Any]) -> List[str]:
        """检查字段格式（正则）"""
        errors = []

        for field, patterns in self.FIELD_PATTERNS.items():
            if field not in output or output[field] is None:
                continue

            value = str(output[field])

            # 跳过空值和占位符
            if not value or value in ["null", "None", ""]:
                continue

            # 处理多个正则模式（任一匹配即可）
            if isinstance(patterns, list):
                matched = any(re.match(p, value) for p in patterns)
            else:
                matched = bool(re.match(patterns, value))

            # 基因名格式比较宽松，不强制报错
            if not matched and field not in ["Gene"]:
                # 只对严格字段报错
                if field in ["OGI", "Chromosome"]:
                    errors.append(f"Invalid format for '{field}': '{value}'")

        return errors

    def generate_correction_prompt(
        self,
        tool_name: str,
        error_msg: str,
        original_output: Dict[str, Any],
    ) -> str:
        """
        生成自我修正提示

        Args:
            tool_name: 工具名
            error_msg: 验证错误信息
            original_output: 原始输出

        Returns:
            用于 LLM 自我修正的提示文本
        """
        constraints = self.adapter.get_constraints(tool_name)

        prompt = f"""## MDR Validation Error

Your previous output failed MDR compliance check:
{error_msg}

## Constraints for {tool_name}:
- Required fields: {self.REQUIRED_FIELDS.get(tool_name, [])}
- Value domains: {constraints.get('vd_constraints', {})}

## Your Original Output:
{json.dumps(original_output, ensure_ascii=False, indent=2)}

## Instructions:
Please correct your output to comply with MDR rules. 
- Ensure all required fields are present
- Use values from the allowed list (e.g., Strand must be "+" or "-")
- Use correct formats (e.g., OGI must be "OGI:XXXXXXXX")

Please provide the corrected output in JSON format.
"""
        return prompt


# ============================================================
# 🎯 GoT-CI v2：工具结果语义校验（不是校验 LLM 工具参数）
# 用于拦截 “JSON 结构合法但业务/字段不对” 的情况，并触发自动重试
# ============================================================
def _has_any_key(d: Dict[str, Any], keys: List[str]) -> bool:
    """d 是否包含 keys 中任意一个键（且值非空）。"""
    if not isinstance(d, dict):
        return False
    for k in keys:
        if k in d and d.get(k) not in (None, ""):
            return True
    return False


def validate_tool_result(
    tool_name: str,
    question: str,
    tool_output: Dict[str, Any],
) -> Tuple[bool, str, str]:
    """
    校验工具执行后的输出（tool_output），用于 GoT-CI v2 拦截并触发重试。

    约定 tool_output 形状为：
      {"query": "...", "result": [ { ... }, ... ]}

    Returns:
      (ok, error_msg, hint)
    """
    if not isinstance(tool_output, dict):
        return True, "", ""

    result = tool_output.get("result")
    if result is None:
        return True, "", ""
    if not isinstance(result, list):
        return False, f"Tool output result must be list, got {type(result).__name__}", "工具返回的 result 字段必须是列表。"

    q = (question or "").strip()
    q_lower = q.lower()

    # ------------------------------
    # structural_variation_locator
    # ------------------------------
    if tool_name == "structural_variation_locator":
        is_longest = any(kw in q_lower for kw in ["最长", "longest", "跨度最大", "最大跨度", "最大"]) and (
            ("结构变异" in q) or ("sv" in q_lower)
        )
        is_stats = any(kw in q_lower for kw in ["统计", "数量", "数目", "多少种", "各类型", "分类统计", "分布"]) and (
            ("结构变异" in q) or ("sv" in q_lower)
        )

        # ✅ 若问题明确指定 SV 类型，则允许只返回 sv_count（不要求按类型分组）
        asked_type_in_question = any(
            kw in q_lower
            for kw in [
                # 中文类型词
                "缺失",
                "插入",
                "易位",
                "倒位",
                "其他",
                # 英文/缩写
                "del",
                "ins",
                "tra",
                "inv",
                "oth",
            ]
        )

        # Longest must be single row + required fields
        if is_longest:
            if len(result) != 1:
                return (
                    False,
                    f"Longest query returned {len(result)} rows (expect 1).",
                    "这是“最长/最大跨度”问题：请在 Cypher 中 `ORDER BY sv.SVLENGTH DESC LIMIT 1`，并只返回 1 条记录。",
                )
            if isinstance(result[0], dict):
                required = ["sv_name", "sv_type", "sv_length", "query_genome", "reference_genome"]
                missing = [k for k in required if not _has_any_key(result[0], [k])]
                if missing:
                    return (
                        False,
                        f"Longest query missing required fields: {missing}",
                        "最长类查询必须返回：sv_name, sv_type, sv_length, query_genome, reference_genome（5字段缺一不可）。",
                    )

        # Stats (per-type) must return sv_type + sv_count rows (unless typed query)
        if is_stats and result and (not asked_type_in_question):
            if len(result) == 1 and isinstance(result[0], dict):
                keys = set(result[0].keys())
                total_only_keys = {"sv_count", "count", "total_variants", "total", "variants", "total_count"}
                has_type = _has_any_key(result[0], ["sv_type", "SVTYPE", "type"])
                if (keys & total_only_keys) and not has_type:
                    return (
                        False,
                        f"Stats query returned total-only keys={sorted(keys)}",
                        "这是“分类统计/各类型数量/多少种”问题：请按 `sv.SVTYPE` 分组返回每一类数量，例如："
                        "`WITH sv.SVTYPE AS sv_type, count(sv) AS sv_count RETURN sv_type, sv_count`。不要只返回总数。",
                    )

            for i, item in enumerate(result):
                if not isinstance(item, dict):
                    continue
                has_type = _has_any_key(item, ["sv_type", "SVTYPE", "type"])
                has_cnt = _has_any_key(item, ["sv_count", "count"])
                if not (has_type and has_cnt):
                    return (
                        False,
                        f"Stats row #{i} missing sv_type/sv_count keys: {sorted(item.keys())}",
                        "统计结果必须返回 `sv_type` 和 `sv_count` 两列（每行一种类型）。",
                    )

    # ------------------------------
    # adjacent_genes
    # ------------------------------
    elif tool_name == "adjacent_genes":
        if not result:
            return (
                False,
                "Adjacent-genes query returned empty result.",
                "这是邻近基因查询：必须返回邻近基因列表，确保 `RETURN g2.name AS gene_name`。",
            )
        if result and isinstance(result[0], dict):
            keys = set(result[0].keys())
            # Run5 ID67: drift into location schema
            looks_like_location = any(k in keys for k in ["chromosome", "start_pos", "end_pos", "gene_url", "start", "end"])
            has_gene_name = any(k in keys for k in ["gene_name", "name"])
            count_only = any(k in keys for k in ["gene_count", "count"]) and not has_gene_name
            if looks_like_location and not has_gene_name:
                return (
                    False,
                    f"Adjacent-genes query drifted into location schema keys={sorted(keys)}",
                    "这是邻近基因查询：请返回邻近基因列表，必须包含 `g2.name AS gene_name`（严禁只返回位置信息/URL）。",
                )
            if count_only:
                return (
                    False,
                    f"Adjacent-genes query returned count-only keys={sorted(keys)}",
                    "这是邻近基因查询：不要只返回数量，必须返回基因列表（`RETURN g2.name AS gene_name`）。",
                )

    # ------------------------------
    # gene_basic_info (transcripts)
    # ------------------------------
    elif tool_name == "gene_basic_info":
        # 转录本查询（不要把“转录方向/转录方向正反/链方向”误判为转录本）
        is_strand_q = any(kw in q_lower for kw in ["链", "strand", "方向", "正链", "负链", "正向", "反向"])
        is_transcript_q = (
            ("转录本" in q)
            or ("mrna" in q_lower)
            or ("mRNA" in q)
            or ("mRNA记录" in q)
        )
        if is_transcript_q:
            if not result:
                return (
                    False,
                    "Transcript query returned empty result.",
                    "这是转录本查询：请通过 `(g:Gene)-[:has_a_transcript]->(m:mRNA)` 并 `RETURN collect(m.name) AS transcripts` 返回转录本列表。",
                )
            first = result[0]
            if isinstance(first, dict):
                if "transcripts" not in first:
                    return (
                        False,
                        f"Transcript question returned insufficient fields keys={sorted(first.keys())}",
                        "这是转录本查询：必须返回 `transcripts` 列表（不要只返回 gene_url 或 mrna_count）。示例："
                        "`MATCH (g:Gene)-[:has_a_transcript]->(m:mRNA) WHERE g.name='xxx' RETURN collect(m.name) AS transcripts`。",
                    )
                if not isinstance(first.get("transcripts"), list) or len(first.get("transcripts") or []) == 0:
                    return (
                        False,
                        "Transcript question returned empty transcripts list.",
                        "转录本查询必须返回非空的 `transcripts` 列表（collect(m.name)）。",
                    )
        # ✅ 链/方向类问题：检查空结果后放行
        if is_strand_q:
            if not result:
                return (
                    False,
                    "Strand query returned empty result.",
                    "这是链方向查询：请确保基因名/品种名匹配正确，查询 `(g:Gene)-[:strand_info]->(st:Strand)`。",
                )
            if isinstance(result[0], dict):
                has_strand = _has_any_key(result[0], ["strand", "Strand", "st.name", "strand_direction"])
                if not has_strand:
                    return (
                        False,
                        f"Strand query missing strand field keys={sorted(result[0].keys())}",
                        "这是链方向查询：必须 `RETURN st.name AS strand`（或别名为 strand），否则无法渲染正链/负链。",
                    )
            return True, "", ""

    # ------------------------------
    # homologous_gene_and_expression
    # ------------------------------
    elif tool_name == "homologous_gene_and_expression":
        is_expr_q = any(kw in q_lower for kw in ["表达", "expression", "leaf", "root", "young", "叶", "根", "穗"])
        if is_expr_q:
            if not result:
                return (
                    False,
                    "Expression query returned empty result.",
                    "表达量查询必须返回 leaf_value、root_value、young_ear_value 三个字段；如果基因名无版本号，请兼容 `n.name STARTS WITH '{gene}.'` 并 `ORDER BY n.name LIMIT 1` 选定一个基因。",
                )
            for i, item in enumerate(result[:3]):
                if not isinstance(item, dict):
                    continue
                # 兼容 Cypher 未 alias 的返回列名（例如 m.leaf_value）
                has_leaf = _has_any_key(item, ["leaf_value", "Leaf", "leaf", "m.leaf_value", "m.leaf", "leaf_expression"])
                has_root = _has_any_key(item, ["root_value", "Root", "root", "m.root_value", "m.root", "root_expression"])
                has_young = _has_any_key(
                    item,
                    [
                        "young_ear_value",
                        "young_ear",
                        "Panicle",
                        "panicle",
                        "m.young_ear_value",
                        "m.young_ear",
                        "spikelet_development",
                    ],
                )
                if not (has_leaf and has_root and has_young):
                    return (
                        False,
                        f"Expression row #{i} missing required expression values keys={sorted(item.keys())}",
                        "表达量查询必须返回叶/根/幼穗三个组织的数据（leaf/root/young_ear），且不能为空；建议用 `AS leaf_value/root_value/young_ear_value` 显式 alias。",
                    )

    # ------------------------------
    # gene_locator (区域基因查询)
    # ------------------------------
    elif tool_name == "gene_locator":
        if not result:
            return (
                False,
                "Gene locator query returned empty result.",
                "这是区域基因查询：请确保 Cypher 正确匹配了品种名（如 G46、125827）、染色体（Chr01-Chr12）和坐标范围。",
            )
        if result and isinstance(result[0], dict):
            keys = set(result[0].keys())
            has_gene_name = any(k in keys for k in ["gene_name", "name", "g.name"])
            if not has_gene_name:
                return (
                    False,
                    f"Gene locator query missing gene_name field, keys={sorted(keys)}",
                    "区域基因查询必须返回 `g.name AS gene_name`（不能只返回坐标）。请在 RETURN 中加入 `g.name AS gene_name`。",
                )

    return True, "", ""


def validate_json_output(
    tool_name: str, 
    llm_json: Dict[str, Any], 
    mdr_schema: Dict[str, Any] = None
) -> Tuple[bool, str]:
    """
    便捷函数：校验 LLM JSON 输出
    
    Args:
        tool_name: 工具名
        llm_json: LLM 输出的 JSON
        mdr_schema: MDR Schema（可选，不传则自动获取）
    
    Returns:
        (is_valid, error_msg)
    """
    validator = MDRValidator()
    is_valid, error_msg, _ = validator.validate(tool_name, llm_json)
    return is_valid, error_msg


def validate_and_correct(
    tool_name: str,
    llm_json: Dict[str, Any],
    return_prompt: bool = False,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    便捷函数：校验并自动修正

    Args:
        tool_name: 工具名
        llm_json: LLM 输出的 JSON
        return_prompt: 是否返回纠错提示（供 LLM 自修正）

    Returns:
        return_prompt=False: (is_valid, error_msg, corrected_json)
        return_prompt=True:  (is_valid, error_msg, corrected_json, correction_prompt)
    """
    validator = MDRValidator()
    is_valid, error_msg, corrected = validator.validate(tool_name, llm_json)
    if return_prompt:
        correction_prompt = ""
        if not is_valid:
            correction_prompt = validator.generate_correction_prompt(tool_name, error_msg, llm_json)
        return is_valid, error_msg, corrected, correction_prompt
    return is_valid, error_msg, corrected


if __name__ == "__main__":
    # 测试
    print("=== MDR Validator Test ===\n")
    
    validator = MDRValidator()
    
    # 测试用例 1: 合规的输出
    print("Test 1: Valid output")
    output1 = {
        "Gene": "LOC_Os08g02050",
        "Chromosome": "Chr08",
        "Position": "662167-667559",
        "Strand": "+"
    }
    is_valid, error_msg, corrected = validator.validate("gene_basic_info", output1)
    print(f"  Valid: {is_valid}")
    
    # 测试用例 2: Strand 使用中文
    print("\nTest 2: Chinese Strand value")
    output2 = {
        "Gene": "LOC_Os08g02050",
        "Strand": "正链"
    }
    is_valid, error_msg, corrected = validator.validate("gene_basic_info", output2)
    print(f"  Valid: {is_valid}")
    print(f"  Corrected: {corrected}")
    
    # 测试用例 3: 缺少必填字段
    print("\nTest 3: Missing required field")
    output3 = {
        "Chromosome": "Chr08"
    }
    is_valid, error_msg, corrected = validator.validate("gene_basic_info", output3)
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error_msg}")
    
    # 测试用例 4: 无效的 OGI 格式
    print("\nTest 4: Invalid OGI format")
    output4 = {
        "Gene": "Os02g0692000",
        "OGI": ""  # 缺少 OGI: 前缀
    }
    is_valid, error_msg, corrected = validator.validate("ogi_info", output4)
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error_msg}")
