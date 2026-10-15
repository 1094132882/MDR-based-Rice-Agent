"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/25 15:46
"""
from rice_Python.App.mdr.subdomain import Subdomain


class SubdomainService:
    def __init__(self, graph):
        self.graph = graph
        self.subdomains = self.search_subdomain()

    def search_subdomain(self):
        cypher = """
        MATCH (n:SubDomain) RETURN n ORDER BY n.identifier
        """
        row_data = self.graph.run(cypher).data()
        subdomains = []
        for row in row_data:
            row = row['n']
            subdomains.append(Subdomain(self.graph, row))
        return subdomains

    def get_subdomain(self):
        return self.subdomains

    def get_subdomain_list(self):
        subdomain_list = []
        for subdomain in self.subdomains:
            subdomain_list.append(subdomain.get_node())
        return subdomain_list

    def get_subdomain_by_identifier(self, identifier):
        for subdomain in self.subdomains:
            if subdomain.get_identifier() == identifier:
                return subdomain
        return None

    def get_subdomain_node_by_identifier(self, identifier):
        subdomain = self.get_subdomain_by_identifier(identifier)
        if not subdomain:
            return None
        return subdomain.get_detailed_information()

    def get_tables_by_subdomain_identifier_and_dataset_identifier(self, subdomain_identifier, dataset_identifier, page):
        subdomain = self.get_subdomain_by_identifier(subdomain_identifier)
        if not subdomain:
            return None
        dataset = subdomain.get_dataset_by_identifier(dataset_identifier)
        if not dataset:
            return None
        tables = dataset.get_tables(page)
        return tables
