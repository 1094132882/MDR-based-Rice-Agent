#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接修复工具文件的 CYPHER_GENERATION_TEMPLATE
不需要诊断，直接根据观察到的错误修复
"""
import os
from pathlib import Path

# 工具文件路径
TOOLS_DIR = Path(str(Path(__file__).resolve().parents[2] / 'rice_Python/App/chat/tools'))

# 修复 genebasicinfoquery.py
print("=" * 80)
print("修复 genebasicinfoquery.py")
print("=" * 80)

gene_basic_info_file = TOOLS_DIR / "genebasicinfoquery.py"
content = gene_basic_info_file.read_text(encoding='utf-8')

# 在 Fine Tuning 部分添加严格约束
new_fine_tuning = """Fine Tuning:
- 当查询染色体时，需将数字编号转换为Chr01格式（例如查询6号染色体应写为："MATCH (c:Chromosome {{name: 'Chr06'}})"）
- 当问题涉及基因节点时，必须返回该基因的URL（示例："MATCH (g:Gene {{name: 'Os02428G0202950600.01'}}) RETURN g.URL"）
- 基因的位置信息包括染色体号、起始位点和终止位点，当查询位置相关问题时，无论是查询其中一个还是全部，都需要将这三个信息都返回。
  例如：当用户询问基因的起始位点和终止位点时，应该将染色体号、起始位点和终止位点都返回。

⚠️ 严格约束（违反将导致查询失败）:
1. Gene 节点没有 strand 属性！❌ 禁止使用 g.strand
2. 不存在 :position 关系！❌ 只能使用 :start_pos 和 :end_pos
3. 要判断链性，需比较 start_pos 和 end_pos 的大小（start < end 为正链，start > end 为负链）
4. 必须严格按照下面的示例格式编写查询

✅ 可用的关系:
- (Gene)-[:chromosome_no]->(Chromosome)
- (Gene)-[:start_pos]->(Position)
- (Gene)-[:end_pos]->(Position)
- (Gene)-[:has_mRNA]->(mRNA)
- (Gene)-[:has_protein]->(Protein)
- (Gene)-[:has_DNA]->(DNA)
- (Gene)-[:has_CDS]->(CDS)"""

# 替换 Fine Tuning 部分
if "Fine Tuning:" in content:
    parts = content.split("Fine Tuning:")
    before = parts[0]
    after_parts = parts[1].split("\n\nCypher示例:")
    after = "\n\nCypher示例:" + after_parts[1] if len(after_parts) > 1 else ""
    
    new_content = before + new_fine_tuning + after
    
    # 添加链性查询示例
    if "Cypher示例:" in new_content:
        cypher_examples_addition = """

2. 查询基因的链性（通过位置判断）
```
match (g:Gene) -[:chromosome_no]-> (c:Chromosome) 
match (g) -[:start_pos]-> (sp:Position)
match (g) -[:end_pos]-> (ep:Position)
where g.name = 'OsYX1G0926018000.01' 
return g.URL as gene_url, c.name as chromosome,
  CASE 
    WHEN toInteger(sp.name) < toInteger(ep.name) THEN '正链' 
    ELSE '负链' 
  END AS strand
```
"""
        # 在第一个示例后插入
        new_content = new_content.replace(
            "```\n\nSchema:",
            "```" + cypher_examples_addition + "\nSchema:"
        )
    
    # 备份原文件
    backup_file = TOOLS_DIR / "genebasicinfoquery.py.backup"
    if not backup_file.exists():
        backup_file.write_text(content, encoding='utf-8')
        print(f"✓ 已备份到: {backup_file}")
    
    # 写入修复后的内容
    gene_basic_info_file.write_text(new_content, encoding='utf-8')
    print(f"✓ 已修复: {gene_basic_info_file}")
else:
    print("⚠ 未找到 Fine Tuning 部分，请手动修改")

print()
print("=" * 80)
print("修复完成！")
print("=" * 80)
print()
print("重新测试:")
print("python methods/s_cot_raps/run.py \\")
print("  --engine py \\")
print("  --method ground_truth \\")
print("  --input methods/s_cot_raps/dataset.csv \\")
print("  --out methods/s_cot_raps/runs/ground_truth_fixed.jsonl \\")
print("  --max 10")

