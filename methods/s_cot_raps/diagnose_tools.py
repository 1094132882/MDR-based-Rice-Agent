#!/usr/bin/env python3
"""诊断每个工具的失败原因"""
from pathlib import Path
import os
import sys
import json

# 设置环境变量
os.environ['NEO4J_URI'] = 'bolt://127.0.0.1:7689'
os.environ['NEO4J_USERNAME'] = 'neo4j'
os.environ['NEO4J_PASSWORD'] = ''
os.environ['OLLAMA_BASE_URL'] = 'http://127.0.0.1:11501'
os.environ['OLLAMA_MODEL'] = 'qwen3:14b'

# 设置路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'rice_Python'))

# 测试用例 - 每个失败类型各取一个
TEST_CASES = [
    # gene_locator - 测试失败的样本
    {
        "name": "gene_locator (失败样本)",
        "tool": "gene_locator",
        "question": "基因OsJ4155_10g0136300所在的染色体及其坐标范围是什么？",
        "expected": "Chr10:15602964-15605797"
    },
    
    # gene_basic_info - strand 查询
    {
        "name": "gene_basic_info (strand)",
        "tool": "gene_basic_info",
        "question": "Os02428G0380001552.01基因所在的DNA链是正链还是负链？",
        "expected": "正链"
    },
    
    # gene_mutant_info - reverse 查询 (type8)
    {
        "name": "gene_mutant_info (reverse)",
        "tool": "gene_mutant_info", 
        "question": "22NBT41突变体材料关联的基因名称是什么？",
        "expected": "8个基因"
    },
    
    # ogi_info - type20 基因数量
    {
        "name": "ogi_info (基因数量)",
        "tool": "ogi_info",
        "question": "OsLaMu_09g0015600所属的OGI分组有多少个成员基因？",
        "expected": "52个基因"
    },
    
    # structural_variation_link - TE 关联
    {
        "name": "structural_variation_link",
        "tool": "structural_variation_link",
        "question": "132424_NamRoo_INS0100250是否关联转座子？",
        "expected": "long_terminal_repeat"
    },
    
    # structural_variation_locator - 区域查询
    {
        "name": "structural_variation_locator",
        "tool": "structural_variation_locator",
        "question": "OsKeNa_01g0001150的基因组区域是否发现过结构变异？",
        "expected": "16个结构变异"
    },
]

def diagnose():
    print("=" * 70)
    print("工具诊断 - 找出每个工具失败的原因")
    print("=" * 70)
    
    # 导入工具
    from rice_Python.App.chat.tools.genelocatorquery import gene_locator_query
    from rice_Python.App.chat.tools.genebasicinfoquery import gene_basic_info_query
    from rice_Python.App.chat.tools.genemutantinfoquery import gene_mutant_info_query
    from rice_Python.App.chat.tools.ogiinfoquery import ogi_info_query
    from rice_Python.App.chat.tools.structuralvariationlinkquery import structural_variation_link_query
    from rice_Python.App.chat.tools.structuralvariationlocatorquery import structural_variation_locator_query
    
    tool_map = {
        "gene_locator": gene_locator_query,
        "gene_basic_info": gene_basic_info_query,
        "gene_mutant_info": gene_mutant_info_query,
        "ogi_info": ogi_info_query,
        "structural_variation_link": structural_variation_link_query,
        "structural_variation_locator": structural_variation_locator_query,
    }
    
    for case in TEST_CASES:
        print(f"\n{'='*70}")
        print(f"测试: {case['name']}")
        print(f"问题: {case['question'][:60]}...")
        print(f"期望: {case['expected']}")
        print("-" * 70)
        
        tool = tool_map.get(case['tool'])
        if not tool:
            print(f"❌ 工具 {case['tool']} 未找到")
            continue
        
        try:
            # 调用工具
            result = tool.invoke({"query": case['question']})
            
            print(f"返回类型: {type(result)}")
            
            if isinstance(result, dict):
                print(f"顶层 keys: {list(result.keys())}")
                
                if 'result' in result:
                    r = result['result']
                    if isinstance(r, list):
                        print(f"result 长度: {len(r)}")
                        if r:
                            print(f"result[0] keys: {list(r[0].keys()) if isinstance(r[0], dict) else 'N/A'}")
                            print(f"result[0] 内容: {json.dumps(r[0], ensure_ascii=False, indent=2)[:200]}")
                        else:
                            print("⚠️ result 为空列表!")
                    else:
                        print(f"result 内容: {r}")
                else:
                    print(f"完整返回: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}")
            else:
                print(f"返回内容: {str(result)[:300]}")
            
            # 判断成功/失败
            if isinstance(result, dict) and 'result' in result:
                if result['result'] and len(result['result']) > 0:
                    print("✅ 工具返回了数据")
                else:
                    print("❌ 工具返回空结果 - 可能是数据库没有数据或 Cypher 有问题")
            
        except Exception as e:
            print(f"❌ 调用失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    diagnose()

