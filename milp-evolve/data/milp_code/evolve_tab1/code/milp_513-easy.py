import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class VehicleAllocationMILP:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_city_graph(self):
        n_nodes = np.random.randint(self.min_nodes, self.max_nodes)
        G = nx.erdos_renyi_graph(n=n_nodes, p=self.zone_prob, directed=True, seed=self.seed)
        return G
    
    def generate_transport_data(self, G):
        for node in G.nodes:
            G.nodes[node]['demand'] = np.random.randint(10, 200)

        for u, v in G.edges:
            G[u][v]['distance'] = np.random.randint(1, 10)
            G[u][v]['capacity'] = np.random.randint(5, 20)
    
    def generate_incompatibility_data(self, G):
        E_invalid = set()
        for edge in G.edges:
            if np.random.random() <= self.exclusion_rate:
                E_invalid.add(edge)
        return E_invalid
    
    def create_zones(self, G):
        zones = list(nx.find_cliques(G.to_undirected()))
        return zones
    
    def get_instance(self):
        G = self.generate_city_graph()
        self.generate_transport_data(G)
        E_invalid = self.generate_incompatibility_data(G)
        zones = self.create_zones(G)
        
        charging_capacity = {node: np.random.randint(20, 100) for node in G.nodes}
        trip_cost = {(u, v): np.random.uniform(1.0, 5.0) for u, v in G.edges}
        
        transport_scenarios = [{} for _ in range(self.no_of_scenarios)]
        for s in range(self.no_of_scenarios):
            transport_scenarios[s]['demand'] = {node: np.random.normal(G.nodes[node]['demand'], G.nodes[node]['demand'] * self.demand_variation)
                                                for node in G.nodes}
            transport_scenarios[s]['distance'] = {(u, v): np.random.normal(G[u][v]['distance'], G[u][v]['distance'] * self.distance_variation)
                                                  for u, v in G.edges}
            transport_scenarios[s]['charging_capacity'] = {node: np.random.normal(charging_capacity[node], charging_capacity[node] * self.capacity_variation)
                                                           for node in G.nodes}
        
        return {
            'G': G,
            'E_invalid': E_invalid, 
            'zones': zones, 
            'charging_capacity': charging_capacity, 
            'trip_cost': trip_cost, 
            'transport_scenarios': transport_scenarios
        }
    
    def solve(self, instance):
        G, E_invalid, zones = instance['G'], instance['E_invalid'], instance['zones']
        charging_capacity = instance['charging_capacity']
        trip_cost = instance['trip_cost']
        transport_scenarios = instance['transport_scenarios']

        model = Model("VehicleAllocation")
        vehicle_vars = {f"Vehicle{node}": model.addVar(vtype="B", name=f"Vehicle{node}") for node in G.nodes}
        route_vars = {f"Route{u}_{v}": model.addVar(vtype="B", name=f"Route{u}_{v}") for u, v in G.edges}

        # Scenario-specific variables
        demand_vars = {s: {f"Demand{node}_s{s}": model.addVar(vtype="B", name=f"Demand{node}_s{s}") for node in G.nodes} for s in range(self.no_of_scenarios)}
        distance_vars = {s: {f"Distance{u}_{v}_s{s}": model.addVar(vtype="B", name=f"Distance{u}_{v}_s{s}") for u, v in G.edges} for s in range(self.no_of_scenarios)}
        capacity_vars = {s: {f"Capacity{node}_s{s}": model.addVar(vtype="B", name=f"Capacity{node}_s{s}") for node in G.nodes} for s in range(self.no_of_scenarios)}

        objective_expr = quicksum(
            transport_scenarios[s]['demand'][node] * demand_vars[s][f"Demand{node}_s{s}"]
            for s in range(self.no_of_scenarios) for node in G.nodes
        )

        objective_expr -= quicksum(
            transport_scenarios[s]['distance'][(u, v)] * distance_vars[s][f"Distance{u}_{v}_s{s}"]
            for s in range(self.no_of_scenarios) for u, v in E_invalid
        )

        objective_expr -= quicksum(
            trip_cost[(u, v)] * route_vars[f"Route{u}_{v}"]
            for u, v in G.edges
        )

        for i, zone in enumerate(zones):
            model.addCons(
                quicksum(vehicle_vars[f"Vehicle{node}"] for node in zone) <= 1,
                name=f"VehicleGroup_{i}"
            )

        M = 1000  # Big M constant, set contextually larger than any decision boundary.

        for u, v in G.edges:
            model.addCons(
                vehicle_vars[f"Vehicle{u}"] + vehicle_vars[f"Vehicle{v}"] <= 1 + M * (1 - route_vars[f"Route{u}_{v}"]),
                name=f"VehicleFlow_{u}_{v}"
            )
            model.addCons(
                vehicle_vars[f"Vehicle{u}"] + vehicle_vars[f"Vehicle{v}"] >= 2 * route_vars[f"Route{u}_{v}"] - M * (1 - route_vars[f"Route{u}_{v}"]),
                name=f"VehicleFlow_{u}_{v}_other"
            )

        # Robust constraints to ensure feasibility across all scenarios
        for s in range(self.no_of_scenarios):
            for node in G.nodes:
                model.addCons(
                    demand_vars[s][f"Demand{node}_s{s}"] == vehicle_vars[f"Vehicle{node}"],
                    name=f"DemandScenario_{node}_s{s}"
                )
                model.addCons(
                    capacity_vars[s][f"Capacity{node}_s{s}"] == vehicle_vars[f"Vehicle{node}"],
                    name=f"CapacityScenario_{node}_s{s}"
                )
            for u, v in G.edges:
                model.addCons(
                    distance_vars[s][f"Distance{u}_{v}_s{s}"] == route_vars[f"Route{u}_{v}"],
                    name=f"DistanceScenario_{u}_{v}_s{s}"
                )

        model.setObjective(objective_expr, "maximize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_nodes': 40,
        'max_nodes': 900,
        'zone_prob': 0.1,
        'exclusion_rate': 0.66,
        'no_of_scenarios': 40,
        'demand_variation': 0.66,
        'distance_variation': 0.74,
        'capacity_variation': 0.55,
    }
    
    vehicle_allocation = VehicleAllocationMILP(parameters, seed=seed)
    instance = vehicle_allocation.get_instance()
    solve_status, solve_time = vehicle_allocation.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")