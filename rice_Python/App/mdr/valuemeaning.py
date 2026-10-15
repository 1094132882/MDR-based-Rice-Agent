"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/28 0:45
"""


class ValueMeaning:
    def __init__(self, graph, value_meaning_node):
        self.graph = graph
        self.value_meaning_node = value_meaning_node
        self.identifier = self.value_meaning_node['identifier']

    def get_node(self):
        return dict(self.value_meaning_node)

    def get_identifier(self):
        return self.identifier
