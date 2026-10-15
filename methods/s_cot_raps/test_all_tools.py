#!/usr/bin/env python3
"""测试所有9个工具的返回格式"""
import os
import sys
import json

# 从统一配置读取（必须在导入前）
try:
    from config import setup_env
    setup_env()
except ImportError:
    # 配置文件不存在时使用默认值
    os.environ.setdefault('OLLAMA_BASE_URL', 'http://127.0.0.1:11501')
    os.environ.setdefault('OLLAMA_MODEL', 'qwen3:32b')
    os.environ.setdefault('NEO4J_URI', 'bolt://127.0.0.1:7689')
    os.environ.setdefault('NEO4J_USER', 'neo4j')
    os.environ.setdefault('NEO4J_PASSWORD', '')

# 添加路径
rice_mdr1_path = os.path.expanduser("~/xrb/rice_mdr1")
rice_python_path = os.path.join(rice_mdr1_path, "rice_Python")
sys.path.insert(0, rice_mdr1_path)
sys.path.insert(0, rice_python_path)

# 每个工具一个测试问题
TOOL_TESTS = {
    "gene_locator": {
        "module": "rice_Python.App.chat.tools.genelocatorquery",
        "func": "gene_locator_query",
        "question": "LOC_Os08g02050在基因组中的具体物理坐标是多少？",
        "expected_fields": ["Chromosome", "Position"],
    },
    "gene_basic_info_strand": {
        "module": "rice_Python.App.chat.tools.genebasicinfoquery",
        "func": "gene_basic_info_query",
        "question": "Os02428G0380001552.01基因所在的DNA链是正链还是负链？",
        "expected_fields": ["Strand"],
    },
    "gene_basic_info_transcript": {
        "module": "rice_Python.App.chat.tools.genebasicinfoquery",
        "func": "gene_basic_info_query",
        "question": "OsN22_01G017170基因注释中记录的mRNA转录本有哪些？",
        "expected_fields": ["Transcripts"],
    },
    "gene_mutant_info": {
        "module": "rice_Python.App.chat.tools.genemutantinfoquery",
        "func": "gene_mutant_info_query",
        "question": "OsMH63_03G0194400这个基因有没有突变体？",
        "expected_fields": ["Mutants"],
    },
    "gene_mutant_info_reverse": {
        "module": "rice_Python.App.chat.tools.genemutantinfoquery",
        "func": "gene_mutant_info_query",
        "question": "22NBT41突变体材料关联的基因名称是什么？",
        "expected_fields": ["Gene", "Genes"],
    },
    "ogi_info": {
        "module": "rice_Python.App.chat.tools.ogiinfoquery",
        "func": "ogi_info_query",
        "question": "Os02g0692000对应的OGI编号是多少？",
        "expected_fields": ["OGI"],
    },
    "ogi_info_genes": {
        "module": "rice_Python.App.chat.tools.ogiinfoquery",
        "func": "ogi_info_query",
        "question": "OGI:08059490这个分类里有哪些水稻基因？",
        "expected_fields": ["Genes"],
    },
    "gene_function": {
        "module": "rice_Python.App.chat.tools.genefunctionquery",
        "func": "gene_function_query",
        "question": "请说明OsZH11G0820233100.01的生物学功能",
        "expected_fields": ["Function"],
    },
    "homologous_gene_and_expression": {
        "module": "rice_Python.App.chat.tools.homologousgeneandexpressionquery",
        "func": "homologous_gene_and_expression_query",
        "question": "比较OsLaMu_05g0004930在根和茎中的表达差异",
        "expected_fields": ["Expression"],
    },
    "adjacent_genes_region": {
        "module": "rice_Python.App.chat.tools.adjacentgenesquery",
        "func": "adjacent_genes_query",
        "question": "G46的染色体三号在500kb到550kb之间有哪些基因？",
        "expected_fields": ["genes", "Genes"],
    },
    "adjacent_genes_upstream": {
        "module": "rice_Python.App.chat.tools.adjacentgenesquery",
        "func": "adjacent_genes_query",
        "question": "OsLK638S_12g0006300上游15kb有哪些邻近基因？",
        "expected_fields": ["upstream", "Neighbors"],
    },
    "structural_variation_link": {
        "module": "rice_Python.App.chat.tools.structuralvariationlinkquery",
        "func": "structural_variation_link_query",
        "question": "OsKeNa_01g0001150的基因组区域是否发现过结构变异？",
        "expected_fields": ["SVs", "sv_list"],
    },
    "structural_variation_locator": {
        "module": "rice_Python.App.chat.tools.structuralvariationlocatorquery",
        "func": "structural_variation_locator_query",
        "question": "DG的一号染色体50kb至70kb区间内发现了哪些SV？",
        "expected_fields": ["SVs", "sv_list"],
    },
}

def test_tool(name, config):
    """测试单个工具"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    
    try:
        import importlib
        module = importlib.import_module(config["module"])
        func = getattr(module, config["func"])
        
        print(f"问题: {config['question'][:50]}...")
        
        # 调用工具
        result = func.invoke({"query": config["question"]})
        
        print(f"\n返回类型: {type(result)}")
        print(f"返回内容:")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        
        # 分析返回结构
        if isinstance(result, dict):
            print(f"\n顶层 keys: {list(result.keys())}")
            if 'result' in result:
                r = result['result']
                if isinstance(r, list) and len(r) > 0:
                    print(f"result[0] keys: {list(r[0].keys()) if isinstance(r[0], dict) else type(r[0])}")
                    print(f"result 长度: {len(r)}")
        
        return result
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", help="指定测试的工具名，不指定则测试所有")
    parser.add_argument("--list", action="store_true", help="列出所有工具")
    args = parser.parse_args()
    
    if args.list:
        print("可用工具:")
        for name in TOOL_TESTS:
            print(f"  - {name}")
        return
    
    results = {}
    
    if args.tool:
        if args.tool in TOOL_TESTS:
            results[args.tool] = test_tool(args.tool, TOOL_TESTS[args.tool])
        else:
            print(f"未知工具: {args.tool}")
            print(f"可用: {list(TOOL_TESTS.keys())}")
    else:
        for name, config in TOOL_TESTS.items():
            results[name] = test_tool(name, config)
    
    # 汇总
    print("\n" + "="*60)
    print("汇总")
    print("="*60)
    for name, result in results.items():
        if result is None:
            status = "❌ 失败"
        elif isinstance(result, dict) and 'result' in result:
            r = result['result']
            if isinstance(r, list) and len(r) > 0:
                status = f"✅ 成功 ({len(r)} 条结果)"
            elif r:
                status = "✅ 成功"
            else:
                status = "⚠️ 空结果"
        else:
            status = "⚠️ 格式异常"
        print(f"{name:40s}: {status}")

if __name__ == "__main__":
    main()

