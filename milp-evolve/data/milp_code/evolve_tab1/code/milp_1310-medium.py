import random
import time
import numpy as np
from itertools import combinations
from pyscipopt import Model, quicksum
import networkx as nx

class Graph:
    def __init__(self, number_of_nodes, edges, degrees, neighbors):
        self.number_of_nodes = number_of_nodes
        self.nodes = np.arange(number_of_nodes)
        self.edges = edges
        self.degrees = degrees
        self.neighbors = neighbors

    @staticmethod
    def barabasi_albert(number_of_nodes, affinity):
        assert affinity >= 1 and affinity < number_of_nodes

        edges = set()
        degrees = np.zeros(number_of_nodes, dtype=int)
        neighbors = {node: set() for node in range(number_of_nodes)}
        for new_node in range(affinity, number_of_nodes):
            if new_node == affinity:
                neighborhood = np.arange(new_node)
            else:
                neighbor_prob = degrees[:new_node] / (2 * len(edges))
                neighborhood = np.random.choice(new_node, affinity, replace=False, p=neighbor_prob)
            for node in neighborhood:
                edges.add((node, new_node))
                degrees[node] += 1
                degrees[new_node] += 1
                neighbors[node].add(new_node)
                neighbors[new_node].add(node)

        graph = Graph(number_of_nodes, edges, degrees, neighbors)
        return graph

class LogisticsPackageRouting:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    def generate_instance(self):
        assert self.n_nodes > 0 and self.n_customers > 0
        assert self.min_depot_cost >= 0 and self.max_depot_cost >= self.min_depot_cost
        assert self.min_customer_cost >= 0 and self.max_customer_cost >= self.min_customer_cost
        assert self.min_depot_capacity > 0 and self.max_depot_capacity >= self.min_depot_capacity

        depot_costs = np.random.randint(self.min_depot_cost, self.max_depot_cost + 1, self.n_nodes)
        customer_costs = np.random.randint(self.min_customer_cost, self.max_customer_cost + 1, (self.n_nodes, self.n_customers))
        capacities = np.random.randint(self.min_depot_capacity, self.max_depot_capacity + 1, self.n_nodes)

        # Generate varying demand scenarios
        demand_scenarios = [np.random.randint(1, 10, self.n_customers) for _ in range(self.n_scenarios)]

        graph = Graph.barabasi_albert(self.n_nodes, self.affinity)
        cliques = []
        for clique in nx.find_cliques(nx.Graph(graph.edges)):
            if len(clique) > 1:
                cliques.append(tuple(sorted(clique)))

        return {
            "depot_costs": depot_costs,
            "customer_costs": customer_costs,
            "capacities": capacities,
            "demand_scenarios": demand_scenarios,
            "cliques": cliques,
        }
        
    def solve(self, instance):
        depot_costs = instance['depot_costs']
        customer_costs = instance['customer_costs']
        capacities = instance['capacities']
        demand_scenarios = instance['demand_scenarios']
        cliques = instance['cliques']
        
        model = Model("LogisticsPackageRoutingRobust")
        n_nodes = len(depot_costs)
        n_customers = len(customer_costs[0])
        n_scenarios = len(demand_scenarios)
        
        # Decision variables
        depot_open = {c: model.addVar(vtype="B", name=f"DepotOpen_{c}") for c in range(n_nodes)}
        customer_served = {(c, r): model.addVar(vtype="B", name=f"Depot_{c}_Customer_{r}") for c in range(n_nodes) for r in range(n_customers)}
        
        # Objective: minimize the total cost including depot costs and customer servicing costs
        model.setObjective(
            quicksum(depot_costs[c] * depot_open[c] for c in range(n_nodes)) +
            quicksum(customer_costs[c, r] * customer_served[c, r] for c in range(n_nodes) for r in range(n_customers)), "minimize"
        )
        
        # Constraints: Each customer is served by at least one depot
        for r in range(n_customers):
            model.addCons(quicksum(customer_served[c, r] for c in range(n_nodes)) >= 1, f"Customer_{r}_Service")
        
        # Constraints: Only open depots can serve customers
        for c in range(n_nodes):
            for r in range(n_customers):
                model.addCons(customer_served[c, r] <= depot_open[c], f"Depot_{c}_Serve_{r}")
        
        # Robust Constraints: Depots cannot exceed their capacity in the worst demand scenario
        for c in range(n_nodes):
            for s in range(n_scenarios):
                model.addCons(quicksum(demand_scenarios[s][r] * customer_served[c, r] for r in range(n_customers)) <= capacities[c], f"Depot_{c}_Capacity_Scenario_{s}")
        
        # Constraints: Depot Route Cliques
        for count, clique in enumerate(cliques):
            model.addCons(quicksum(depot_open[node] for node in clique) <= 1, f"Clique_{count}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time, model.getObjVal()

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_nodes': 20,
        'n_customers': 672,
        'min_customer_cost': 2058,
        'max_customer_cost': 3000,
        'min_depot_cost': 168,
        'max_depot_cost': 5000,
        'min_depot_capacity': 34,
        'max_depot_capacity': 47,
        'affinity': 4,
        'n_scenarios': 0,
    }

    logistics_optimizer = LogisticsPackageRouting(parameters, seed)
    instance = logistics_optimizer.generate_instance()
    solve_status, solve_time, objective_value = logistics_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")