"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 9:53
"""


class DataElementConcept:
    def __init__(self, graph, data_element_concept_node, object_class_identifier,
                 object_class_name, property_identifier, property_name,
                 conceptual_domain_identifier, conceptual_domain_name):
        self.graph = graph
        self.identifier = data_element_concept_node.get("identifier")
        self.name = data_element_concept_node.get("name")
        self.data_element_concept_node = data_element_concept_node
        self.object_class_identifier = object_class_identifier
        self.object_class_name = object_class_name
        self.property_identifier = property_identifier
        self.property_name = property_name
        self.conceptual_domain_identifier = conceptual_domain_identifier
        self.conceptual_domain_name = conceptual_domain_name

    def get_node(self):
        data_element_concept_node = dict(self.data_element_concept_node)
        data_element_concept_node["object_class"] = {
            "identifier": self.object_class_identifier,
            "name": self.object_class_name,
        }
        data_element_concept_node["property"] = {
            "identifier": self.property_identifier,
            "name": self.property_name,
        }
        data_element_concept_node["conceptual_domain"] ={
            "identifier": self.conceptual_domain_identifier,
            "name": self.conceptual_domain_name,
        }
        return data_element_concept_node

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name

    def get_object_class_identifier(self):
        return self.object_class_identifier

    def get_object_class_name(self):
        return self.object_class_name

    def get_property_identifier(self):
        return self.property_identifier

    def get_property_name(self):
        return self.property_name

    def get_conceptual_domain_identifier(self):
        return self.conceptual_domain_identifier

    def get_conceptual_domain_name(self):
        return self.conceptual_domain_name
