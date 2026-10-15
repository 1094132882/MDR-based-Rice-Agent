"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 12:59
"""


class DataElement:
    def __init__(self, graph, data_element_node, data_element_concept_identifier, data_element_concept_name,
                 value_domain_identifier, value_domain_name):
        self.graph = graph
        self.data_element_node = data_element_node
        self.identifier = self.data_element_node["identifier"]
        self.name = self.data_element_node["name"]
        self.data_element_concept_identifier = data_element_concept_identifier
        self.data_element_concept_name = data_element_concept_name
        self.value_domain_identifier = value_domain_identifier
        self.value_domain_name = value_domain_name

    def get_node(self):
        data_element_node = dict(self.data_element_node)
        data_element_node["data_element_concept"] = {
            "identifier": self.data_element_concept_identifier,
            "name": self.data_element_concept_name
        }
        data_element_node["value_domain"] = {
            "identifier": self.value_domain_identifier,
            "name": self.value_domain_name
        }
        return data_element_node

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name

    def get_data_element_concept_identifier(self):
        return self.data_element_concept_identifier

    def get_data_element_concept_name(self):
        return self.data_element_concept_name

    def get_value_domain_identifier(self):
        return self.value_domain_identifier

    def get_value_domain_name(self):
        return self.value_domain_name

    @staticmethod
    def get_data_element_list(graph):
        cypher = """
        MATCH (n:`数据元`) -[:`值域`]-> (v:`值域`) 
        MATCH (n) -[:`数据元概念`]-> (d:`数据元概念`) 
        return n,v,d 
        ORDER BY n.identifier
        """
        try:
            raw_data = graph.run(cypher).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")

        if not raw_data:
            return {}

        result = []
        for record in raw_data:
            data_element_concept = {
                "identifier": record["d"]["identifier"],
                "name": record["d"]["name"]
            }

            value_domain = {
                "identifier": record["v"]["identifier"],
                "name": record["v"]["name"]
            }

            data_element = dict(record["n"])
            data_element["data_element_concept"] = data_element_concept
            data_element["value_domain"] = value_domain

            result.append(data_element)

        return result

    @classmethod
    def get_data_element_by_identifier(cls, graph, identifier):
        cypher = """
        MATCH (n:`数据元`) -[:`值域`]-> (v:`值域`) 
        MATCH (n) -[:`数据元概念`]-> (d:`数据元概念`) 
        WHERE n.identifier = $identifier
        return n,v,d 
        """
        try:
            raw_data = graph.run(cypher, identifier=identifier).data()
        except Exception as e:
            raise Exception(f"Error running Cypher query: {str(e)}")

        if not raw_data:
            return {}

        data_element = dict(raw_data[0]["n"])
        data_element_concept = {
            "identifier": raw_data[0]["d"]["identifier"],
            "name": raw_data[0]["d"]["name"]
        }

        value_domain = {
            "identifier": raw_data[0]["v"]["identifier"],
            "name": raw_data[0]["v"]["name"]
        }

        data_element["data_element_concept"] = data_element_concept
        data_element["value_domain"] = value_domain

        return data_element
