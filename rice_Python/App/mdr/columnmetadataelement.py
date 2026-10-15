"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/26 1:30
"""


class ColumnMetadataElement:
    def __init__(self, graph, column_metadata_element_node):
        self.graph = graph
        self.column_metadata_element_node = column_metadata_element_node
        self.data_element_identifier = self.search_data_element_identifier()

    def get_identifier(self):
        return self.column_metadata_element_node.get("identifier")

    def get_name(self):
        return self.column_metadata_element_node.get("name")

    def get_sample(self):
        return self.column_metadata_element_node.get("sample")

    def search_data_element_identifier(self):
        cypher = """
        MATCH (n:`Column Metadata Element`) -[:`data element`]-> (m:`数据元`) 
        WHERE n.identifier = $identifier 
        RETURN m.identifier
        """
        result = self.graph.run(cypher, identifier=self.get_identifier()).data()
        if result:
            return result[0]["m.identifier"]
        else:
            return None

    def get_node(self):
        column_metadata_element_node = dict(self.column_metadata_element_node)
        column_metadata_element_node["data_element_identifier"] = self.data_element_identifier
        return column_metadata_element_node
