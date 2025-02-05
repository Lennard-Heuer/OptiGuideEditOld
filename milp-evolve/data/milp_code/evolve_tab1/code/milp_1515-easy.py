import random
import time
import numpy as np
import networkx as nx
from itertools import combinations
from pyscipopt import Model, quicksum

class Graph:
    """
    Helper function: Container for a graph.
    """
    def __init__(self, number_of_nodes, edges, degrees, neighbors):
        self.number_of_nodes = number_of_nodes
        self.nodes = np.arange(number_of_nodes)
        self.edges = edges
        self.degrees = degrees
        self.neighbors = neighbors

    @staticmethod
    def erdos_renyi(number_of_nodes, edge_probability):
        """
        Generate an Erdös-Rényi random graph with a given edge probability.
        """
        edges = set()
        degrees = np.zeros(number_of_nodes, dtype=int)
        neighbors = {node: set() for node in range(number_of_nodes)}
        for edge in combinations(np.arange(number_of_nodes), 2):
            if np.random.uniform() < edge_probability:
                edges.add(edge)
                degrees[edge[0]] += 1
                degrees[edge[1]] += 1
                neighbors[edge[0]].add(edge[1])
                neighbors[edge[1]].add(edge[0])
        graph = Graph(number_of_nodes, edges, degrees, neighbors)
        return graph

    @staticmethod
    def barabasi_albert(number_of_nodes, edges_to_attach):
        """
        Generate a Barabási-Albert random graph.
        """
        edges = set()
        neighbors = {node: set() for node in number_of_nodes}
        G = nx.barabasi_albert_graph(number_of_nodes, edges_to_attach)
        degrees = np.zeros(number_of_nodes, dtype=int)
        for edge in G.edges:
            edges.add(edge)
            degrees[edge[0]] += 1
            degrees[edge[1]] += 1
            neighbors[edge[0]].add(edge[1])
            neighbors[edge[1]].add(edge[0])
        graph = Graph(number_of_nodes, edges, degrees, neighbors)
        return graph

class HumanitarianAidDistribution:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_graph(self):
        if self.graph_type == 'erdos_renyi':
            return Graph.erdos_renyi(self.n_nodes, self.edge_probability)
        elif self.graph_type == 'barabasi_albert':
            return Graph.barabasi_albert(self.n_nodes, self.edges_to_attach)
        else:
            raise ValueError("Unsupported graph type.")

    def get_instance(self):
        graph = self.generate_graph()
        critical_care_demand = np.random.randint(1, 100, size=graph.number_of_nodes)
        network_capacity = np.random.randint(100, 500, size=graph.number_of_nodes)
        zoning_costs = np.random.randint(50, 150, size=graph.number_of_nodes)
        transportation_costs = np.random.rand(graph.number_of_nodes, graph.number_of_nodes) * 50
        service_hours = np.random.randint(1, 10, size=(graph.number_of_nodes, graph.number_of_nodes))

        ### given instance data code ends here
        access_restrictions = np.random.choice([0, 1], size=graph.number_of_nodes)
        security_risks = np.random.normal(loc=5.0, scale=2.0, size=graph.number_of_nodes)
        priority_safety = np.random.choice([0, 1], size=graph.number_of_nodes)
        theft_risks = np.random.gamma(shape=2.0, scale=1.0, size=(graph.number_of_nodes, graph.number_of_nodes))

        ### new instance data code ends here

        res = {
            'graph': graph,
            'critical_care_demand': critical_care_demand,
            'network_capacity': network_capacity,
            'zoning_costs': zoning_costs,
            'transportation_costs': transportation_costs,
            'service_hours': service_hours,
            'access_restrictions': access_restrictions,
            'security_risks': security_risks,
            'priority_safety': priority_safety,
            'theft_risks': theft_risks
        }
        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        graph = instance['graph']
        critical_care_demand = instance['critical_care_demand']
        network_capacity = instance['network_capacity']
        zoning_costs = instance['zoning_costs']
        transportation_costs = instance['transportation_costs']
        service_hours = instance['service_hours']
        access_restrictions = instance['access_restrictions']
        security_risks = instance['security_risks']
        priority_safety = instance['priority_safety']
        theft_risks = instance['theft_risks']

        model = Model("HumanitarianAidDistribution")

        # Add variables
        MedicalCenterSelection_vars = {node: model.addVar(vtype="B", name=f"MedicalCenterSelection_{node}") for node in graph.nodes}
        HealthcareRouting_vars = {(i, j): model.addVar(vtype="B", name=f"HealthcareRouting_{i}_{j}") for i in graph.nodes for j in graph.nodes}
        
        # New service time variables
        ServiceTime_vars = {node: model.addVar(vtype="C", name=f"ServiceTime_{node}") for node in graph.nodes}

        # New delivery time window satisfaction variables
        DeliveryWindowSatisfaction_vars = {node: model.addVar(vtype="B", name=f"DeliveryWindowSatisfaction_{node}") for node in graph.nodes}

        # Resource Theft Risk Variables
        ResourceTheftRisk_vars = {(i, j): model.addVar(vtype="C", name=f"ResourceTheftRisk_{i}_{j}") for i in graph.nodes for j in graph.nodes}

        # Network Capacity Constraints for healthcare centers
        for center in graph.nodes:
            model.addCons(quicksum(critical_care_demand[node] * HealthcareRouting_vars[node, center] for node in graph.nodes) <= network_capacity[center], name=f"NetworkCapacity_{center}")

        # Connection Constraints of each node to one healthcare center
        for node in graph.nodes:
            model.addCons(quicksum(HealthcareRouting_vars[node, center] for center in graph.nodes) == 1, name=f"CriticalCareDemand_{node}")

        # Ensure routing to selected healthcare centers
        for node in graph.nodes:
            for center in graph.nodes:
                model.addCons(HealthcareRouting_vars[node, center] <= MedicalCenterSelection_vars[center], name=f"HealthcareServiceConstraint_{node}_{center}")

        # Service time constraints
        for node in graph.nodes:
            model.addCons(ServiceTime_vars[node] >= 0, name=f'ServiceMinTime_{node}')
            model.addCons(ServiceTime_vars[node] <= service_hours.max(), name=f'ServiceMaxTime_{node}')

        # Ensure at least 95% of facilities meet the delivery time window
        total_facilities = len(graph.nodes)
        min_satisfied = int(0.95 * total_facilities)
        model.addCons(quicksum(DeliveryWindowSatisfaction_vars[node] for node in graph.nodes) >= min_satisfied, name="MinDeliveryWindowSatisfaction")

        # Link service time with delivery window satisfaction variables
        for node in graph.nodes:
            model.addCons(ServiceTime_vars[node] <= DeliveryWindowSatisfaction_vars[node] * service_hours.max(), name=f"DeliveryWindowLink_{node}")

        # Restrict access to certain regions
        for node in graph.nodes:
            model.addCons(
                quicksum(HealthcareRouting_vars[node, center] for center in graph.nodes if access_restrictions[center] == 1) == 0,
                name=f"RestrictedAccess_{node}"
            )

        # Prioritize safety of women and children
        for node in graph.nodes:
            if priority_safety[node] == 1:
                model.addCons(
                    quicksum(MedicalCenterSelection_vars[neighbor] for neighbor in graph.neighbors[node] if security_risks[neighbor] <= 5.0) >= 1,
                    name=f"PrioritizeSafety_{node}"
                )

        # Minimize resource theft risk
        for i, j in graph.edges:
            if access_restrictions[i] == 0 and access_restrictions[j] == 0:
                model.addCons(
                    HealthcareRouting_vars[i, j] * theft_risks[i, j] <= ResourceTheftRisk_vars[i, j],
                    name=f"ResourceTheftRiskConstraint_{i}_{j}"
                )

        # Objective: Minimize total zoning, transportation costs, maximize delivery window satisfaction, and minimize resource theft risk
        zoning_cost = quicksum(MedicalCenterSelection_vars[node] * zoning_costs[node] for node in graph.nodes)
        transportation_cost = quicksum(HealthcareRouting_vars[i, j] * transportation_costs[i, j] for i in graph.nodes for j in graph.nodes)
        theft_risk_cost = quicksum(ResourceTheftRisk_vars[i, j] for i in graph.nodes for j in graph.nodes)

        total_cost = zoning_cost + transportation_cost + theft_risk_cost
        
        model.setObjective(total_cost, "minimize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_nodes': 50,
        'edge_probability': 0.76,
        'graph_type': 'erdos_renyi',
        'edges_to_attach': 50,
    }

    humanitarian_optimization = HumanitarianAidDistribution(parameters, seed=seed)
    instance = humanitarian_optimization.get_instance()
    solve_status, solve_time, obj_val = humanitarian_optimization.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {obj_val:.2f}")