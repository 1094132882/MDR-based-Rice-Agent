"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/24 0:18
"""
from py2neo import Graph
from dotenv import load_dotenv
import os

from rice_Python.App.mdr.dataelement import DataElement
from rice_Python.App.mdr.subdomainservice import SubdomainService
from rice_Python.App.mdr.mdrservice import MDRService

load_dotenv()


class Neo4jService:
    def __init__(self):
        self.graph = Graph(os.getenv("NEO4J_URI"),
                           user=os.getenv("NEO4J_USER"),
                           password=os.getenv("NEO4J_PASSWORD"))
        self.subdomain_service = SubdomainService(self.graph)
        self.mdr_service = MDRService(self.graph)

    def get_object_class_list(self):
        return self.mdr_service.get_object_class_list()

    def get_object_class_by_identifier(self, identifier):
        return self.mdr_service.get_object_class_by_identifier(identifier)

    def get_property_list(self):
        return self.mdr_service.get_property_list()

    def get_property_by_identifier(self, identifier):
        return self.mdr_service.get_property_by_identifier(identifier)

    def get_conceptual_domain_list(self):
        return self.mdr_service.get_conceptual_domain_list()

    def get_conceptual_domain_by_identifier(self, identifier):
        return self.mdr_service.get_conceptual_domain_by_identifier(identifier)

    def get_data_element_concept_list(self):
        return self.mdr_service.get_data_element_concept_list()

    def get_data_element_concept_by_identifier(self, identifier):
        return self.mdr_service.get_data_element_concept_by_identifier(identifier)

    def get_value_domain_list(self):
        return self.mdr_service.get_value_domain_list()

    def get_value_domain_by_identifier(self, identifier):
        return self.mdr_service.get_value_domain_by_identifier(identifier)

    def get_data_element_list(self):
        return DataElement.get_data_element_list(self.graph)

    def get_data_element_by_identifier(self, identifier):
        return DataElement.get_data_element_by_identifier(self.graph, identifier)

    def get_subdomain_list(self):
        return self.subdomain_service.get_subdomain_list()

    def get_subdomain_by_identifier(self, identifier):
        subdomain = self.subdomain_service.get_subdomain_node_by_identifier(identifier)
        for dataset in subdomain["datasets"]:
            if dataset.get("table_metadata"):
                for table_metadata_element in dataset["table_metadata"]["table_metadata_elements"]:
                    data_element_identifier = table_metadata_element["data_element_identifier"]
                    data_element = self.mdr_service.get_data_element_by_identifier(data_element_identifier)
                    if data_element is not None:
                        table_metadata_element["data_element"] = data_element
                    else:
                        table_metadata_element["data_element"] = {}
            else:
                dataset["table_metadata"] = {}
            if dataset["is_column_first"]:
                for cm in dataset["column_metadata"]:
                    if len(cm["column_metadata_elements"]) > 0:
                        for cme in cm["column_metadata_elements"]:
                            data_element_identifier = cme["data_element_identifier"]
                            data_element = self.mdr_service.get_data_element_by_identifier(data_element_identifier)
                            if data_element is not None:
                                cme["data_element"] = data_element
                            else:
                                cme["data_element"] = {}
                    else:
                        data_element_identifier = cm["data_element_identifier"]
                        data_element = self.mdr_service.get_data_element_by_identifier(data_element_identifier)
                        if data_element is not None:
                            cm["data_element"] = data_element
                        else:
                            cm["data_element"] = {}
            else:
                for rm in dataset["row_metadata"]:
                    for cm in rm["column_metadata"]:
                        if len(cm["column_metadata_elements"]) > 0:
                            for cme in cm["column_metadata_elements"]:
                                data_element_identifier = cme["data_element_identifier"]
                                data_element = self.mdr_service.get_data_element_by_identifier(data_element_identifier)
                                if data_element is not None:
                                    cme["data_element"] = data_element
                                else:
                                    cme["data_element"] = {}
                        else:
                            data_element_identifier = cm["data_element_identifier"]
                            data_element = self.mdr_service.get_data_element_by_identifier(data_element_identifier)
                            if data_element is not None:
                                cm["data_element"] = data_element
                            else:
                                cm["data_element"] = {}
        return subdomain

    def get_tables_by_subdomain_identifier_and_dataset_identifier(self, subdomain_identifier, dataset_identifier, page):
        return self.subdomain_service.get_tables_by_subdomain_identifier_and_dataset_identifier(subdomain_identifier,
                                                                                                dataset_identifier, page)