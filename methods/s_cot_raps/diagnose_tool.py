#!/usr/bin/env python3
import sys
import os

# 需要添加 rice_mdr1 目录（rice_Python的父目录）
project_root = os.path.expanduser("~/xrb/rice_mdr1")
rice_python_path = os.path.join(project_root, "rice_Python")

sys.path.insert(0, project_root)        # 添加 rice_mdr1
sys.path.insert(0, rice_python_path)    # 添加 rice_Python

print(f"项目根目录: {project_root}")
print(f"rice_Python路径: {rice_python_path}")

# 设置环境变量
os.environ['NEO4J_URI'] = 'bolt://127.0.0.1:7689'
os.environ['NEO4J_USERNAME'] = 'neo4j'
os.environ['NEO4J_PASSWORD'] = ''

print("=" * 60)
print("诊断工具函数连接问题")
print("=" * 60)

# 测试导入
print("\n[1/3] 导入工具模块...")
try:
    from rice_Python.App.chat.tools.genelocatorquery import gene_locator_query
    print("  ✓ 导入成功")
except Exception as e:
    print(f"  ✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试调用
print("\n[2/3] 调用工具函数...")
test_question = "LOC_Os08g02050在基因组中的具体物理坐标是多少？"
try:
    result = gene_locator_query(test_question)
    print(f"  ✓ 调用成功")
    print(f"  返回类型: {type(result)}")
    print(f"  返回内容:")
    import json
    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)
except Exception as e:
    print(f"  ✗ 调用失败: {e}")
    import traceback
    traceback.print_exc()

print("\n[3/3] 检查Flask服务...")
import requests
try:
    r = requests.get("http://localhost:11500/", timeout=2)
    print(f"  ✓ Flask响应状态: {r.status_code}")
except Exception as e:
    print(f"  ✗ Flask连接失败: {e}")

print("\n" + "=" * 60)
