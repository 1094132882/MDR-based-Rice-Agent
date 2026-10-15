import os
from pathlib import Path
import pandas as pd
from neo4j import GraphDatabase

# --- 配置信息 ---
URI = os.environ["NEO4J_URI"]
USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
PASSWORD = os.environ["NEO4J_PASSWORD"]
CSV_PATH = str(Path(__file__).resolve().parents[1] / 'update_graph/ObjectClass.csv')

def update_object_classes(tx, data_list):
    """
    更新说明：
    1. 将 n.Name 修改为 n.name (匹配数据库中的属性名)
    2. 将 row.Name 对应 CSV 中的列名 (保持大写)
    3. 使用 trim() 防止因 CSV 或数据库中多余的空格导致匹配失败
    """
    query = """
    UNWIND $batch AS row
    MATCH (n:对象类) 
    WHERE trim(n.name) = trim(toString(row.Name))
    SET n.describe = row.Description,
        n.status = 'Registered'
    RETURN count(n) as updated_count
    """
    result = tx.run(query, batch=data_list)
    return result.single()["updated_count"]

def main():
    # 1. 读取 CSV 文件
    try:
        df = pd.read_csv(CSV_PATH, encoding='gbk')
        # 将 DataFrame 转换为字典列表，方便传参
        data_list = df[['Name', 'Description']].to_dict('records')
    except Exception as e:
        print(f"读取 CSV 文件失败: {e}")
        return

    # 2. 连接 Neo4j 并执行更新
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    
    try:
        with driver.session() as session:
            updated_count = session.execute_write(update_object_classes, data_list)
            print(f"成功更新了 {updated_count} 个 '对象类' 节点。")
    except Exception as e:
        print(f"Neo4j 操作失败: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    main()