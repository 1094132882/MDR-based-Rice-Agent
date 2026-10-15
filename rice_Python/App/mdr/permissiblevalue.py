"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/28 1:33
"""


class PermissibleValue:
    def __init__(self, graph, permissible_value_node, value_meaning_identifier):
        self.graph = graph
        self.permissible_value_node = permissible_value_node
        self.value_meaning_identifier = value_meaning_identifier
        self.identifier = self.permissible_value_node["identifier"]

    def get_node(self):
        return dict(self.permissible_value_node)

    def get_identifier(self):
        return self.identifier

    def get_value_meaning_identifier(self):
        return self.value_meaning_identifier
