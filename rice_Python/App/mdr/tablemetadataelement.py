"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/25 14:52
"""


class TableMetadataElement:
    def __init__(self, graph, table_metadata_element_node):
        self.graph = graph
        self.table_metadata_element_node = table_metadata_element_node
        self.data_element_identifier = self.search_data_element_identifier()

    def search_data_element_identifier(self):
        cypher = """
        MATCH (n:`Table MetaData Element`) -[:`data element`]-> (m:`数据元`) 
        WHERE n.identifier = $identifier 
        RETURN m.identifier
        """
        result = self.graph.run(cypher, identifier=self.get_identifier()).data()
        if result:
            return result[0]['m.identifier']
        else:
            return None

    def get_node(self):
        table_metadata_element_node = dict(self.table_metadata_element_node)
        table_metadata_element_node['data_element_identifier'] = self.data_element_identifier
        return table_metadata_element_node

    def get_identifier(self):
        return self.table_metadata_element_node.get('identifier')

    def get_name(self):
        return self.table_metadata_element_node.get('name')

    def get_sample(self):
        return self.table_metadata_element_node.get('sample')
