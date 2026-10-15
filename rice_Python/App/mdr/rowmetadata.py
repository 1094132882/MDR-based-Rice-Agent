"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/26 1:44
"""
from rice_Python.App.mdr.columnmetadata import ColumnMetadata


class RowMetadata:
    def __init__(self, graph, row_metadata_node):
        self.graph = graph
        self.row_metadata_node = row_metadata_node
        self.column_metadata = self.search_column_metadata()

    def search_column_metadata(self):
        cypher = """
        MATCH (n:`Row Metadata`) -[:contain]-> (m:`Column Metadata`) 
        WHERE n.identifier = $identifier
        RETURN n,m ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.row_metadata_node['identifier']).data()
        column_metadata_list = []
        for row in row_data:
            column_metadata_list.append(ColumnMetadata(self.graph, row['m']))
        return column_metadata_list

    def get_identifier(self):
        return self.row_metadata_node['identifier']

    def get_name(self):
        return self.row_metadata_node['name']

    def get_segmentation(self):
        return self.row_metadata_node['segmentation']

    def get_column_metadata(self):
        return self.column_metadata

    def get_node(self):
        node = dict(self.row_metadata_node)
        node['column_metadata'] = [column_metadata.get_node() for column_metadata in self.column_metadata]
        return node
