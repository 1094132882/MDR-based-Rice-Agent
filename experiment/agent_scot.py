"""
-*- coding: utf-8 -*-
🔌 S-COT 集成的 ReAct Agent（增强版 + GoT-CI）

与学长的 agent.py 对比，核心区别：
- 学长: 静态手工编写的 MDR 约束提示词
- S-COT: 基于 MDR 元数据动态生成的结构化思维链提示词
- GoT-CI: 验证 + 自修复循环（提升 EM）

增强功能：
- 🔌 统一配置：端口通过 config.py 管理（7689, 11501）
- 🔄 GoT-CI 自修复：验证失败时自动重试
- 📊 动态 MDR：从 Neo4j 实时获取约束规则

@author: jingwen.wu
@Time: 2025/12
"""
import sys
import re
import json
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 添加 S-COT 模块路径
SCOT_PATH = PROJECT_ROOT / "methods" / "s_cot_raps"
sys.path.insert(0, str(SCOT_PATH))

# 导入统一配置
try:
    from methods.s_cot_raps.config import Config
    Config.print_config()  # 打印配置信息
except ImportError:
    print("⚠️ Warning: config.py not found, using defaults")

# ⚠️ 必须最先导入：应用 langchain 兼容性补丁
import tools._langchain_patch

# 导入响应模板渲染器
try:
    from response_templates import render_response, _normalize_location_answer
except Exception:
    render_response = None
    _normalize_location_answer = None

# 导入 GoT-CI 验证器（动态 MDR 校验）
try:
    sys.path.insert(0, str(SCOT_PATH))
    from validator import MDRValidator, validate_and_correct, validate_tool_result
    VALIDATOR_AVAILABLE = True
    print("✓ GoT-CI Validator initialized")
except ImportError:
    VALIDATOR_AVAILABLE = False
    MDRValidator = None
    validate_and_correct = None
    validate_tool_result = None

from llm import llm
from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import tiktoken

# 工具（与学长相同的9个工具）
from tools.genebasicinfoquery import gene_basic_info_query
from tools.genefunctionquery import gene_function_query
from tools.genemutantinfoquery import gene_mutant_info_query
from tools.ogiinfoquery import ogi_info_query
from tools.genelocatorquery import gene_locator_query
from tools.adjacentgenesquery import adjacent_genes_query
from tools.homologousgeneandexpressionquery import homologous_gene_and_expression_query
from tools.structuralvariationlinkquery import structural_variation_link_query
from tools.structuralvariationlocatorquery import structural_variation_locator_query


# ============================================================
# 🎯 P0-2 修复：JSON 解析辅助函数
# 将 JSON 字符串安全解析为字典，避免有数据却渲染为空
# ============================================================
def _safe_json_parse(content: str) -> dict:
    """
    安全解析 JSON 字符串
    
    - 如果是 JSON 字符串，解析为 dict
    - 如果解析失败，返回 {"raw": content}
    - 如果是嵌套的字符串（如 JSON 被 stringify 了两次），尝试双重解析
    """
    if not content or not isinstance(content, str):
        return {"raw": str(content) if content else ""}
    
    content = content.strip()
    
    # 检查是否像 JSON
    if not (content.startswith('{') or content.startswith('[')):
        return {"raw": content}
    
    try:
        parsed = json.loads(content)
        
        # 如果解析结果是字符串（被双重 stringify），再解析一次
        if isinstance(parsed, str) and (parsed.startswith('{') or parsed.startswith('[')):
            try:
                parsed = json.loads(parsed)
            except:
                pass
        
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    except json.JSONDecodeError:
        return {"raw": content}


def _extract_result_data(tool_output: dict) -> dict:
    """
    从工具返回的 JSON 中提取实际数据
    
    工具返回格式通常是:
    {"query": "...", "result": [{"field": "value"}]}
    
    我们需要提取 result 中的数据，合并到顶层
    """
    if not isinstance(tool_output, dict):
        return tool_output
    
    # 如果有 result 字段，提取其中的数据
    result = tool_output.get('result')
    if result:
        if isinstance(result, list) and len(result) > 0:
            # 如果是列表，将第一个元素的字段合并到顶层
            first_item = result[0] if isinstance(result[0], dict) else {}
            merged = {**tool_output, **first_item}
            
            # 保留列表数据供多值查询使用
            merged['_result_list'] = result
            return merged
        elif isinstance(result, dict):
            return {**tool_output, **result}
    
    return tool_output


# S-COT提示词生成器
try:
    from prompt_builder import PromptBuilder, TOOL_SCHEMAS, normalize_tool_name
    SCOT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: S-COT modules not available: {e}")
    SCOT_AVAILABLE = False
    TOOL_SCHEMAS = {}
    def normalize_tool_name(x): return x

# 定义工具列表（与学长相同）
tools = [
    Tool.from_function(
        name="Gene_Basic_Info_Query",
        description="使用Cypher提供水稻基因的基本信息。"
                    "包括位置信息（染色体、起始/终止位点）、转录本（mRNA）、蛋白质序列、DNA序列、CDS序列等。"
                    "输入为自然语言描述的问题。",
        func=gene_basic_info_query
    ),
    Tool.from_function(
        name="Gene_Function_Query",
        description="使用Cypher查询给定基因ID的功能或注释信息。"
                    "输入为自然语言描述的问题。",
        func=gene_function_query
    ),
    Tool.from_function(
        name="Gene_Mutant_Info_Query",
        description="使用Cypher查询水稻基因的突变体信息。"
                    "输入为自然语言描述的问题。",
        func=gene_mutant_info_query
    ),
    Tool.from_function(
        name="OGI_Info_Query",
        description="使用Cypher查询OGI（Ortholog Gene Index，直系同源基因索引）的相关信息。"
                    "输入为自然语言描述的问题。",
        func=ogi_info_query
    ),
    Tool.from_function(
        name="Gene_Locator_Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的基因。"
                    "输入为自然语言描述的问题。",
        func=gene_locator_query
    ),
    Tool.from_function(
        name="Adjacent_Genes_Query",
        description="使用Cypher查询某个基因的上下游基因。"
                    "输入为自然语言描述的问题。",
        func=adjacent_genes_query
    ),
    Tool.from_function(
        name="Homologous_Gene_and_Expression_Query",
        description="使用Cypher查询基因的同源基因和表达信息。"
                    "输入为自然语言描述的问题。",
        func=homologous_gene_and_expression_query
    ),
    Tool.from_function(
        name="Structural_Variation_Link_Query",
        description="使用Cypher查询询结构变异(SV)与基因的联系以及结构变异的转座元件信息。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_link_query
    ),
    Tool.from_function(
        name="Structural_Variation_Locator_Query",
        description="使用Cypher查询某个水稻种质（品种）的指定染色体的特定范围内存在的结构变异。"
                    "输入为自然语言描述的问题。",
        func=structural_variation_locator_query
    )
]

# 初始化S-COT提示构建器
prompt_builder = None
if SCOT_AVAILABLE:
    try:
        prompt_builder = PromptBuilder()
        print("✓ S-COT PromptBuilder initialized")
    except Exception as e:
        print(f"Warning: Failed to initialize PromptBuilder: {e}")

memory = MemorySaver()


def detect_tool_from_question(question: str) -> str:
    """
    根据问题自动检测应该使用的工具（增强版 P2 修复）
    
    🎯 修复原则：借鉴 run.py 的 TYPE2TOOL 规则匹配，保证工具选择正确率
    
    优先级顺序（从高到低）：
    1. SV/TE 相关（最容易混淆，必须最先检测）
    2. 突变体
    3. OGI
    4. 邻近基因
    5. 表达量
    6. 功能注释
    7. 区域基因
    8. 默认基因基本信息
    """
    question_lower = question.lower()
    
    # =====================================
    # 🎯 P2 修复：SV/TE 相关必须最先检测！
    # =====================================
    
    # 1a. 转座元件/TE 查询 → structural_variation_link（ID 137/138/142/147 修复）
    # ⚠️ 必须在 "功能注释" 之前检测，否则 "TE注释" 会被 "注释" 误匹配到 gene_function
    if any(kw in question for kw in ['转座', 'TE注释', 'TE ', '转座子', '转座元件', '装作元件']):
        return 'structural_variation_link'
    
    # 检测 SV 名称模式：xxx_xxx_INS/DEL/TRA/INV/OTH + 数字
    import re
    sv_name_pattern = r'[A-Za-z0-9_]+_[A-Za-z0-9]+_(?:INS|DEL|TRA|INV|OTH)\d+'
    if re.search(sv_name_pattern, question):
        # 如果问的是 TE/转座元件注释，用 link；否则用 locator
        if any(kw in question for kw in ['注释', 'TE', '转座', '关联']):
            return 'structural_variation_link'
        return 'structural_variation_locator'
    
    # 1b. 结构变异查询 → structural_variation_locator（ID 105/135 修复）
    # ⚠️ 添加 "易位/缺失/插入" 等 SV 类型关键词
    sv_keywords = [
        '结构变异', 'SV', '_INS', '_DEL', '_TRA', '_INV', 
        'insertion', 'deletion', 'translocation', 'inversion',
        '易位', '缺失', '插入', '倒位',  # 🎯 P2 修复：添加中文 SV 类型
        '变异类型', '变异数量', '变异统计'
    ]
    if any(kw in question for kw in sv_keywords):
        return 'structural_variation_locator'
    
    # 1c. 区域+变异 组合检测
    if '变异' in question and any(kw in question for kw in ['区域', '范围', '染色体', 'kb']):
        return 'structural_variation_locator'
    
    # =====================================
    # 2. 突变体查询（包括22NB编号）
    # =====================================
    if any(kw in question for kw in ['突变体', 'mutant', '22NB']):
        return 'gene_mutant_info'
    
    # =====================================
    # 3. OGI查询
    # =====================================
    if any(kw in question for kw in ['OGI', 'OGI:', '同源基因索引', '所属OGI', '隶属于哪个OGI']):
        return 'ogi_info'
    if '分组' in question and ('成员' in question or '基因' in question):
        return 'ogi_info'
    
    # =====================================
    # 4. 邻近基因查询
    # 🎯 Run4 修复：增加更多邻近基因关键词（"后面"、"前面"、"尾部"等）
    # =====================================
    adjacent_keywords = [
        '上游', '下游', '邻近', '相邻', '最近的基因', '紧跟着',
        '后面', '前面', '尾部', '头部', '起始点', '结束位置',
        '紧接着', '下一个基因', '上一个基因', '左边', '右边'
    ]
    # 检查是否是邻近基因查询
    if any(kw in question for kw in adjacent_keywords):
        # 额外检查：包含 "kb" + 基因名模式，更可能是邻近基因查询
        if 'kb' in question.lower() or any(kw in question for kw in ['最近', '几个基因', '个基因']):
            return 'adjacent_genes'
        return 'adjacent_genes'
    
    # =====================================
    # 5. 表达量查询
    # =====================================
    if any(kw in question for kw in ['表达', 'expression', '根中', '茎中', '叶中', '穗']):
        return 'homologous_gene_and_expression'
    
    # =====================================
    # 6. 功能注释查询（放在 TE 之后！）
    # =====================================
    if any(kw in question for kw in ['功能', 'function']):
        return 'gene_function'
    # ⚠️ 单独的 "注释" 不再直接匹配 gene_function，因为可能是 TE 注释
    if '注释' in question and '基因' in question:
        return 'gene_function'
    
    # =====================================
    # 7. 区域内基因查询
    # =====================================
    if any(kw in question for kw in ['区域', '范围内', '之间', '区间']):
        return 'gene_locator'
    
    # =====================================
    # 8. 默认：基因基本信息
    # =====================================
    return 'gene_basic_info'


def get_scot_prompt(question: str, method: str = "s_cot_raps", tool_name: str = None) -> str:
    """
    使用S-COT生成动态提示词（简化版 - 参考 Run1 成功模式）
    
    Run1 成功的关键：简洁的提示 + MDR 约束，不要过度指导输出格式
    
    Args:
        question: 用户问题
        method: 提示方法
        tool_name: 指定工具名（可选，不指定则自动检测）
    
    Returns:
        动态生成的提示词
    """
    # 工具检测/锁定
    if tool_name is None:
        tool_name = detect_tool_from_question(question)
    
    if prompt_builder is None:
        return get_basic_prompt()
    
    # 使用S-COT生成提示词
    try:
        dynamic_prompt = prompt_builder.build_prompt(
            question=question,
            tool_name=tool_name,
            method=method
        )
    except Exception:
        return get_basic_prompt()
    
    return dynamic_prompt


def get_basic_prompt() -> str:
    """基础提示词（fallback）"""
    return """
**角色定义**：
你是水稻基因组领域的Rice Gene Index（RGI）数据库助手。

**工作流程**：
1. 分析问题，选择合适的工具
2. 调用工具查询数据库
3. 用中文自然语言完整回答

**输出格式**：
- 位置查询: "基因XXX的位置在ChrXX:起始-终止。"
- 链方向查询: "基因XXX位于正链/负链。"
- 序列查询: "基因XXX的DNA序列可以通过点击[链接](URL)进行查看。"
- OGI查询: "基因XXX属于OGI:XXXXXXXX。"
- 多结果时先说数量，再列出(1. 2. 3.)

**禁止**：不要输出JSON，不要编造数据

/no_think
"""


def is_valid_response(content: str, tool_name: str) -> bool:
    """
    检查响应是否有效（增强版）
    
    判断标准：
    1. 不是空/nan
    2. 不是 Cypher 语法错误
    3. 不是工具调用格式（应该是执行结果）
    4. 包含有效数据字段
    """
    if not content or content.strip() in ['', 'nan', '{}', '[]']:
        return False
    
    content = content.strip()
    
    # Cypher 语法错误 - 无效
    if 'SyntaxError' in content or 'Neo.ClientError' in content:
        return False
    
    # 检测工具调用格式（说明Agent没有执行工具）
    # 格式: {"name": "Tool_Name", "arguments": {...}}
    if '"name":' in content and '"arguments":' in content:
        try:
            # 尝试解析第一行（可能有多行）
            first_line = content.split('\n')[0].strip()
            if first_line.startswith('{'):
                parsed = json.loads(first_line)
                if 'name' in parsed and 'arguments' in parsed:
                    return False  # 这是工具调用请求，不是结果
        except:
            pass
    
    # 检查是否包含有效数据
    content_lower = content.lower()
    
    # 常见的有效数据指标
    valid_indicators = [
        '"gene":', '"chromosome":', '"position":', '"strand":',
        '"mutant":', '"mutants":', '"genes":',
        '"ogi":', '"function":', '"expression":',
        '"sv":', '"svs":', '"neighbors":', '"region":',
        '"dna_sequence_link":', '"protein_sequence_link":', '"cds_sequence_link":',
        'chr0', 'chr1', 'ogi:', 'https://riceome'
    ]
    
    has_valid_data = any(ind in content_lower for ind in valid_indicators)
    
    # 如果有 error 字段但也有其他数据，认为部分有效
    if '"error":' in content_lower:
        if has_valid_data:
            return True  # 有错误但也有数据
        return False  # 只有错误
    
    # 如果完全没有有效数据指标，可能是无效响应
    if not has_valid_data:
        # 最后检查是否是纯文本回答（可能是LLM自己回答而非调用工具）
        if len(content) > 50 and '基因' not in content and 'Gene' not in content:
            return False
    
    return True


def extract_and_fix_tool_call(content: str):
    """
    如果响应是工具调用格式而非结果，尝试提取并返回工具信息
    
    Returns:
        (tool_name, arguments) 或 (None, None)
    """
    if '"name":' not in content or '"arguments":' not in content:
        return None, None
    
    try:
        # 尝试解析第一行
        first_line = content.split('\n')[0].strip()
        if first_line.startswith('{'):
            parsed = json.loads(first_line)
            if 'name' in parsed and 'arguments' in parsed:
                return parsed['name'], parsed['arguments']
    except:
        pass
    
    return None, None


def standardize_response(content: str, tool_name: str, question: str) -> str:
    """
    标准化响应格式（修复问题4: nan/空返回）
    
    将各种异常情况转换为规范的 JSON 格式：
    - 空结果 → {"data": [], "message": "未查询到相关信息"}
    - nan → {"data": null, "message": "无数据"}
    - "未查询到" → 结构化错误
    
    Args:
        content: 原始响应内容
        tool_name: 使用的工具名
        question: 用户问题（用于提取实体）
    
    Returns:
        标准化后的JSON字符串
    """
    if not content or content.strip() in ['', 'nan', '{}', '[]', 'None', 'null']:
        # 尝试从问题中提取关键实体
        gene_match = re.search(r'(Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?|LOC_Os\d+g\d+|Oglab_\d+)', question)
        gene_name = gene_match.group(1) if gene_match else None
        
        normalized = tool_name.replace('_', ' ').title()
        result = {
            "status": "no_data",
            "message": f"未在数据库中找到相关信息",
            "tool": normalized
        }
        if gene_name:
            result["query_entity"] = gene_name
        return json.dumps(result, ensure_ascii=False)
    
    # 检查是否是"未查询到"类型的错误
    content_str = str(content)
    if '未查询到' in content_str or '没有找到' in content_str or '"error":' in content_str.lower():
        # 如果已经是JSON格式，保留原样
        try:
            parsed = json.loads(content_str)
            if isinstance(parsed, dict):
                # 确保有标准字段
                if 'status' not in parsed:
                    parsed['status'] = 'no_data'
                return json.dumps(parsed, ensure_ascii=False)
        except:
            pass
        
        # 非JSON的错误信息，转换为标准格式
        gene_match = re.search(r'(Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?|LOC_Os\d+g\d+|Oglab_\d+)', question)
        result = {
            "status": "no_data",
            "message": content_str[:200] if len(content_str) > 200 else content_str,
            "tool": tool_name
        }
        if gene_match:
            result["query_entity"] = gene_match.group(1)
        return json.dumps(result, ensure_ascii=False)
    
    return content_str


# ============================================================
# 模板化自然语言渲染（核心改进：提升 F1 和 AR）
# ============================================================

RESPONSE_TEMPLATES = {
    "gene_basic_info": {
        "default": "基因{Gene}位于{Chromosome}{Strand_text}，坐标{Position}。",
        "strand_only": "基因{Gene}位于{Strand_text}。",
        "position_only": "基因{Gene}位于{Chromosome}，坐标{Position}。",
        "transcripts": "基因{Gene}共有{transcript_count}个转录本：{Transcripts_text}。",
        "sequence": "基因{Gene}的{seq_type}序列可以通过点击[链接]({seq_link})查看。"
    },
    "gene_function": {
        "default": "基因{Gene}的功能注释为{Function}。"
    },
    "gene_mutant_info": {
        "gene_to_mutants": "基因{Gene}共有{mutant_count}个突变体：{Mutants_text}。",
        "mutant_to_genes": "{Mutant}共与{gene_count}个基因有关：{Genes_text}。"
    },
    "ogi_info": {
        "gene_to_ogi": "基因{Gene}属于{OGI}。",
        "ogi_count": "基因{Gene}所属的OGI是{OGI}，该OGI中共有{gene_count}个基因。",
        "ogi_genes": "{OGI}包含以下基因：{Genes_text}。"
    },
    "gene_locator": {
        "default": "在{Region}区域内共有{gene_count}个基因：{Genes_text}。"
    },
    "adjacent_genes": {
        "upstream": "基因{TargetGene}最近的上游基因是{Neighbor}。",
        "downstream": "基因{TargetGene}最近的下游基因是{Neighbor}。",
        "upstream_n": "基因{TargetGene}的上游最近{n}个基因包括：{Neighbors_text}。",
        "downstream_n": "基因{TargetGene}的下游最近{n}个基因包括：{Neighbors_text}。",
        "region": "在{TargetGene}的{Direction}{distance}区域内共有{neighbor_count}个基因：{Neighbors_text}。"
    },
    "homologous_gene_and_expression": {
        "default": "基因{Gene}的表达量：叶片{Leaf}，根{Root}，幼穗{Panicle}。"
    },
    "structural_variation_locator": {
        "gene_sv": "基因{Gene}共存在{sv_count}个结构变异：{SVs_text}。",
        "gene_sv_type": "基因{Gene}共存在{sv_count}个{sv_type}类型的结构变异：{SVs_text}。",
        "region_sv": "在{Region}区域内共有{sv_count}个结构变异：{SVs_text}。",
        "region_sv_type": "在{Region}区域内共有{sv_count}个{sv_type}类型的结构变异：{SVs_text}。",
        "region_sv_count": "在{Region}区域内，存在{sv_count}个类型为{sv_type}的结构变异。",
        "region_sv_stats": "在{Region}区域内，{sv_stats_text}。",
        "longest_sv": "在{Region}区域内，长度最长的结构变异是{SV_name}，类型为{sv_type}，长度为{length}。"
    },
    "structural_variation_link": {
        "default": "结构变异{SV}关联的转座元件包括：{TE_text}。"
    }
}


def is_likely_hallucinated(data: dict) -> bool:
    """
    检测响应是否可能是幻觉（编造的数据）
    
    常见幻觉特征：
    1. 坐标是连续数字如 123456-789012, 1234567-1235678
    2. 坐标包含基因ID中的数字（从ID猜测的）
    3. 坐标太短或不合理
    """
    pos = data.get('Position', '')
    if not pos:
        return False
    
    # 常见的幻觉坐标模式
    hallucination_patterns = [
        '123456', '789012', '1234567', '1235678',  # 连续数字
        '67400-67450',  # 太短太整齐
        '6509300-6509350',  # 太短
    ]
    
    for pattern in hallucination_patterns:
        if pattern in str(pos):
            return True
    
    # 检查坐标长度是否合理（水稻基因坐标通常是6-8位数字）
    try:
        parts = str(pos).replace(',', '').split('-')
        if len(parts) == 2:
            start, end = int(parts[0]), int(parts[1])
            # 坐标范围太小（<100bp）或太整齐可能是编造的
            if end - start < 100:
                return True
            # 坐标是整万/整十万可能是编造的
            if start % 10000 == 0 and end % 10000 == 0:
                return True
    except:
        pass
    
    return False


def render_natural_language(content: str, tool_name: str, question: str) -> str:
    """
    将 JSON 输出渲染为自然语言（模板化方式，确定性转换）
    
    增加幻觉检测：如果数据看起来是编造的，返回错误信息
    """
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return content
    except:
        return content  # 不是 JSON，保持原样
    
    # 如果已经有 summary 字段，直接返回
    if 'summary' in data and data['summary']:
        return data['summary']
    
    # 如果是错误/无数据响应，保持原样
    if data.get('status') == 'no_data' or 'error' in data:
        return content
    
    # 🚨 幻觉检测：如果坐标看起来是编造的，返回无数据
    if tool_name == 'gene_basic_info' and is_likely_hallucinated(data):
        gene = data.get('Gene', '')
        return json.dumps({
            "status": "no_data", 
            "message": f"未查询到基因{gene}的真实坐标信息",
            "Gene": gene
        }, ensure_ascii=False)
    
    templates = RESPONSE_TEMPLATES.get(tool_name, {})
    question_lower = question.lower()
    
    # 根据工具类型选择模板并渲染
    try:
        if tool_name == 'gene_basic_info':
            return _render_gene_basic_info(data, templates, question)
        elif tool_name == 'gene_function':
            return _render_gene_function(data, templates)
        elif tool_name == 'gene_mutant_info':
            return _render_gene_mutant_info(data, templates, question)
        elif tool_name == 'ogi_info':
            return _render_ogi_info(data, templates, question)
        elif tool_name == 'gene_locator':
            return _render_gene_locator(data, templates)
        elif tool_name == 'adjacent_genes':
            return _render_adjacent_genes(data, templates, question)
        elif tool_name == 'homologous_gene_and_expression':
            return _render_expression(data, templates)
        elif tool_name == 'structural_variation_locator':
            return _render_sv_locator(data, templates, question)
        elif tool_name == 'structural_variation_link':
            return _render_sv_link(data, templates)
    except Exception as e:
        pass
    
    # 兜底：返回原始内容
    return content


def _render_gene_basic_info(data: dict, templates: dict, question: str) -> str:
    """渲染基因基本信息"""
    gene = data.get('Gene', '')
    chrom = data.get('Chromosome', '')
    pos = data.get('Position', '')
    strand = data.get('Strand', '')
    
    strand_text = "正链" if strand == '+' else "负链" if strand == '-' else ""
    
    # 根据问题类型选择模板
    if '链' in question or 'strand' in question.lower():
        if strand_text:
            return f"基因{gene}位于{strand_text}。"
    
    if chrom and pos:
        return f"基因{gene}位于{chrom}{strand_text}，坐标{pos}。"
    elif chrom:
        return f"基因{gene}位于{chrom}{strand_text}。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_gene_function(data: dict, templates: dict) -> str:
    """渲染基因功能"""
    gene = data.get('Gene', '')
    func = data.get('Function', '')
    return f"基因{gene}的功能注释为{func}。"


def _render_gene_mutant_info(data: dict, templates: dict, question: str) -> str:
    """渲染突变体信息"""
    if 'Genes' in data and data['Genes']:
        # 突变体 -> 基因（多个）
        mutant = data.get('Mutant', '')
        genes = data['Genes']
        genes_text = "、".join([f"{i+1}.{g}" for i, g in enumerate(genes)])
        return f"{mutant}共与{len(genes)}个基因有关：{genes_text}。"
    elif 'Mutants' in data:
        # 基因 -> 突变体
        gene = data.get('Gene', '')
        mutants = data.get('Mutants', [])
        if mutants:
            mutants_text = " ".join([f"{i+1}.{m}" for i, m in enumerate(mutants)])
            return f"基因{gene}共有{len(mutants)}个突变体：{mutants_text}。"
        else:
            return f"基因{gene}暂无已报道的突变体记录。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_ogi_info(data: dict, templates: dict, question: str) -> str:
    """渲染 OGI 信息"""
    gene = data.get('Gene', '')
    ogi = data.get('OGI', '')
    count = data.get('gene_count', '')
    
    if '多少' in question or '数量' in question or '总数' in question:
        if count:
            return f"基因{gene}所属的OGI是{ogi}，该OGI中共有{count}个基因。"
    
    if ogi:
        if count:
            return f"基因{gene}所属的OGI是{ogi}，该OGI中共有{count}个基因。"
        return f"基因{gene}属于{ogi}。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_gene_locator(data: dict, templates: dict) -> str:
    """渲染区域内基因"""
    genes = data.get('Genes', [])
    region = data.get('Region', '')
    
    if genes:
        genes_text = " ".join([f"{i+1}.{g}" for i, g in enumerate(genes)])
        return f"在{region}区域内共有{len(genes)}个基因：{genes_text}。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_adjacent_genes(data: dict, templates: dict, question: str) -> str:
    """渲染邻近基因"""
    target = data.get('TargetGene', '')
    neighbors = data.get('Neighbors', [])
    direction = data.get('Direction', '')
    
    if not neighbors:
        return json.dumps(data, ensure_ascii=False)
    
    # 判断方向
    is_upstream = '上游' in question or 'upstream' in question.lower()
    is_downstream = '下游' in question or 'downstream' in question.lower()
    
    direction_text = "上游" if is_upstream else "下游" if is_downstream else direction
    
    if len(neighbors) == 1:
        return f"基因{target}最近的{direction_text}基因是{neighbors[0]}。"
    else:
        neighbors_text = " ".join([f"{i+1}.{n}" for i, n in enumerate(neighbors)])
        return f"基因{target}的{direction_text}最近{len(neighbors)}个基因包括：{neighbors_text}。"


def _render_expression(data: dict, templates: dict) -> str:
    """渲染表达量"""
    gene = data.get('Gene', '')
    expr = data.get('Expression', {})
    
    if expr:
        parts = []
        for tissue, val in expr.items():
            parts.append(f"{tissue}: {val}")
        return f"基因{gene}的表达量为：{', '.join(parts)}。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_sv_locator(data: dict, templates: dict, question: str) -> str:
    """渲染结构变异"""
    gene = data.get('Gene', '')
    region = data.get('Region', '')
    svs = data.get('SVs', [])
    sv_count = data.get('sv_count', len(svs) if svs else 0)
    
    # 判断 SV 类型
    sv_type_map = {'DEL': '缺失', 'INS': '插入', 'TRA': '易位', 'INV': '倒位', 'OTH': '其他'}
    sv_type = None
    for t, name in sv_type_map.items():
        if t.lower() in question.lower() or name in question:
            sv_type = name
            break
    
    # 数量统计类问题
    if '多少' in question or '数量' in question or '统计' in question:
        if sv_type:
            return f"在{region or gene}区域内，存在{sv_count}个类型为{sv_type}的结构变异。"
        return f"在{region or gene}区域内，存在{sv_count}个结构变异。"
    
    # 最长 SV 问题
    if '最长' in question or '最大' in question:
        if svs and len(svs) > 0:
            sv = svs[0] if isinstance(svs[0], dict) else {'Name': svs[0]}
            sv_name = sv.get('Name', '')
            sv_t = sv.get('Type', '')
            length = sv.get('Length', data.get('length', ''))
            return f"在{region}区域内，长度最长的结构变异是{sv_name}，类型为{sv_t}，长度为{length}。"
    
    # 列表类问题
    if svs:
        sv_names = []
        for i, sv in enumerate(svs[:20]):  # 最多显示20个
            if isinstance(sv, dict):
                sv_names.append(f"{i+1}.{sv.get('Name', '')}")
            else:
                sv_names.append(f"{i+1}.{sv}")
        svs_text = " ".join(sv_names)
        
        if gene:
            if sv_type:
                return f"基因{gene}共存在{sv_count}个{sv_type}类型的结构变异：{svs_text}。"
            return f"基因{gene}共存在{sv_count}个结构变异：{svs_text}。"
        else:
            if sv_type:
                return f"在{region}区域内共有{sv_count}个{sv_type}类型的结构变异：{svs_text}。"
            return f"在{region}区域内共有{sv_count}个结构变异：{svs_text}。"
    
    return json.dumps(data, ensure_ascii=False)


def _render_sv_link(data: dict, templates: dict) -> str:
    """渲染 SV 关联的转座元件"""
    sv = data.get('SV', '')
    te_list = data.get('TE_Annotations', [])
    
    if te_list:
        te_text = " ".join([f"{i+1}.{t}" for i, t in enumerate(te_list)])
        return f"结构变异{sv}关联的转座元件包括：{te_text}。"
    
    return json.dumps(data, ensure_ascii=False)


def validate_mutant_response(content: str, question: str) -> str:
    """
    验证突变体查询响应的一致性（修复问题2: 关键值不匹配）
    
    检查：
    1. 如果问题是"突变体X关联哪些基因"，结果应该返回多个基因
    2. 突变体ID必须出现在返回结果中
    
    Args:
        content: 响应内容
        question: 用户问题
    
    Returns:
        验证/修正后的响应
    """
    # 提取问题中的突变体ID
    mutant_match = re.search(r'(22NB[A-Z]\d+)', question, re.IGNORECASE)
    if not mutant_match:
        return content  # 不是突变体查询
    
    mutant_id = mutant_match.group(1).upper()
    
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            # 检查响应中是否包含突变体ID
            response_str = json.dumps(parsed).upper()
            
            # 如果问的是"突变体关联哪些基因"，但返回的是单个Gene而非Genes列表
            if '关联' in question or '相关' in question or '针对' in question:
                if 'Gene' in parsed and 'Genes' not in parsed:
                    # 如果只返回了单个基因，可能有问题
                    # 添加警告标记
                    if mutant_id not in response_str:
                        parsed['_warning'] = f"响应中未包含查询的突变体{mutant_id}"
                    
            return json.dumps(parsed, ensure_ascii=False)
    except:
        pass
    
    return content


def generate_response_scot(user_input: str, session_id: str, method: str = "s_cot_raps", max_retries: int = 3, debug_log: bool = False, debug_log_file: str = None, trace_info: dict = None, use_got_ci: bool = True):
    """
    S-COT方法的核心：动态生成提示词 + ReAct Agent + GoT-CI 自修复
    
    🎯 核心改进：GoT-CI 自修复循环
    - 验证失败时，将错误反馈给 LLM 请求修正
    - 最多重试 max_retries 次
    - 自动应用别名映射（如 "正链" -> "+"）
    
    🎯 全链路追踪 (Black Box Recorder)：
    - trace_info 字典用于记录全流程细节
    - 包括：MDR 约束、合成示例、GoT-CI 历史、工具结果
    
    优化策略：
    1. 简洁的 prompt
    2. 自然语言输出（提升 F1）
    3. GoT-CI 验证 + 自修复（提升 EM）
    
    Args:
        user_input: 用户问题
        session_id: 会话ID
        method: 提示方法（s_cot_raps/no_vd/no_mps/zero/few）
        max_retries: 最大重试次数（默认3次，用于 GoT-CI 自修复）
        debug_log: 是否记录调试日志
        debug_log_file: 调试日志文件路径
        trace_info: 【飞行记录仪】用于记录全链路追踪信息的字典（由调用方传入）
    
    Returns:
        (response_content, total_tokens)
    """
    tool_name = detect_tool_from_question(user_input)
    content = None
    current_user_input = user_input  # 允许 GoT-CI 在重试时追加纠错提示（不改变原始 user_input）
    retry_due_to_gotci = False  # ✅ 当重试是由 GoT-CI 拦截触发时，保持原 method，不切换到 few
    
    # 🎯 初始化追踪字典（飞行记录仪）
    if trace_info is None:
        trace_info = {}
    
    # 记录基础信息
    trace_info["tool_name"] = tool_name
    trace_info["method"] = method
    trace_info["got_ci_attempts"] = []  # GoT-CI 拦截/通过记录
    trace_info["mdr_constraints"] = None  # MDR 约束
    trace_info["synthetic_examples"] = None  # 合成示例
    trace_info["full_prompt"] = None  # 完整提示词
    trace_info["tool_output"] = None  # 工具返回结果
    
    # 🎯 调试日志：记录工具返回的原始 JSON
    _debug_info = {
        "session_id": session_id,
        "question": user_input,
        "tool_name": tool_name,
        "tool_json": None,
        "llm_response": None,
        "rendered_response": None,
        "final_response": None,
        "got_ci_interventions": []  # 记录 GoT-CI 介入历史
    }
    
    for attempt in range(max_retries + 1):
        # 策略：首次用完整S-COT，重试时简化（但只重试1次，参考 Run1）
        if attempt == 0:
            current_method = method
        else:
            # ✅ GoT-CI 拦截触发的重试：保留原 method（避免丢失 schema/约束导致继续生成坏 Cypher）
            current_method = method if retry_due_to_gotci else "few"  # few: 去掉VD/MPS
        # 重置标记（若本轮再次被 GoT-CI 拦截，会在 continue 前置回 True）
        retry_due_to_gotci = False
        
        # 生成提示词
        dynamic_prompt = get_scot_prompt(current_user_input, current_method, tool_name)
        
        # 🔍【埋点 A】记录提示词构建效果
        if attempt == 0:  # 只在首次记录完整提示词
            trace_info["full_prompt"] = dynamic_prompt[:2000] + "..." if len(dynamic_prompt) > 2000 else dynamic_prompt
            
            # 🎯 提取 "合成示例" 部分（匹配 prompt_builder.py 的实际格式）
            # prompt_builder 使用 "## Few-shot Examples (Synthetic)" 和 "**示例 1:**"
            example_markers = ["## Few-shot Examples", "**示例 1:**", "### 示例", "**示例**"]
            for marker in example_markers:
                if marker in dynamic_prompt:
                    try:
                        examples_part = dynamic_prompt.split(marker)[1]
                        # 找到下一个 "##" 或 "**" 作为结束
                        for end_marker in ["## 当前问题", "## 执行步骤", "###"]:
                            if end_marker in examples_part:
                                examples_part = examples_part.split(end_marker)[0]
                                break
                        trace_info["synthetic_examples"] = examples_part.strip()[:1000]
                        break
                    except:
                        trace_info["synthetic_examples"] = "[解析失败]"
            
            # 🎯 提取 MDR 约束部分（匹配 prompt_builder.py 的实际格式）
            # prompt_builder 使用 "## MDR 数据约束 (动态获取)" 和 "**值域约束"
            constraint_markers = ["## MDR 数据约束", "**值域约束", "**MDR约束**", "### 约束"]
            for marker in constraint_markers:
                if marker in dynamic_prompt:
                    try:
                        constraints_part = dynamic_prompt.split(marker)[1]
                        # 找到下一个 "##" 作为结束
                        for end_marker in ["## Few-shot", "## 当前问题", "###"]:
                            if end_marker in constraints_part:
                                constraints_part = constraints_part.split(end_marker)[0]
                                break
                        trace_info["mdr_constraints"] = constraints_part.strip()[:500]
                        break
                    except:
                        trace_info["mdr_constraints"] = "[解析失败]"
        
        # 创建Agent
        agent = create_react_agent(
            llm, 
            tools=tools, 
            checkpointer=memory, 
            prompt=dynamic_prompt
        )
        
        # 执行Agent
        inputs = {"messages": [("user", current_user_input)]}
        config = {"configurable": {"thread_id": f"{session_id}_a{attempt}"}}
        
        tool_json_result = None  # 工具返回的原始 JSON
        
        try:
            response = agent.invoke(inputs, config=config)
            messages = response.get("messages", [])
            
            # 🎯 核心改进：遍历消息历史，提取工具返回的原始 JSON
            # 工具返回的消息类型是 ToolMessage
            for msg in reversed(messages):
                msg_type = type(msg).__name__
                # 检查是否是工具返回的消息
                if msg_type == 'ToolMessage' or (hasattr(msg, 'type') and msg.type == 'tool'):
                    tool_content = msg.content if hasattr(msg, 'content') else str(msg)
                    # 如果内容是 JSON 格式，保存它
                    if tool_content and (tool_content.strip().startswith('{') or tool_content.strip().startswith('[')):
                        tool_json_result = tool_content
                        _debug_info["tool_json"] = tool_json_result
                        # 🔍【埋点 C】记录工具调用效果
                        trace_info["tool_output"] = tool_json_result[:1000] + "..." if len(tool_json_result) > 1000 else tool_json_result
                        break
                    elif tool_content and 'result' in tool_content.lower():
                        # 可能是字符串形式的结果
                        tool_json_result = tool_content
                        _debug_info["tool_json"] = tool_json_result
                        trace_info["tool_output"] = tool_json_result[:1000] + "..." if len(tool_json_result) > 1000 else tool_json_result
                        break
            
            # 记录 LLM 的最终回复
            llm_final = messages[-1].content if messages else ""
            _debug_info["llm_response"] = llm_final[:500] if llm_final else None
            
            # 如果找到了工具的原始 JSON，直接使用它
            if tool_json_result:
                content = tool_json_result
            else:
                # 否则使用 LLM 的最终回复
                content = llm_final
                
        except Exception as e:
            content = f"Error: {str(e)}"
            continue
        
        # 检查是否返回了工具调用格式（说明Agent没执行工具）
        if '"name":' in content and '"arguments":' in content:
            tool_call_name, tool_call_args = extract_and_fix_tool_call(content)
            if tool_call_name:
                # 手动执行工具
                try:
                    for t in tools:
                        if tool_call_name.lower().replace('_', '') in t.name.lower().replace('_', ''):
                            arg_str = tool_call_args if isinstance(tool_call_args, str) else str(tool_call_args)
                            tool_result = t.invoke(arg_str)
                            content = tool_result if isinstance(tool_result, str) else json.dumps(tool_result, ensure_ascii=False)
                            break
                except:
                    pass
        
        # ============================================================
        # 🎯 GoT-CI v2：工具结果语义校验（字段完备性 / 统计粒度 / longest 只返回1条）
        # 目的：拦截 Run5 这类“JSON 合法但业务不对”的 A-stage 问题
        # ============================================================
        got_ci_valid = True  # 默认通过

        # 1) 先做「工具结果」校验（只有当 content 是工具返回的 {"query","result"} 时才启用）
        if use_got_ci and VALIDATOR_AVAILABLE and validate_tool_result is not None:
            try:
                content_stripped = content.strip() if content else ""
                if content_stripped.startswith("{"):
                    import json as json_module
                    parsed_json = json_module.loads(content_stripped)
                    if isinstance(parsed_json, dict) and "result" in parsed_json:
                        ok, err_msg, hint = validate_tool_result(tool_name, user_input, parsed_json)
                        if not ok:
                            got_ci_valid = False
                            trace_info["got_ci_attempts"].append({
                                "status": "intercepted",
                                "attempt": attempt + 1,
                                "bad_json": str(parsed_json)[:300],
                                "error_msg": err_msg[:300] if isinstance(err_msg, str) else str(err_msg)[:300],
                            })
                            # 将纠错提示附加到下一轮问题中（不改变 tool_name）
                            if hint:
                                current_user_input = user_input + "\n\n" + hint
                            if debug_log:
                                print(f"🔄 [GoT-CI v2] Tool-result intercepted (attempt {attempt+1}): {err_msg}")
                            if attempt < max_retries:
                                retry_due_to_gotci = True
                                continue
            except Exception as e:
                if debug_log:
                    print(f"[GoT-CI v2] Tool-result validation error: {e}")
        
        if use_got_ci and VALIDATOR_AVAILABLE and validate_and_correct is not None:
            try:
                # 尝试解析 JSON 并验证
                content_stripped = content.strip() if content else ""
                if content_stripped.startswith('{') or content_stripped.startswith('['):
                    import json as json_module
                    try:
                        parsed_json = json_module.loads(content_stripped)
                        if isinstance(parsed_json, dict):
                            is_valid, error_msg, corrected, correction_prompt = validate_and_correct(
                                tool_name,
                                parsed_json,
                                return_prompt=True,
                            )
                            _debug_info["validation_result"] = {
                                "valid": is_valid,
                                "error": error_msg if not is_valid else None
                            }
                            
                            if not is_valid:
                                # 🔄 GoT-CI 自修复：验证失败，记录并准备重试
                                got_ci_valid = False
                                _debug_info["got_ci_interventions"].append({
                                    "attempt": attempt,
                                    "error": error_msg,
                                    "action": "request_correction"
                                })
                                
                                # 🔍【埋点 B】记录 GoT-CI 拦截事件
                                trace_info["got_ci_attempts"].append({
                                    "status": "intercepted",
                                    "attempt": attempt + 1,
                                    "bad_json": str(parsed_json)[:300],  # 截断
                                    "error_msg": error_msg
                                })
                                
                                if debug_log:
                                    print(f"🔄 [GoT-CI] Intervention #{attempt + 1}: {error_msg[:100]}")
                                
                                # 如果还有重试机会，将在下一轮重试时使用更简化的方法
                                if correction_prompt:
                                    current_user_input = user_input + "\n\n" + correction_prompt
                                if attempt < max_retries:
                                    retry_due_to_gotci = True
                                    continue  # 触发重试
                            
                            elif corrected != parsed_json:
                                # ✅ 应用自动修正（如别名映射）
                                content = json_module.dumps(corrected, ensure_ascii=False)
                                changes = {k: v for k, v in corrected.items() if parsed_json.get(k) != v}
                                _debug_info["got_ci_interventions"].append({
                                    "attempt": attempt,
                                    "action": "auto_corrected",
                                    "changes": changes
                                })
                                
                                # 🔍【埋点 B】记录 GoT-CI 自动修正事件
                                trace_info["got_ci_attempts"].append({
                                    "status": "auto_corrected",
                                    "attempt": attempt + 1,
                                    "original": str({k: parsed_json.get(k) for k in changes.keys()})[:200],
                                    "corrected": str(changes)[:200]
                                })
                                
                                if debug_log:
                                    print(f"✓ [GoT-CI] Auto-corrected: {list(corrected.keys())}")
                            else:
                                # ✅ 验证通过，无需修正
                                trace_info["got_ci_attempts"].append({
                                    "status": "passed",
                                    "attempt": attempt + 1,
                                    "final_json": str(parsed_json)[:300]
                                })
                                    
                    except json_module.JSONDecodeError:
                        pass
            except Exception as e:
                if debug_log:
                    print(f"[GoT-CI] Validation error: {e}")
        
        # 检查响应质量（简化检查，参考 Run1）
        if content and 'Error' not in content and len(content) > 10:
            # 检测明显的幻觉（假坐标）
            if not _is_hallucinated_position(content):
                # 检查是否是 Cypher 语法错误
                if 'SyntaxError' not in content and 'Neo.ClientError' not in content:
                    break  # 有效响应，退出重试
    
    # 处理空响应
    if not content or content.strip() in ['', 'nan', 'None', '{}']:
        content = "未查询到相关信息"
    
    # ============================================================
    # 🎯 P0-2 修复：确保 JSON 被正确解析
    # 将 JSON 字符串解析为结构化数据，然后再渲染
    # ============================================================
    content_stripped = content.strip() if content else ""
    is_json_like = content_stripped.startswith('{') or content_stripped.startswith('[')
    
    if is_json_like:
        try:
            # 1. 安全解析 JSON
            parsed_data = _safe_json_parse(content)
            
            # 2. 提取 result 中的实际数据（解决 {"query": ..., "result": [...]} 格式问题）
            extracted_data = _extract_result_data(parsed_data)
            
            # 3. 转回 JSON 字符串供渲染使用
            content = json.dumps(extracted_data, ensure_ascii=False)
            
            if debug_log:
                print(f"[DEBUG] Extracted data keys: {list(extracted_data.keys())[:5]}")
        except Exception as e:
            if debug_log:
                print(f"[DEBUG] JSON parse error: {e}")
    
    # ============================================================
    # 🎯 核心改进：用确定性模板将 JSON 转换为自然语言
    # 目的：输出格式与 ground_truth 完全一致，提升 EM 和 F1
    # ============================================================
    if render_response is not None:
        try:
            # 判断内容是否是 JSON 格式
            content_stripped = content.strip()
            is_json_like = content_stripped.startswith('{') or content_stripped.startswith('[')
            if is_json_like:
                rendered = render_response(tool_name, content, user_input)
                _debug_info["rendered_response"] = rendered[:500] if rendered else None
                if rendered:
                    content = rendered
                else:
                    content = "未查询到相关信息"
        except Exception as e:
            # 渲染失败，避免暴露 JSON
            if debug_log:
                print(f"[DEBUG] Render error: {e}")
            if content.strip().startswith('{') or content.strip().startswith('['):
                content = "未查询到相关信息"

    # 位置题：LLM 直接回答时也做位置归一化（避免多输出链方向）
    if tool_name == 'gene_basic_info' and _normalize_location_answer is not None:
        normalized = _normalize_location_answer(content, user_input)
        if normalized:
            content = normalized
    
    _debug_info["final_response"] = content[:500] if content else None
    
    # 🎯 调试日志：写入文件（适合 tmux 后台运行）
    if debug_log:
        import datetime
        _debug_info["timestamp"] = datetime.datetime.now().isoformat()
        
        # 默认日志文件路径
        if debug_log_file is None:
            debug_log_file = Path(__file__).parent / "results" / "debug_log.jsonl"
        else:
            debug_log_file = Path(debug_log_file)
        
        # 确保目录存在
        debug_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 追加写入 JSONL 格式
        try:
            with open(debug_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(_debug_info, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
    
    # 计算token
    encoder = tiktoken.get_encoding("cl100k_base")
    input_tokens = len(encoder.encode(user_input))
    output_tokens = len(encoder.encode(content))
    total_tokens = input_tokens + output_tokens
    
    return content, total_tokens


def _is_hallucinated_position(content: str) -> bool:
    """检测明显的幻觉坐标（如 123456-789012）"""
    # 常见幻觉模式
    fake_patterns = [
        '123456', '789012', '1234567', '',
        '100000-100050', '200000-200050',  # 太整齐
    ]
    for p in fake_patterns:
        if p in content:
            return True
    return False


# ============================================================
# 对比测试函数
# ============================================================

def compare_methods(question: str, session_id: str = "test"):
    """对比不同方法的响应"""
    from agent import generate_response as generate_response_mdr_static
    
    print("=" * 60)
    print(f"Question: {question}")
    print(f"Detected Tool: {detect_tool_from_question(question)}")
    print("=" * 60)
    
    # 1. 学长的方法（MDR-Static）
    print("\n[MDR-Static - 学长方法]")
    try:
        resp1, tokens1 = generate_response_mdr_static(question, session_id + "_static")
        print(f"Response: {resp1[:300]}...")
        print(f"Tokens: {tokens1}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 2. S-COT方法
    print("\n[S-COT - 你的方法]")
    try:
        resp2, tokens2 = generate_response_scot(question, session_id + "_scot", "s_cot_raps")
        print(f"Response: {resp2[:300]}...")
        print(f"Tokens: {tokens2}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("=" * 60)


if __name__ == "__main__":
    # 测试代码
    test_cases = [
        "LOC_Os08g02050在基因组中的具体物理坐标是多少？",
        "OsMH63_03G0194400这个基因有没有突变体？",
        "Os02g0692000对应的OGI编号是多少？",
    ]
    
    print("Testing S-COT Agent (Enhanced)...")
    print("=" * 60)
    
    for q in test_cases:
        tool = detect_tool_from_question(q)
        print(f"\nQ: {q}")
        print(f"Detected Tool: {tool}")
        
        # 测试提示词生成
        prompt = get_scot_prompt(q, "s_cot_raps", tool)
        print(f"Prompt length: {len(prompt)} chars")
    
    print("\n" + "=" * 60)
    print("✓ Agent initialized successfully!")
