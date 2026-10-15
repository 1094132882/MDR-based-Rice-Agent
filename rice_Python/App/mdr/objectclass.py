"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 0:30
"""


class ObjectClass:
    def __init__(self, graph, object_class_node):
        self.graph = graph
        self.object_class_node = object_class_node
        self.identifier = object_class_node["identifier"]
        self.name = object_class_node["name"]

    def get_node(self):
        return dict(self.object_class_node)

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name
