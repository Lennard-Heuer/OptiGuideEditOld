import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class EmergencySupplyDistribution:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# data generation #################
    def generate_instance(self):
        assert self.n_supply_centers > 0 and self.n_disaster_zones > 0
        assert self.min_transport_cost >= 0 and self.max_transport_cost >= self.min_transport_cost
        assert self.min_supply_cost >= 0 and self.max_supply_cost >= self.min_supply_cost
        assert self.min_supply_capacity > 0 and self.max_supply_capacity >= self.min_supply_capacity
        assert self.min_transport_time >= 0 and self.max_transport_time >= self.min_transport_time
        
        supply_opening_costs = np.random.randint(self.min_supply_cost, self.max_supply_cost + 1, self.n_supply_centers)
        transport_costs = np.random.randint(self.min_transport_cost, self.max_transport_cost + 1, (self.n_supply_centers, self.n_disaster_zones))
        transport_times = np.random.uniform(self.min_transport_time, self.max_transport_time, (self.n_supply_centers, self.n_disaster_zones))
        capacities = np.random.randint(self.min_supply_capacity, self.max_supply_capacity + 1, self.n_supply_centers)
        demand = np.random.randint(1, 50, self.n_disaster_zones)
        
        # Generate coverage data similar to FCMCNF problem
        coverage_costs = np.random.randint(1, self.coverage_max_cost + 1, size=self.n_supply_centers)
        coverage_pairs = [(i, j) for i in range(self.n_supply_centers) for j in range(self.n_disaster_zones)]
        chosen_pairs = np.random.choice(len(coverage_pairs), size=self.n_coverage_pairs, replace=False)
        coverage_set = [coverage_pairs[i] for i in chosen_pairs]
        
        return {
            "supply_opening_costs": supply_opening_costs,
            "transport_costs": transport_costs,
            "transport_times": transport_times,
            "capacities": capacities,
            "demand": demand,
            "coverage_costs": coverage_costs,
            "coverage_set": coverage_set,
        }
        
    ################# PySCIPOpt modeling #################
    def solve(self, instance):
        supply_opening_costs = instance['supply_opening_costs']
        transport_costs = instance['transport_costs']
        transport_times = instance['transport_times']
        capacities = instance['capacities']
        demand = instance['demand']
        coverage_costs = instance['coverage_costs']
        coverage_set = instance['coverage_set']
        
        model = Model("EmergencySupplyDistribution")
        n_supply_centers = len(supply_opening_costs)
        n_disaster_zones = len(demand)
        
        # Decision variables
        supply_open_vars = {s: model.addVar(vtype="B", name=f"Supply_{s}") for s in range(n_supply_centers)}
        supply_assignment_vars = {(s, z): model.addVar(vtype="I", lb=0, name=f"Supply_{s}_Zone_{z}") for s in range(n_supply_centers) for z in range(n_disaster_zones)}
        coverage_matched_vars = {(i, j): model.addVar(vtype="B", name=f"Matched_Coverage_{i}_{j}") for (i, j) in coverage_set}
        
        # Objective: minimize the total cost (supply center opening + transport costs + transport times for urgency)
        model.setObjective(
            quicksum(supply_opening_costs[s] * supply_open_vars[s] for s in range(n_supply_centers)) +
            quicksum(transport_costs[s, z] * supply_assignment_vars[s, z] for s in range(n_supply_centers) for z in range(n_disaster_zones)) +
            quicksum(transport_times[s, z] * supply_assignment_vars[s, z] for s in range(n_supply_centers) for z in range(n_disaster_zones)) +
            quicksum(coverage_costs[i] * coverage_matched_vars[(i, j)] for (i, j) in coverage_set),
            "minimize"
        )
        
        # Constraints: Each disaster zone's demand must be satisfied
        for z in range(n_disaster_zones):
            model.addCons(quicksum(supply_assignment_vars[s, z] for s in range(n_supply_centers)) >= demand[z], f"Zone_{z}_Demand")
        
        # Constraints: Supply center capacity constraints
        for s in range(n_supply_centers):
            model.addCons(quicksum(supply_assignment_vars[s, z] for z in range(n_disaster_zones)) <= capacities[s] * supply_open_vars[s], f"Supply_{s}_Capacity")
        
        # Constraints: Supplies must be transported from open supply centers
        for s in range(n_supply_centers):
            for z in range(n_disaster_zones):
                model.addCons(supply_assignment_vars[s, z] <= capacities[s] * supply_open_vars[s], f"Open_Supply_{s}_For_Zone_{z}")
        
        # Constraints: coverage constraints
        for (i, j) in coverage_set:
            model.addCons(coverage_matched_vars[(i, j)] + supply_open_vars[i] <= 1, f"Coverage_Pairing_{i}_{j}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time, model.getObjVal()
    
if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_supply_centers': 360,
        'n_disaster_zones': 45,
        'min_transport_cost': 112,
        'max_transport_cost': 750,
        'min_supply_cost': 3000,
        'max_supply_cost': 5000,
        'min_supply_capacity': 900,
        'max_supply_capacity': 5000,
        'min_transport_time': 0.24,
        'max_transport_time': 5.0,
        'coverage_max_cost': 15,
        'n_coverage_pairs': 50,
    }
    
    supply_distribution_optimizer = EmergencySupplyDistribution(parameters, seed=42)
    instance = supply_distribution_optimizer.generate_instance()
    solve_status, solve_time, objective_value = supply_distribution_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")