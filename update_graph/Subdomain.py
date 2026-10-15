import os
from pathlib import Path
import pandas as pd
from neo4j import GraphDatabase

# --- 配置信息 ---
URI = os.environ["NEO4J_URI"]
USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
PASSWORD = os.environ["NEO4J_PASSWORD"]
# 确保路径指向新的 .xlsx 文件
EXCEL_PATH = str(Path(__file__).resolve().parents[1] / 'update_graph/Subdomain.xlsx')

def update_subdomains(tx, data_list):
    """
    匹配逻辑：
    1. MATCH 使用 Excel 的 ChineseName 匹配数据库现有的 name
    2. SET 使用 Excel 的 Name 更新数据库的 name
    3. SET 使用 Excel 的 Description 更新数据库的 description
    """
    query = """
    UNWIND $batch AS row
    MATCH (s:SubDomain)
    WHERE trim(s.name) = trim(toString(row.ChineseName))
    SET s.name = row.Name,
        s.description = row.Description,
        s.status = 'Registered'
    RETURN count(s) as updated_count
    """
    result = tx.run(query, batch=data_list)
    return result.single()["updated_count"]

def main():
    # 1. 读取 Excel 文件
    try:
        # 使用 pandas 直接读取 xlsx，不需要担心 utf-8 或 gbk 编码问题
        df = pd.read_excel(EXCEL_PATH)
        
        # 打印前几行确认读取正常
        print("Excel 文件读取成功！")
        print(f"识别到的列名: {df.columns.tolist()}")
        
        # 将数据转换为字典列表
        data_list = df[['ChineseName', 'Name', 'Description']].to_dict('records')
        print(f"共准备好 {len(data_list)} 条记录进行更新。")
        
    except Exception as e:
        print(f"读取 Excel 文件失败: {e}")
        print("请确保已安装 openpyxl: pip install openpyxl")
        return

    # 2. 连接 Neo4j 执行更新
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    try:
        with driver.session() as session:
            updated_count = session.execute_write(update_subdomains, data_list)
            print(f"--- 更新完成 ---")
            print(f"成功更新 SubDomain 节点数量: {updated_count}")
            
            if updated_count == 0:
                print("【注意】更新数量为 0，可能原因：")
                print("1. 数据库中 Subdomain 节点的 'name' 属性不是中文名。")
                print("2. Excel 中 'ChineseName' 列的值与数据库不匹配（请检查空格）。")
                
    except Exception as e:
        print(f"Neo4j 操作失败: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    main()