"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 2:03
"""

from rice_Python.App.mdr.valuemeaning import ValueMeaning


class ConceptualDomain:
    def __init__(self, graph, conceptual_domain_node):
        self.graph = graph
        self.conceptual_domain_node = conceptual_domain_node
        self.identifier = conceptual_domain_node["identifier"]
        self.value_meaning_list = self.search_value_meaning()
        self.name = self.conceptual_domain_node["name"]

    def search_value_meaning(self):
        cypher = """
        MATCH (n:`概念域`) -[:`值含义`]-> (v:`值含义`) 
        WHERE n.identifier = $identifier 
        return v 
        ORDER BY v.identifier
        """
        try:
            raw_data = self.graph.run(cypher, identifier=self.identifier).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")

        value_meanings = []
        for record in raw_data:
            value_meanings.append(ValueMeaning(self.graph, record["v"]))
        return value_meanings

    def get_identifier(self):
        return self.identifier

    def get_node(self):
        conceptual_domain_node = dict(self.conceptual_domain_node)
        value_meanings = [v.get_node() for v in self.value_meaning_list]
        conceptual_domain_node["value_meanings"] = value_meanings
        return conceptual_domain_node

    def get_name(self):
        return self.name

    def get_value_meaning_by_identifier(self, identifier):
        for value_meaning in self.value_meaning_list:
            if value_meaning.get_identifier() == identifier:
                return value_meaning.get_node()
        return None
