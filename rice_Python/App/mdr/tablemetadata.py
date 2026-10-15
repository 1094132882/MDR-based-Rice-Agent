"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/25 14:56
"""

from rice_Python.App.mdr.tablemetadataelement import TableMetadataElement


class TableMetadata:
    def __init__(self, graph, table_metadata_node):
        self.graph = graph
        self.table_metadata_node = table_metadata_node
        self.table_metadata_elements = self.search_table_metadata_element()

    def search_table_metadata_element(self):
        cypher = """
        MATCH (n:`Table Metadata`) -[:contain]-> (m:`Table MetaData Element`) 
        WHERE n.identifier = $identifier 
        RETURN m 
        ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.table_metadata_node['identifier']).data()
        table_metadata_element_list = []
        for record in row_data:
            node = record['m']
            table_metadata_element_list.append(TableMetadataElement(self.graph, node))
        return table_metadata_element_list

    def get_identifier(self):
        return self.table_metadata_node['identifier']

    def get_sample(self):
        return self.table_metadata_node['sample']

    def get_node(self):
        table_metadata_node = dict(self.table_metadata_node)
        table_metadata_elements_node_list = [table_metadata_element.get_node()
                                             for table_metadata_element in self.table_metadata_elements]
        table_metadata_node['table_metadata_elements'] = table_metadata_elements_node_list
        return table_metadata_node

    def get_table_metadata_element(self):
        return self.table_metadata_elements
