"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 10:34
"""

from rice_Python.App.mdr.permissiblevalue import PermissibleValue


class ValueDomain:
    def __init__(self, graph, value_domain_node, conceptual_domain_identifier, conceptual_domain_name):
        self.graph = graph
        self.value_domain_node = value_domain_node
        self.conceptual_domain_identifier = conceptual_domain_identifier
        self.conceptual_domain_name = conceptual_domain_name
        self.identifier = value_domain_node.get("identifier")
        self.name = value_domain_node.get("name")
        self.permissible_values_list = self.search_permissible_value()

    def search_permissible_value(self):
        cypher = """
        MATCH (n:`值域`) -[:`组`]-> (:`值域组`)-[:`可允许值`]-> (p:`可允许值`) -[:`值含义`]-> (v:`值含义`) 
        WHERE n.identifier = $identifier  
        RETURN p,v 
        ORDER BY p.identifier
        """
        try:
            raw_data = self.graph.run(cypher, identifier=self.identifier).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")

        permissible_values = []
        for record in raw_data:
            permissible_values.append(PermissibleValue(self.graph, record["p"], record["v"]["identifier"]))
        return permissible_values

    def get_node(self):
        value_domain_node = dict(self.value_domain_node)
        # value_domain_node["permissible_values"] = [pv.get_node() for pv in self.permissible_values_list]
        value_domain_node["conceptual_domain"] = {
            "identifier": self.conceptual_domain_identifier,
            "name": self.conceptual_domain_name
        }
        return value_domain_node

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name

    def get_conceptual_domain_identifier(self):
        return self.conceptual_domain_identifier

    def get_permissible_values_list(self):
        return self.permissible_values_list

