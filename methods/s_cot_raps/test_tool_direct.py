#!/usr/bin/env python3
"""直接测试工具调用，看看返回什么"""
import os
import sys

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

def test_mutant():
    """测试 gene_mutant_info 工具"""
    print("\n" + "="*60)
    print("测试 gene_mutant_info")
    print("="*60)
    
    from rice_Python.App.chat.tools.genemutantinfoquery import gene_mutant_info_query
    
    question = "OsMH63_03G0194400这个基因有没有突变体？"
    print(f"问题: {question}")
    
    try:
        result = gene_mutant_info_query.invoke({"query": question})
        print(f"\n返回类型: {type(result)}")
        print(f"返回内容: {result}")
    except Exception as e:
        print(f"错误: {e}")

def test_ogi():
    """测试 ogi_info 工具"""
    print("\n" + "="*60)
    print("测试 ogi_info")
    print("="*60)
    
    from rice_Python.App.chat.tools.ogiinfoquery import ogi_info_query
    
    question = "OsARC_01g0045410属于哪个OGI分组？"
    print(f"问题: {question}")
    
    try:
        result = ogi_info_query.invoke({"query": question})
        print(f"\n返回类型: {type(result)}")
        print(f"返回内容: {result}")
    except Exception as e:
        print(f"错误: {e}")

def test_basic_info():
    """测试 gene_basic_info 工具 - strand"""
    print("\n" + "="*60)
    print("测试 gene_basic_info (strand)")
    print("="*60)
    
    from rice_Python.App.chat.tools.genebasicinfoquery import gene_basic_info_query
    
    question = "Os02428G0380001552.01基因所在的DNA链是正链还是负链？"
    print(f"问题: {question}")
    
    try:
        result = gene_basic_info_query.invoke({"query": question})
        print(f"\n返回类型: {type(result)}")
        print(f"返回内容: {result}")
    except Exception as e:
        print(f"错误: {e}")

def test_locator():
    """测试 gene_locator 工具 - 这个之前成功过"""
    print("\n" + "="*60)
    print("测试 gene_locator")
    print("="*60)
    
    from rice_Python.App.chat.tools.genelocatorquery import gene_locator_query
    
    question = "LOC_Os03g01220在哪条染色体的什么位置？"
    print(f"问题: {question}")
    
    try:
        result = gene_locator_query.invoke({"query": question})
        print(f"\n返回类型: {type(result)}")
        print(f"返回内容: {result}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", choices=["mutant", "ogi", "basic", "locator", "all"], default="all")
    args = parser.parse_args()
    
    if args.tool == "mutant" or args.tool == "all":
        test_mutant()
    if args.tool == "ogi" or args.tool == "all":
        test_ogi()
    if args.tool == "basic" or args.tool == "all":
        test_basic_info()
    if args.tool == "locator" or args.tool == "all":
        test_locator()

