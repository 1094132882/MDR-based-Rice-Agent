import os
from pathlib import Path
import pandas as pd
from neo4j import GraphDatabase

# --- 配置信息 ---
URI = os.environ["NEO4J_URI"]
USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
PASSWORD = os.environ["NEO4J_PASSWORD"]
# 确保路径指向你的 DataElementConcept.xlsx 文件
EXCEL_PATH = str(Path(__file__).resolve().parents[1] / 'update_graph/DataSet.xlsx')

def update_properties(tx, data_list):
    """
    匹配逻辑：
    1. MATCH 使用 Excel 的 Name 列匹配数据库中 :属性 节点的 name 属性
    2. SET 更新 describe 属性为 Excel 的 Description 内容
    3. SET 更新 status 属性为 'Registered'
    """
    query = """
    UNWIND $batch AS row
    MATCH (p:DataSet)
    WHERE trim(p.identifier) = trim(toString(row.Name))
    SET p.description = row.Description
    RETURN count(p) as updated_count
    """
    result = tx.run(query, batch=data_list)
    return result.single()["updated_count"]

def main():
    # 1. 读取 Excel 文件
    try:
        df = pd.read_excel(EXCEL_PATH)
        
        print("Excel 文件读取成功！")
        print(f"识别到的列名: {df.columns.tolist()}")
        
        # 将数据转换为字典列表
        data_list = df[['Name', 'Description']].to_dict('records')
        print(f"共准备好 {len(data_list)} 条记录进行更新。")
        
    except Exception as e:
        print(f"读取 Excel 文件失败: {e}")
        return

    # 2. 连接 Neo4j 执行更新
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    try:
        with driver.session() as session:
            updated_count = session.execute_write(update_properties, data_list)
            print(f"--- 更新完成 ---")
            print(f"成功更新“属性”节点数量: {updated_count}")
            
            if updated_count == 0:
                print("【警告】更新数量为 0。请检查数据库中的标签名是否为 ':属性'，以及 name 是否匹配。")
                
    except Exception as e:
        print(f"Neo4j 操作失败: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    main()