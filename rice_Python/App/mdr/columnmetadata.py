"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/26 1:34
"""
from rice_Python.App.mdr.columnmetadataelement import ColumnMetadataElement


class ColumnMetadata:
    def __init__(self, graph, column_metadata_node):
        self.graph = graph
        self.column_metadata_node = column_metadata_node
        self.column_metadata_elements = self.search_column_metadata_element()
        self.data_element_identifier = self.search_data_element_identifier()

    def search_column_metadata_element(self):
        cypher = """
        MATCH (n:`Column Metadata`) -[:contain]-> (m:`Column Metadata Element`) 
        WHERE n.identifier = $identifier
        RETURN m ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.column_metadata_node['identifier']).data()
        column_metadata_elements = []
        for row in row_data:
            column_metadata_elements.append(ColumnMetadataElement(self.graph, row['m']))
        return column_metadata_elements

    def search_data_element_identifier(self):
        cypher = """
        MATCH (n:`Column Metadata`) -[:`data element`]-> (m:`数据元`) 
        WHERE n.identifier = $identifier 
        RETURN m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.get_identifier()).data()
        if len(row_data) > 0:
            return row_data[0]['m.identifier']
        else:
            return None

    def get_identifier(self):
        return self.column_metadata_node['identifier']

    def get_name(self):
        return self.column_metadata_node['name']

    def get_sample(self):
        if len(self.column_metadata_elements) > 0:
            return self.column_metadata_node['sample']
        else:
            return None

    def get_column_metadata_elements(self):
        return self.column_metadata_elements

    def get_node(self):
        node = dict(self.column_metadata_node)
        node['column_metadata_elements'] = [cm_element.get_node() for cm_element in self.column_metadata_elements]
        node['data_element_identifier'] = self.data_element_identifier
        return node
