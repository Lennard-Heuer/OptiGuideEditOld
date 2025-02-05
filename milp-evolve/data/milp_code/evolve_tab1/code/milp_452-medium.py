import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum
from itertools import combinations

class HCAN:
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

    def generate_healthcare_data(self, G):
        for node in G.nodes:
            G.nodes[node]['patients'] = np.random.randint(10, 200)
            G.nodes[node]['utility'] = np.random.randint(1, 100)  # Adding utility for nodes

        for u, v in G.edges:
            G[u][v]['visit_time'] = np.random.randint(1, 3)
            G[u][v]['capacity'] = np.random.randint(5, 15)
            G[u][v]['distance'] = np.random.randint(1, 20)  # Adding distance for edges

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
        self.generate_healthcare_data(G)
        E_invalid = self.generate_incompatibility_data(G)
        zones = self.create_zones(G)

        healthcare_cap = {node: np.random.randint(20, 100) for node in G.nodes}
        shift_cost = {(u, v): np.random.uniform(1.0, 5.0) for u, v in G.edges}

        care_scenarios = [{} for _ in range(self.no_of_scenarios)]
        for s in range(self.no_of_scenarios):
            care_scenarios[s]['patients'] = {node: np.random.normal(G.nodes[node]['patients'], G.nodes[node]['patients'] * self.patient_variation)
                                              for node in G.nodes}
            care_scenarios[s]['visit_time'] = {(u, v): np.random.normal(G[u][v]['visit_time'], G[u][v]['visit_time'] * self.time_variation)
                                               for u, v in G.edges}
            care_scenarios[s]['healthcare_cap'] = {node: np.random.normal(healthcare_cap[node], healthcare_cap[node] * self.capacity_variation)
                                                   for node in G.nodes}

        # additional bus and route data
        for node in G.nodes:
            G.nodes[node]['capacity'] = np.random.randint(1, self.max_capacity)         # From RouteAssignment data
            G.nodes[node]['demand'] = np.random.randint(1, self.max_demand)             # From RouteAssignment data
        for u, v in G.edges:                                                          
            G[u][v]['time'] = np.random.exponential(scale=self.exp_scale)              # From RouteAssignment data

        # New data for weather impact and traffic data
        weather_impact = {f"{u}_{v}": np.random.normal(1, self.weather_std) for u, v in G.edges}
        traffic_data = {f"{u}_{v}": np.random.uniform(0.5, 1.5) for u, v in G.edges}
        vehicle_emissions = {vtype: np.random.uniform(100, 300) for vtype in range(self.num_vehicle_types)}
        
        transportation_costs = {node: np.random.uniform(0.1, 1.0) for node in G.nodes}
        mutual_exclusivity_pairs = self.generate_mutual_exclusivity_pairs(len(G.nodes))

        return {
            'G': G,
            'E_invalid': E_invalid, 
            'zones': zones, 
            'healthcare_cap': healthcare_cap, 
            'shift_cost': shift_cost,
            'care_scenarios': care_scenarios,
            'weather_impact': weather_impact,
            'traffic_data': traffic_data,
            'vehicle_emissions': vehicle_emissions,
            'transportation_costs': transportation_costs,
            'mutual_exclusivity_pairs': mutual_exclusivity_pairs,
        }
    
    def generate_mutual_exclusivity_pairs(self, num_nodes):
        pairs = []
        for _ in range(self.n_exclusive_pairs):
            node1 = random.randint(0, num_nodes - 1)
            node2 = random.randint(0, num_nodes - 1)
            while node1 == node2:
                node2 = random.randint(0, num_nodes - 1)
            pairs.append((node1, node2))
        return pairs

    def solve(self, instance):
        G, E_invalid, zones = instance['G'], instance['E_invalid'], instance['zones']
        healthcare_cap = instance['healthcare_cap']
        shift_cost = instance['shift_cost']
        care_scenarios = instance['care_scenarios']
        weather_impact = instance['weather_impact']
        traffic_data = instance['traffic_data']
        vehicle_emissions = instance['vehicle_emissions']
        transportation_costs = instance['transportation_costs']
        mutual_exclusivity_pairs = instance['mutual_exclusivity_pairs']

        model = Model("HCAN")
        nurse_shift_vars = {f"NurseShift{node}": model.addVar(vtype="B", name=f"NurseShift{node}") for node in G.nodes}
        home_visit_vars = {f"HomeVisit{u}_{v}": model.addVar(vtype="B", name=f"HomeVisit{u}_{v}") for u, v in G.edges}
        shift_budget = model.addVar(vtype="C", name="shift_budget")

        # New variables from RouteAssignment
        bus_stop_vars = {f"BusStop{node}": model.addVar(vtype="B", name=f"BusStop{node}") for node in G.nodes}
        route_vars = {f"Route{u}_{v}": model.addVar(vtype="B", name=f"Route{u}_{v}") for u, v in G.edges}

        # New variables for weather and traffic impacts
        travel_time_vars = {f"TravelTime{u}_{v}": model.addVar(vtype="C", name=f"TravelTime{u}_{v}") for u, v in G.edges}
        vehicle_vars = {f"VehicleType{u}_{v}": {vtype: model.addVar(vtype="B", name=f"VehicleType{u}_{v}_vtype{vtype}") for vtype in range(self.num_vehicle_types)} for u, v in G.edges}

        # Scenario-specific variables
        patient_vars = {s: {f"NurseShift{node}_s{s}": model.addVar(vtype="B", name=f"NurseShift{node}_s{s}") for node in G.nodes} for s in range(self.no_of_scenarios)}
        visit_time_vars = {s: {f"HomeVisit{u}_{v}_s{s}": model.addVar(vtype="B", name=f"HomeVisit{u}_{v}_s{s}") for u, v in G.edges} for s in range(self.no_of_scenarios)}
        care_cap_vars = {s: {f"Capacity{node}_s{s}": model.addVar(vtype="B", name=f"Capacity{node}_s{s}") for node in G.nodes} for s in range(self.no_of_scenarios)}

        objective_expr = quicksum(
            care_scenarios[s]['patients'][node] * patient_vars[s][f"NurseShift{node}_s{s}"]
            for s in range(self.no_of_scenarios) for node in G.nodes
        )

        objective_expr -= quicksum(
            care_scenarios[s]['visit_time'][(u, v)] * visit_time_vars[s][f"HomeVisit{u}_{v}_s{s}"]
            for s in range(self.no_of_scenarios) for u, v in E_invalid
        )

        objective_expr -= quicksum(
            care_scenarios[s]['healthcare_cap'][node] * care_scenarios[s]['patients'][node]
            for s in range(self.no_of_scenarios) for node in G.nodes
        )

        objective_expr -= quicksum(
            shift_cost[(u, v)] * home_visit_vars[f"HomeVisit{u}_{v}"]
            for u, v in G.edges
        )

        # New objective parts from RouteAssignment
        efficiency_expr = quicksum(route_vars[f"Route{u}_{v}"] * G[u][v]['time'] for u, v in G.edges)
        emissions_expr = quicksum(vehicle_vars[f"VehicleType{u}_{v}"][vtype] * vehicle_emissions[vtype] for u, v in G.edges for vtype in range(self.num_vehicle_types))
        objective_expr -= (efficiency_expr + emissions_expr)

        # Objective parts from City Planner
        utility_expr = quicksum(G.nodes[node]['utility'] * nurse_shift_vars[f"NurseShift{node}"] for node in G.nodes)
        transportation_cost_expr = quicksum(transportation_costs[node] * nurse_shift_vars[f"NurseShift{node}"] for node in G.nodes)
        objective_expr += utility_expr - transportation_cost_expr

        for i, zone in enumerate(zones):
            model.addCons(
                quicksum(nurse_shift_vars[f"NurseShift{node}"] for node in zone) <= 1,
                name=f"WorkerGroup_{i}"
            )

        M = 1000  # Big M constant, set contextually larger than any decision boundary.

        for u, v in G.edges:
            model.addCons(
                nurse_shift_vars[f"NurseShift{u}"] + nurse_shift_vars[f"NurseShift{v}"] <= 1 + M * (1 - home_visit_vars[f"HomeVisit{u}_{v}"]),
                name=f"PatientFlow_{u}_{v}"
            )
            model.addCons(
                nurse_shift_vars[f"NurseShift{u}"] + nurse_shift_vars[f"NurseShift{v}"] >= 2 * home_visit_vars[f"HomeVisit{u}_{v}"] - M * (1 - home_visit_vars[f"HomeVisit{u}_{v}"]),
                name=f"PatientFlow_{u}_{v}_other"
            )
            model.addCons(
                travel_time_vars[f"TravelTime{u}_{v}"] == G[u][v]['time'] * weather_impact[f"{u}_{v}"] * traffic_data[f"{u}_{v}"],
                name=f"TravelTimeWeatherTraffic_{u}_{v}"
            )
            model.addCons(
                nurse_shift_vars[f"NurseShift{u}"] + nurse_shift_vars[f"NurseShift{v}"] - route_vars[f"Route{u}_{v}"] <= 1,
                name=f"MallDistanceConstraints_{u}_{v}"
            )

        model.addCons(
            shift_budget <= self.shift_hours,
            name="OffTime_Limit"
        )

        # New constraints similar to bus route assignment
        for node in G.nodes:
            model.addCons(
                quicksum(route_vars[f"Route{u}_{v}"] for u, v in G.edges if u == node or v == node) <= G.nodes[node]['capacity'],
                name=f"Capacity_Healthcare_{node}"
            )

        for u, v in G.edges:
            model.addCons(
                bus_stop_vars[f"BusStop{u}"] + bus_stop_vars[f"BusStop{v}"] >= route_vars[f"Route{u}_{v}"],
                name=f"RouteAssignment_{u}_{v}"
            )
            model.addCons(
                quicksum(vehicle_vars[f"VehicleType{u}_{v}"][vtype] for vtype in range(self.num_vehicle_types)) == route_vars[f"Route{u}_{v}"],
                name=f"VehicleAssignment_{u}_{v}"
            )

        for node in G.nodes:
            model.addCons(
                quicksum(nurse_shift_vars[f"NurseShift{neighbor}"] for neighbor in G.neighbors(node)) <= G.nodes[node]['capacity'],
                name=f"CapacityConstraints_{node}"
            )

        for (node1, node2) in mutual_exclusivity_pairs:
            model.addCons(
                nurse_shift_vars[f"NurseShift{node1}"] + nurse_shift_vars[f"NurseShift{node2}"] <= 1,
                name=f"MutualExclusivityConstraints_{node1}_{node2}"
            )
        
        # Robust constraints to ensure feasibility across all scenarios
        for s in range(self.no_of_scenarios):
            for node in G.nodes:
                model.addCons(
                    patient_vars[s][f"NurseShift{node}_s{s}"] == nurse_shift_vars[f"NurseShift{node}"],
                    name=f"PatientDemandScenario_{node}_s{s}"
                )
                model.addCons(
                    care_cap_vars[s][f"Capacity{node}_s{s}"] == nurse_shift_vars[f"NurseShift{node}"],
                    name=f"ResourceAvailability_{node}_s{s}"
                )
            for u, v in G.edges:
                model.addCons(
                    visit_time_vars[s][f"HomeVisit{u}_{v}_s{s}"] == home_visit_vars[f"HomeVisit{u}_{v}"],
                    name=f"FlowConstraintVisits_{u}_{v}_s{s}"
                )

        model.setObjective(objective_expr, "maximize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_nodes': 66,
        'max_nodes': 1071,
        'zone_prob': 0.1,
        'exclusion_rate': 0.8,
        'shift_hours': 840,
        'no_of_scenarios': 84,
        'patient_variation': 0.52,
        'time_variation': 0.38,
        'capacity_variation': 0.59,
        'max_capacity': 40,
        'max_demand': 75,
        'exp_scale': 125.0,
        'weather_std': 0.2,
        'num_vehicle_types': 3,
        'n_exclusive_pairs': 200,
    }

    hcan = HCAN(parameters, seed=seed)
    instance = hcan.get_instance()
    solve_status, solve_time = hcan.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")