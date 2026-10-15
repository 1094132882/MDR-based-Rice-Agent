#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S-CoT Prompt Builder (Dynamic MDR Version)

核心改进：
1. ❌ 删除 dataset.csv 依赖（避免数据泄露）
2. ✅ 从 Neo4j 动态获取 MDR Schema
3. ✅ 基于 MDR 规则合成 Fake Few-shot Examples
4. ✅ GoT-CI 约束集成

@author: jingwen.wu
@Time: 2025/12
"""
import json
import re
import random
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 确保能导入
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "methods" / "s_cot_raps"))

# 导入动态 MDR 组件
try:
    from methods.s_cot_raps.mdr_adapter import MDRSchemaAdapter
    from methods.s_cot_raps.export_schema import get_mdr_schema
except ImportError:
    from mdr_adapter import MDRSchemaAdapter
    from export_schema import get_mdr_schema


# ============================================================
# 工具级别的严格 Schema 定义
# ============================================================

TOOL_SCHEMAS = {
    "gene_basic_info": {
        "description": "查询基因基本信息（位置、链、转录本、序列链接等）",
        "required_fields": ["Gene"],
        "optional_fields": ["Chromosome", "Position", "Strand", "Transcripts", "DNA_Sequence_Link", "CDS_Sequence_Link", "Protein_Sequence_Link"],
        "output_template": "基因{gene}的位置在{chromosome}:{position}。",
        "example_question": "LOC_Os08g02050在基因组中的具体物理坐标是多少？"
    },
    "gene_function": {
        "description": "查询基因功能注释",
        "required_fields": ["Gene", "Function"],
        "optional_fields": [],
        "output_template": "基因{gene}的功能注释为{function}。",
        "example_question": "OsXL628S_07g0049200的功能是什么？"
    },
    "gene_mutant_info": {
        "description": "查询基因突变体信息或突变体关联的基因（双向查询）",
        "required_fields": [],
        "optional_fields": ["Gene", "Mutants", "Mutant", "Genes"],
        "output_template": "基因{gene}共有{count}个突变体:{mutants}",
        "example_question": "OsMH63_03G0194400有哪些突变体？"
    },
    "ogi_info": {
        "description": "查询OGI同源基因索引信息",
        "required_fields": ["OGI"],
        "optional_fields": ["Gene", "Genes", "gene_count"],
        "output_template": "基因{gene}属于OGI:{ogi}，该分组共有{count}个成员基因。",
        "example_question": "OsARC_01g0045410的OGI编号是多少？"
    },
    "gene_locator": {
        "description": "查询某品种某染色体某区域内的基因",
        "required_fields": ["Genes"],
        "optional_fields": ["Region"],
        "output_template": "在{accession}的{region}区域内共有{count}个基因:{genes}",
        "example_question": "G46的染色体三号在500kb到550kb之间有哪些基因？"
    },
    "adjacent_genes": {
        "description": "查询基因的上下游邻近基因",
        "required_fields": ["Neighbors"],
        "optional_fields": ["TargetGene", "Direction", "neighbor_count"],
        "output_template": "基因{gene}的{direction}最近{count}个基因包括：{neighbors}",
        "example_question": "OsLK638S_12g0006300的上游有哪些基因？"
    },
    "homologous_gene_and_expression": {
        "description": "查询基因同源信息和表达量",
        "required_fields": ["Gene"],
        "optional_fields": ["Expression", "Leaf", "Root", "Panicle"],
        "output_template": "基因{gene}在叶片中的表达量为{leaf}，在根部的表达量为{root}。",
        "example_question": "Os09g0442200在不同组织中的表达情况如何？"
    },
    "structural_variation_link": {
        "description": "查询结构变异关联的转座元件",
        "required_fields": [],
        "optional_fields": ["SV", "TE_Annotations"],
        "output_template": "结构变异{sv}关联的装作元件包括：{te_types}",
        "example_question": "02428_117425_INS0734090关联了哪些转座元件？"
    },
    "structural_variation_locator": {
        "description": "查询某基因或某区域内的结构变异",
        "required_fields": [],
        "optional_fields": ["Gene", "SVs", "sv_count", "Region", "longest_sv"],
        "output_template": "基因{gene}共存在{count}个结构变异:{svs}",
        "example_question": "OsKeNa_01g0001150是否存在结构变异？"
    }
}

# 工具名标准化映射
TOOL_NAME_MAP = {
    "gene_basic_info": "gene_basic_info",
    "genebasicinfoquery": "gene_basic_info",
    "Gene_Basic_Info_Query": "gene_basic_info",
    "gene_function": "gene_function",
    "genefunctionquery": "gene_function",
    "Gene_Function_Query": "gene_function",
    "gene_mutant_info": "gene_mutant_info",
    "genemutantinfoquery": "gene_mutant_info",
    "Gene_Mutant_Info_Query": "gene_mutant_info",
    "ogi_info": "ogi_info",
    "ogiinfoquery": "ogi_info",
    "OGI_Info_Query": "ogi_info",
    "gene_locator": "gene_locator",
    "genelocatorquery": "gene_locator",
    "Gene_Locator_Query": "gene_locator",
    "adjacent_genes": "adjacent_genes",
    "adjacentgenesquery": "adjacent_genes",
    "Adjacent_Genes_Query": "adjacent_genes",
    "homologous_gene_and_expression": "homologous_gene_and_expression",
    "homologousgeneandexpressionquery": "homologous_gene_and_expression",
    "Homologous_Gene_and_Expression_Query": "homologous_gene_and_expression",
    "structural_variation_locator": "structural_variation_locator",
    "structuralvariationlocatorquery": "structural_variation_locator",
    "Structural_Variation_Locator_Query": "structural_variation_locator",
    "structural_variation_link": "structural_variation_link",
    "structuralvariationlinkquery": "structural_variation_link",
    "Structural_Variation_Link_Query": "structural_variation_link",
}


def normalize_tool_name(tool_name: str) -> str:
    """标准化工具名"""
    return TOOL_NAME_MAP.get(tool_name, TOOL_NAME_MAP.get(tool_name.lower(), "gene_basic_info"))


class SyntheticExampleGenerator:
    """
    合成示例生成器
    
    基于 MDR 规则实时生成 Fake Q&A 示例，避免数据泄露
    """
    
    # 合成用的假基因名模板
    FAKE_GENE_TEMPLATES = [
        "LOC_Os{chr:02d}g{num:05d}",
        "Os{chr:02d}g{num:07d}",
        "OsFake_{chr:02d}g{num:07d}.01"
    ]
    
    # 合成用的假品种名
    FAKE_ACCESSIONS = ["FakeAcc1", "FakeAcc2", "TestVariety"]
    
    def __init__(self, adapter: MDRSchemaAdapter):
        self.adapter = adapter
        self.schema = adapter.get_full_schema()
    
    def generate_fake_gene_name(self) -> str:
        """生成假基因名"""
        template = random.choice(self.FAKE_GENE_TEMPLATES)
        return template.format(chr=random.randint(1, 12), num=random.randint(10000, 99999))
    
    def generate_fake_ogi(self) -> str:
        """生成假 OGI"""
        return f"OGI:{random.randint(10000000, 99999999):08d}"
    
    def generate_fake_position(self) -> str:
        """生成假位置"""
        start = random.randint(100000, 9000000)
        end = start + random.randint(1000, 10000)
        return f"{start}-{end}"
    
    def generate_fake_chromosome(self) -> str:
        """生成假染色体"""
        return f"Chr{random.randint(1, 12):02d}"
    
    def generate_fake_mutant(self) -> str:
        """生成假突变体"""
        return f"22NB{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(10, 99)}"
    
    def generate_fake_sv_name(self) -> str:
        """生成假 SV 名称"""
        acc = random.choice(self.FAKE_ACCESSIONS)
        sv_type = random.choice(["DEL", "INS", "TRA", "INV"])
        return f"{acc}_Ref_{sv_type}{random.randint(100000, 999999)}"
    
    def generate_example(self, tool_name: str) -> Dict[str, str]:
        """
        生成合成示例
        
        Args:
            tool_name: 工具名
        
        Returns:
            {
                "question": "合成的问题",
                "thought": "思考过程",
                "tool_call": "工具调用",
                "answer": "合成的答案"
            }
        """
        normalized = normalize_tool_name(tool_name)
        schema = TOOL_SCHEMAS.get(normalized, TOOL_SCHEMAS["gene_basic_info"])
        
        # 根据工具类型生成不同的示例
        if normalized == "gene_basic_info":
            return self._gen_gene_basic_info_example()
        elif normalized == "gene_function":
            return self._gen_gene_function_example()
        elif normalized == "ogi_info":
            return self._gen_ogi_info_example()
        elif normalized == "gene_locator":
            return self._gen_gene_locator_example()
        elif normalized == "adjacent_genes":
            return self._gen_adjacent_genes_example()
        elif normalized == "gene_mutant_info":
            return self._gen_gene_mutant_example()
        elif normalized == "homologous_gene_and_expression":
            return self._gen_expression_example()
        elif normalized == "structural_variation_locator":
            return self._gen_sv_locator_example()
        elif normalized == "structural_variation_link":
            return self._gen_sv_link_example()
        else:
            return self._gen_gene_basic_info_example()
    
    def _gen_gene_basic_info_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        chrom = self.generate_fake_chromosome()
        pos = self.generate_fake_position()
        # ⚠️ 位置查询示例不包含 strand，避免 LLM 在纯位置问题中输出多余信息
        # GT 格式: "基因XXX的位置在ChrXX:起始-终止。" (无 strand)
        
        return {
            "question": f"{gene}在基因组中的位置是什么？",
            "thought": f"用户询问基因{gene}的位置，需要调用gene_basic_info工具",
            "tool_call": f"Gene_Basic_Info_Query('{gene}在基因组中的位置是什么？')",
            "answer": f"基因{gene}的位置在{chrom}:{pos}。"
        }
    
    def _gen_gene_function_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        func = random.choice(["Protein kinase", "Transcription factor", "Unknown function"])
        
        return {
            "question": f"{gene}的功能是什么？",
            "thought": f"用户询问基因{gene}的功能注释，需要调用gene_function工具",
            "tool_call": f"Gene_Function_Query('{gene}的功能是什么？')",
            "answer": f"基因{gene}的功能注释为{func}。"
        }
    
    def _gen_ogi_info_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        ogi = self.generate_fake_ogi()
        count = random.randint(10, 100)
        
        return {
            "question": f"{gene}的OGI编号是多少？",
            "thought": f"用户询问基因{gene}的OGI编号，需要调用ogi_info工具",
            "tool_call": f"OGI_Info_Query('{gene}的OGI编号是多少？')",
            "answer": f"基因{gene}属于{ogi}，该分组共有{count}个成员基因。"
        }
    
    def _gen_gene_locator_example(self) -> Dict[str, str]:
        acc = random.choice(["G46", "Azucena", "Y3551"])
        chrom = self.generate_fake_chromosome()
        start = random.randint(100, 900)
        end = start + random.randint(50, 100)
        genes = [self.generate_fake_gene_name() for _ in range(random.randint(2, 5))]
        
        return {
            "question": f"{acc}的{chrom}在{start}kb到{end}kb之间有哪些基因？",
            "thought": f"用户询问{acc}品种{chrom}的区域基因，需要调用gene_locator工具",
            "tool_call": f"Gene_Locator_Query('{acc}的{chrom}在{start}kb到{end}kb之间有哪些基因？')",
            "answer": f"在{acc}的{chrom}:{start*1000}-{end*1000}区域内共有{len(genes)}个基因:" + "".join(f"{i+1}.{g} " for i, g in enumerate(genes))
        }
    
    def _gen_adjacent_genes_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        direction = random.choice(["上游", "下游"])
        count = random.randint(2, 5)
        neighbors = [self.generate_fake_gene_name() for _ in range(count)]
        
        return {
            "question": f"{gene}的{direction}最近的{count}个基因是什么？",
            "thought": f"用户询问基因{gene}的{direction}邻近基因，需要调用adjacent_genes工具",
            "tool_call": f"Adjacent_Genes_Query('{gene}的{direction}最近的{count}个基因是什么？')",
            "answer": f"基因{gene}的{direction}最近{count}个基因包括：" + "".join(f"{i+1}.{n} " for i, n in enumerate(neighbors))
        }
    
    def _gen_gene_mutant_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        mutants = [self.generate_fake_mutant() for _ in range(random.randint(1, 3))]
        
        return {
            "question": f"{gene}有哪些突变体？",
            "thought": f"用户询问基因{gene}的突变体信息，需要调用gene_mutant_info工具",
            "tool_call": f"Gene_Mutant_Info_Query('{gene}有哪些突变体？')",
            "answer": f"基因{gene}共有{len(mutants)}个突变体:" + "".join(f"{i+1}.{m} " for i, m in enumerate(mutants))
        }
    
    def _gen_expression_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        leaf = round(random.uniform(0, 50), 2)
        root = round(random.uniform(0, 50), 2)
        
        return {
            "question": f"{gene}在不同组织中的表达量是多少？",
            "thought": f"用户询问基因{gene}的表达量，需要调用homologous_gene_and_expression工具",
            "tool_call": f"Homologous_Gene_and_Expression_Query('{gene}在不同组织中的表达量是多少？')",
            "answer": f"基因{gene}在叶片中的表达量为{leaf}，在根部的表达量为{root}。"
        }
    
    def _gen_sv_locator_example(self) -> Dict[str, str]:
        gene = self.generate_fake_gene_name()
        count = random.randint(1, 10)
        svs = [self.generate_fake_sv_name() for _ in range(min(count, 3))]
        
        return {
            "question": f"{gene}是否存在结构变异？",
            "thought": f"用户询问基因{gene}的结构变异，需要调用structural_variation_locator工具",
            "tool_call": f"Structural_Variation_Locator_Query('{gene}是否存在结构变异？')",
            "answer": f"基因{gene}共存在{count}个结构变异:" + "".join(f"{i+1}.{s} " for i, s in enumerate(svs))
        }
    
    def _gen_sv_link_example(self) -> Dict[str, str]:
        sv = self.generate_fake_sv_name()
        te_types = random.sample(["long_terminal_repeat", "Gypsy_LTR_retrotransposon", "repeat_region"], k=random.randint(1, 2))
        
        return {
            "question": f"{sv}关联了哪些转座元件？",
            "thought": f"用户询问结构变异{sv}的TE注释，需要调用structural_variation_link工具",
            "tool_call": f"Structural_Variation_Link_Query('{sv}关联了哪些转座元件？')",
            "answer": f"结构变异{sv}关联的装作元件包括：" + "".join(f"{i+1}.{t} " for i, t in enumerate(te_types))
        }


class PromptBuilder:
    """
    S-CoT × RAPS 提示生成器 (Dynamic MDR Version)
    
    核心改进：
    1. 从 Neo4j 动态获取 MDR Schema
    2. 基于 MDR 规则合成 Few-shot 示例（避免数据泄露）
    3. 集成 GoT-CI 约束
    """
    
    def __init__(
        self,
        schema_adapter: Optional[MDRSchemaAdapter] = None,
        prompts_dir: Optional[str] = None
    ):
        if schema_adapter is None:
            schema_adapter = MDRSchemaAdapter()
        self.schema_adapter = schema_adapter
        
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        self.prompts_dir = Path(prompts_dir)
        
        # 合成示例生成器
        self.example_generator = SyntheticExampleGenerator(schema_adapter)
        
        # 加载模板
        self.system_template = self._load_template("system.md")
        self.constraints_template = self._load_template("constraints.md")
        
        print("  ✓ PromptBuilder initialized (Dynamic MDR Mode)", flush=True)
    
    def _load_template(self, filename: str) -> str:
        template_path = self.prompts_dir / filename
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        return ""
    
    def _get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        normalized = normalize_tool_name(tool_name)
        return TOOL_SCHEMAS.get(normalized, TOOL_SCHEMAS["gene_basic_info"])
    
    def _format_tool_schema_for_prompt(self, tool_name: str) -> str:
        """格式化工具 Schema"""
        schema = self._get_tool_schema(tool_name)
        normalized = normalize_tool_name(tool_name)
        
        lines = []
        lines.append(f"**指定工具**: `{normalized}`")
        lines.append(f"**功能**: {schema['description']}")
        
        return "\n".join(lines)
    
    def _generate_synthetic_examples(self, tool_name: str, k: int = 2) -> List[Dict[str, str]]:
        """
        生成合成的 Few-shot 示例
        
        Args:
            tool_name: 工具名
            k: 示例数量
        
        Returns:
            示例列表
        """
        examples = []
        for _ in range(k):
            ex = self.example_generator.generate_example(tool_name)
            examples.append(ex)
        return examples
    
    def _format_synthetic_examples(self, examples: List[Dict[str, str]]) -> str:
        """格式化合成示例"""
        if not examples:
            return ""
        
        lines = ["## Few-shot Examples (Synthetic)\n"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"**示例 {i}:**")
            lines.append(f"问题: {ex['question']}")
            lines.append(f"思考: {ex['thought']}")
            lines.append(f"工具调用: {ex['tool_call']}")
            lines.append(f"答案: {ex['answer']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_mdr_constraints_text(self, tool_name: str) -> str:
        """获取 MDR 约束文本"""
        constraints = self.schema_adapter.get_constraints(tool_name)
        vd = constraints.get("vd_constraints", {})
        mps = self.schema_adapter.get_mappings()
        
        lines = []
        
        # 值域约束
        if vd:
            lines.append("**值域约束 (从数据库动态获取):**")
            for field, values in vd.items():
                if isinstance(values, list) and len(values) <= 15:
                    lines.append(f"  - {field}: {values}")
                elif isinstance(values, list):
                    lines.append(f"  - {field}: {values[:10]}... (共{len(values)}个)")
        
        # 别名映射（精选）
        key_mappings = {k: v for k, v in mps.items() if k in ["正链", "负链", "缺失", "插入", "上游", "下游"]}
        if key_mappings:
            lines.append(f"**别名映射:** {json.dumps(key_mappings, ensure_ascii=False)}")
        
        return "\n".join(lines) if lines else ""

    def _get_ontology_text(self, tool_name: str, mode: str) -> str:
        """获取本体信息摘要（DEC/数据元/工具字段）"""
        if mode == "none":
            return ""

        schema = self.schema_adapter.get_full_schema()
        dec_list = schema.get("DEC", []) or []
        data_elements = schema.get("DataElements", {}) or {}
        normalized = normalize_tool_name(tool_name)
        tool_def = schema.get("Tools", {}).get(normalized, {}) or {}

        lines = []

        # DEC 列表
        if dec_list:
            if mode == "simple":
                sample = dec_list[:10]
                suffix = f"...(共{len(dec_list)}个)" if len(dec_list) > len(sample) else ""
                lines.append(f"**数据元概念(DEC)**: {', '.join(sample)}{suffix}")
            else:
                lines.append(f"**数据元概念(DEC)**: {', '.join(dec_list)}")

        # 工具字段（简单本体也展示）
        in_fields = tool_def.get("in", [])
        out_fields = tool_def.get("out", [])
        if in_fields or out_fields:
            lines.append(f"**工具字段**: 输入={in_fields} 输出={out_fields}")

        # DataElements（仅 full 模式）
        if mode == "full" and data_elements:
            lines.append("**数据元(DataElements)**:")
            items = sorted(data_elements.items(), key=lambda x: x[0])
            max_items = 60
            for name, info in items[:max_items]:
                dec = info.get("dec") or ""
                vd = info.get("value_domain") or ""
                parts = []
                if dec:
                    parts.append(f"DEC={dec}")
                if vd:
                    parts.append(f"VD={vd}")
                detail = " | ".join(parts)
                if detail:
                    lines.append(f"  - {name}: {detail}")
                else:
                    lines.append(f"  - {name}")
            if len(items) > max_items:
                lines.append(f"  - ...(共{len(items)}个)")

        return "\n".join(lines) if lines else ""
    
    def build_prompt(
        self,
        question: str,
        tool_name: str,
        method: str = "s_cot_raps",
        split_type: Optional[str] = None,
        use_dynamic_schema: bool = True,
        include_vd: bool = True,
        include_mps: bool = True,
        include_few_shot: bool = True,
        ontology_mode: str = "none"
    ) -> str:
        """
        构建完整提示
        
        Args:
            question: 用户问题
            tool_name: 工具名
            method: 提示方法
            split_type: 问题类型
            use_dynamic_schema: 使用动态 Schema
            include_vd: 包含值域约束
            include_mps: 包含别名映射
            include_few_shot: 包含 Few-shot 示例
        
        Returns:
            完整的提示词
        """
        # 支持本体消融方法（ont_full / ont_simple）
        base_method = method
        if method.startswith("ont_"):
            ontology_mode = method.replace("ont_", "", 1)
            base_method = "s_cot_raps"

        # 根据 method 调整参数
        if base_method == "zero":
            include_few_shot = False
            include_vd = False
            include_mps = False
        elif base_method == "few":
            include_few_shot = True
            include_vd = False
            include_mps = False
        elif base_method == "no_vd":
            include_vd = False
        elif base_method == "no_mps":
            include_mps = False
        elif base_method == "simple":
            include_few_shot = False
            include_vd = False
            include_mps = False
        
        normalized_tool = normalize_tool_name(tool_name)
        
        # Zero-shot 简化版
        if base_method == "zero":
            return f"""你是水稻基因组数据库助手。

问题：{question}

请调用 {normalized_tool} 工具查询，然后用中文自然语言回答。
输出格式示例：
- 位置: "基因XXX的位置在ChrXX:起始-终止。"
- 链方向: "基因XXX位于正链/负链。"
- 序列: "基因XXX的DNA序列可以通过点击[链接](URL)进行查看。"

不要输出JSON，只用自然语言回答。"""
        
        # ========== 完整版提示 ==========
        parts = []
        
        # 1. System template
        if self.system_template:
            parts.append(self.system_template)
        
        # 2. 指定工具
        parts.append("\n## 指定工具\n")
        parts.append(self._format_tool_schema_for_prompt(tool_name))
        
        # 3. 输出格式
        if self.constraints_template:
            parts.append("\n## 输出格式\n")
            parts.append(self.constraints_template)
        
        # 4. MDR 约束 (动态从 Neo4j 获取)
        if include_vd or include_mps:
            mdr_text = self._get_mdr_constraints_text(tool_name)
            if mdr_text:
                parts.append("\n## MDR 数据约束 (动态获取)\n")
                parts.append(mdr_text)

        # 4.5 本体信息（可选消融）
        if ontology_mode != "none":
            ont_text = self._get_ontology_text(tool_name, ontology_mode)
            if ont_text:
                parts.append("\n## 本体信息 (Ontology)\n")
                parts.append(ont_text)
        
        # 5. 合成 Few-shot 示例（不使用真实数据集）
        if include_few_shot:
            examples = self._generate_synthetic_examples(tool_name, k=2)
            examples_text = self._format_synthetic_examples(examples)
            if examples_text:
                parts.append("\n" + examples_text)
        
        # 6. 用户问题
        parts.append(f"\n## 当前问题\n\n{question}")
        
        # 7. 执行指令
        parts.append(f"""
## 执行步骤

1. 调用工具 `{normalized_tool}` 查询数据库
2. 用**中文自然语言**完整回答问题（不要输出JSON）
3. 严格使用工具返回的真实数据，不要编造

**输出格式示例**（必须严格遵循）:
- 位置查询: "基因XXX的位置在ChrXX:起始-终止。"
- 链方向查询: "基因XXX位于正链/负链。"
- 序列查询: "基因XXX的DNA序列可以通过点击[链接](URL)进行查看。"
- OGI查询: "基因XXX属于OGI:XXXXXXXX，该分组共有N个成员基因。"
- 多结果: 先说数量，再用有序列表(1. 2. 3.)

/no_think
""")
        
        return "\n".join(parts)


if __name__ == "__main__":
    # 测试
    print("=== Prompt Builder Test (Dynamic MDR) ===\n")
    
    builder = PromptBuilder()
    
    # 测试构建提示
    question = "LOC_Os08g02050在基因组中的位置是什么？"
    prompt = builder.build_prompt(question, "gene_basic_info")
    
    print("Generated Prompt:")
    print("=" * 60)
    print(prompt[:2000])
    print("...")
    print("=" * 60)
    print(f"\nTotal length: {len(prompt)} chars")
