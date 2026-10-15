"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/28 0:19
"""

from rice_Python.App.mdr.objectclass import ObjectClass
from rice_Python.App.mdr.property import Property
from rice_Python.App.mdr.conceptualdomain import ConceptualDomain
from rice_Python.App.mdr.dataelementconcept import DataElementConcept
from rice_Python.App.mdr.valuedomain import ValueDomain
from rice_Python.App.mdr.dataelement import DataElement


class MDRService:
    def __init__(self, graph):
        self.graph = graph
        self.object_class_list = self.init_object_class()
        self.property_list = self.init_property()
        self.conceptual_domain_list = self.init_conceptual_domain()
        self.data_element_concept_list = self.init_data_element_concept()
        self.value_domain_list = self.init_value_domain()
        self.data_element_list = self.init_data_element()

    def init_object_class(self):
        cypher = "MATCH (n:对象类) RETURN n ORDER BY n.identifier"

        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        object_class_list = []
        for data in raw_data:
            object_class_list.append(ObjectClass(self.graph, data['n']))

        return object_class_list

    def init_property(self):
        cypher = "MATCH (n:属性) RETURN n ORDER BY n.identifier"
        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        property_list = []
        for data in raw_data:
            property_list.append(Property(self.graph, data['n']))

        return property_list

    def init_conceptual_domain(self):
        cypher = "MATCH (n:概念域) RETURN n ORDER BY n.identifier"
        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        conceptual_domain_list = []
        for data in raw_data:
            conceptual_domain_list.append(ConceptualDomain(self.graph, data['n']))

        return conceptual_domain_list

    def init_data_element_concept(self):
        cypher = """
        MATCH (n:`数据元概念`) -[:`对象类`]-> (o:`对象类`) 
        MATCH(n) -[:`属性`]-> (p:`属性`) 
        MATCH(n) -[:`概念域`]-> (c:`概念域`)
        RETURN n,o,p,c
        ORDER BY n.identifier
        """
        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        data_element_concept_list = []
        for data in raw_data:
            data_element_concept_list.append(DataElementConcept(self.graph, data['n'],
                                                                data['o']['identifier'], data['o']['name'],
                                                                data['p']['identifier'], data['p']['name'],
                                                                data['c']['identifier'], data['c']['name']))
        return data_element_concept_list

    def init_value_domain(self):
        cypher = """
        MATCH (n:`值域`) -[:`概念域`]-> (c:`概念域`) 
        RETURN n,c 
        ORDER BY n.identifier
        """
        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        value_domain_list = []
        for data in raw_data:
            value_domain_list.append(ValueDomain(self.graph, data['n'], data['c']['identifier'], data['c']['name']))
        return value_domain_list

    def init_data_element(self):
        cypher = """
                MATCH (n:`数据元`) -[:`值域`]-> (v:`值域`) 
                MATCH (n) -[:`数据元概念`]-> (d:`数据元概念`) 
                return n,v,d 
                ORDER BY n.identifier
                """
        try:
            raw_data = self.graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")
        data_element_list = []
        for data in raw_data:
            data_element_list.append(DataElement(self.graph, data['n'], data['d']['identifier'], data['d']['name'],
                                                 data['v']['identifier'], data['v']['name']))
        return data_element_list

    def get_object_class_list(self):
        result = []
        for object_class in self.object_class_list:
            result.append(object_class.get_node())
        return result

    def get_object_class_by_identifier(self, identifier):
        for object_class in self.object_class_list:
            if object_class.get_identifier() == identifier:
                return object_class.get_node()
        return None

    def get_property_list(self):
        result = []
        for property in self.property_list:
            result.append(property.get_node())
        return result

    def get_property_by_identifier(self, identifier):
        for property in self.property_list:
            if property.get_identifier() == identifier:
                return property.get_node()
        return None

    def get_conceptual_domain_list(self):
        result = []
        for conceptual_domain in self.conceptual_domain_list:
            result.append(conceptual_domain.get_node())
        return result

    def get_conceptual_domain_by_identifier(self, identifier):
        for conceptual_domain in self.conceptual_domain_list:
            if conceptual_domain.get_identifier() == identifier:
                return conceptual_domain.get_node()
        return None

    def get_conceptual_domain_object_by_identifier(self, identifier):
        for conceptual_domain in self.conceptual_domain_list:
            if conceptual_domain.get_identifier() == identifier:
                return conceptual_domain
        return None

    def get_data_element_concept_list(self):
        result = []
        for data_element_concept in self.data_element_concept_list:
            result.append(data_element_concept.get_node())
        return result

    def get_data_element_concept_by_identifier(self, identifier):
        for data_element_concept in self.data_element_concept_list:
            if data_element_concept.get_identifier() == identifier:
                return data_element_concept.get_node()
        return None

    def get_value_domain_list(self):
        result = []
        for value_domain in self.value_domain_list:
            result.append(self.get_value_domain_by_identifier(value_domain.get_identifier()))
        return result

    def get_value_domain_by_identifier(self, identifier):
        for value_domain in self.value_domain_list:
            if value_domain.get_identifier() == identifier:
                value_domain_node = value_domain.get_node()
                permissible_values_list = value_domain.get_permissible_values_list()
                if len(permissible_values_list) == 0:
                    value_domain_node["permissible_values"] = []
                    return value_domain_node
                else:
                    permissible_values = []
                    conceptual_domain_identifier = value_domain.get_conceptual_domain_identifier()
                    conceptual_domain_node = self.get_conceptual_domain_object_by_identifier(
                        conceptual_domain_identifier)
                    for permissible_value in permissible_values_list:
                        value_meaning_identifier = permissible_value.get_value_meaning_identifier()
                        value_meaning_node = conceptual_domain_node.get_value_meaning_by_identifier(
                            value_meaning_identifier)
                        permissible_value_node = permissible_value.get_node()
                        permissible_value_node["value_meanings"] = value_meaning_node
                        permissible_values.append(permissible_value_node)
                    value_domain_node["permissible_values"] = permissible_values
                    return value_domain_node
        return None

    def get_data_element_list(self):
        result = []
        for data_element in self.data_element_list:
            result.append(data_element.get_node())
        return result

    def get_data_element_by_identifier(self, identifier):
        for data_element in self.data_element_list:
            if data_element.get_identifier() == identifier:
                return data_element.get_node()
        return None