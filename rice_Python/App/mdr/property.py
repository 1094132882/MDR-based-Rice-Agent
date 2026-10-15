"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 1:56
"""


class Property:
    def __init__(self, graph, property_node):
        self.graph = graph
        self.property_node = property_node
        self.identifier = property_node["identifier"]
        self.name = property_node["name"]

    def get_node(self):
        return dict(self.property_node)

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name
