"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/25 14:48
"""
from rice_Python.App.mdr.tablemetadata import TableMetadata
from rice_Python.App.mdr.columnmetadata import ColumnMetadata
from rice_Python.App.mdr.rowmetadata import RowMetadata


class Dataset:
    def __init__(self, graph, dataset_node):
        self.graph = graph
        self.dataset_node = dataset_node
        self.table_metadata = self.search_table_metadata()
        self.column_metadata = self.search_column_metadata()
        self.row_metadata = self.search_row_metadata()
        if len(self.row_metadata) == 0:
            self.is_column_first = True
        else:
            self.is_column_first = False
        self.total_tables = self.search_tables_counts()

    def search_table_metadata(self):
        cypher = """
        MATCH (n:DataSet) -[:contain]-> (m:`Table Metadata`) 
        WHERE n.identifier = $identifier 
        RETURN m 
        """
        row_data = self.graph.run(cypher, identifier=self.dataset_node['identifier']).data()
        if len(row_data) == 0:
            return None
        else:
            return TableMetadata(self.graph, row_data[0]['m'])

    def search_column_metadata(self):
        cypher = """
        MATCH (n:DataSet) -[:contain]-> (m:`Column Metadata`) 
        WHERE n.identifier = $identifier
        RETURN m ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.dataset_node['identifier'])
        column_metadata_list = []
        for row in row_data:
            column_metadata_list.append(ColumnMetadata(self.graph, row['m']))
        return column_metadata_list

    def search_row_metadata(self):
        cypher = """
        MATCH (n:DataSet) -[:contain]-> (m:`Row Metadata`) 
        WHERE n.identifier = $identifier
        RETURN m ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.dataset_node['identifier'])
        row_metadata_list = []
        for row in row_data:
            row_metadata_list.append(RowMetadata(self.graph, row['m']))
        return row_metadata_list

    def search_tables_counts(self):
        count_query = """
                    MATCH (d:DataSet)-[:contain]->(t:Table)
                    WHERE d.identifier = $identifier
                    RETURN count(t) AS total_tables
                    """
        total_tables = self.graph.run(count_query, identifier=self.get_identifier()).data()[0]['total_tables']
        return total_tables

    def get_identifier(self):
        return self.dataset_node['identifier']

    def get_name(self):
        return self.dataset_node['name']

    def get_description(self):
        return self.dataset_node['description']

    def get_table_metadata(self):
        return self.table_metadata

    def get_node(self):
        dataset_node = dict(self.dataset_node)
        if self.table_metadata is not None:
            dataset_node['table_metadata'] = self.table_metadata.get_node()
        else:
            dataset_node['table_metadata'] = None
        dataset_node["total_tables"] = self.total_tables
        if self.is_column_first:
            dataset_node['column_metadata'] = [column.get_node() for column in self.column_metadata]
        else:
            dataset_node['row_metadata'] = [row.get_node() for row in self.row_metadata]
        dataset_node["is_column_first"] = self.is_column_first
        dataset_node["tables"] = self.get_tables(1)
        return dataset_node

    def get_tables(self, page):
        per_page = 10
        skip = (page - 1) * per_page
        cypher = """
        MATCH (d:DataSet)-[:contain]->(t:Table)-[:sample]->(s:`Sample Data`)
        WHERE d.identifier = $identifier
        WITH t, s
        ORDER BY t.identifier, s.id
        RETURN t AS table, collect(s) AS sample_data
        ORDER BY t.identifier
        SKIP $skip
        LIMIT $per_page
        """

        result = self.graph.run(cypher, identifier=self.get_identifier(), skip=skip, per_page=per_page).data()

        # count_query = """
        #     MATCH (d:DataSet)-[:contain]->(t:Table)
        #     WHERE d.identifier = $identifier
        #     RETURN count(t) AS total_tables
        #     """
        # total_tables = self.graph.run(count_query).data()[0]['total_tables']
        total_tables = self.total_tables
        total_pages = (total_tables + per_page - 1) // per_page  # 计算总页数

        tables = []
        for record in result:
            table_data = dict(record['table'])
            sample_data = [dict(sample) for sample in record['sample_data']]
            tables.append({
                'table': table_data,
                'sample_data': sample_data
            })

        return {
            'data': tables,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_tables': total_tables,
                'total_pages': total_pages
            }
        }
