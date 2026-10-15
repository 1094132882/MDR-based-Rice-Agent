"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/25 14:42
"""

from rice_Python.App.mdr.dataset import Dataset


class Subdomain:
    def __init__(self, graph, subdomain_node):
        self.graph = graph
        self.subdomain_node = subdomain_node
        self.datasets = self.search_dataset()

    def search_dataset(self):
        cypher = """
        MATCH (n:SubDomain) -[:contain]-> (m:DataSet) 
        WHERE n.identifier = $identifier 
        RETURN m ORDER BY m.identifier
        """
        row_data = self.graph.run(cypher, identifier=self.subdomain_node['identifier']).data()
        datasets = []
        for row in row_data:
            row = row['m']
            datasets.append(Dataset(self.graph, row))
        return datasets

    def get_identifier(self):
        return self.subdomain_node['identifier']

    def get_name(self):
        return self.subdomain_node['name']

    def get_description(self):
        return self.subdomain_node['description']

    def get_access(self):
        return self.subdomain_node['access']

    def get_datasets(self):
        return self.datasets

    def get_node(self):
        subdomain_node = dict(self.subdomain_node)
        # subdomain_node['datasets'] = [dataset.get_node() for dataset in self.datasets]
        subdomain_node['datasets_count'] = len(self.datasets)
        return subdomain_node

    def get_detailed_information(self):
        subdomain_node = dict(self.subdomain_node)
        subdomain_node['datasets'] = [dataset.get_node() for dataset in self.datasets]
        return subdomain_node

    def get_dataset_by_identifier(self, identifier):
        for dataset in self.datasets:
            if dataset.get_identifier() == identifier:
                return dataset
        return None
