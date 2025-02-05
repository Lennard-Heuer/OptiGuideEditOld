import random
import time
import numpy as np
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
        
        contagion_levels = np.random.uniform(0, 1, self.n_disaster_zones)
        vulnerability_index = np.random.uniform(0, 1, self.n_disaster_zones)
        disruptions = np.random.binomial(1, 0.1, self.n_supply_centers)
        
        # Determining the Big M values by an upper limit
        M = np.max(capacities)
        return {
            "supply_opening_costs": supply_opening_costs,
            "transport_costs": transport_costs,
            "transport_times": transport_times,
            "capacities": capacities,
            "demand": demand,
            "contagion_levels": contagion_levels,
            "vulnerability_index": vulnerability_index,
            "disruptions": disruptions,
            "M": M
        }

    ################# PySCIPOpt modeling #################
    def solve(self, instance):
        supply_opening_costs = instance['supply_opening_costs']
        transport_costs = instance['transport_costs']
        transport_times = instance['transport_times']
        capacities = instance['capacities']
        demand = instance['demand']
        contagion_levels = instance['contagion_levels']
        vulnerability_index = instance['vulnerability_index']
        disruptions = instance['disruptions']
        M = instance['M']
        
        model = Model("EmergencySupplyDistribution")
        n_supply_centers = len(supply_opening_costs)
        n_disaster_zones = len(demand)
        
        # Decision variables
        supply_open_vars = {s: model.addVar(vtype="B", name=f"Supply_{s}") for s in range(n_supply_centers)}
        supply_assignment_vars = {(s, z): model.addVar(vtype="I", lb=0, name=f"Supply_{s}_Zone_{z}") for s in range(n_supply_centers) for z in range(n_disaster_zones)}
        disruption_vars = {s: model.addVar(vtype="B", name=f"Disruption_{s}") for s in range(n_supply_centers)}

        # Objective: minimize the total cost with adjusted priorities and penalties
        model.setObjective(
            quicksum(supply_opening_costs[s] * supply_open_vars[s] for s in range(n_supply_centers)) +
            quicksum(transport_costs[s, z] * supply_assignment_vars[s, z] * (1 + contagion_levels[z]) * (1 + vulnerability_index[z]) for s in range(n_supply_centers) for z in range(n_disaster_zones)) +
            quicksum(transport_times[s, z] * supply_assignment_vars[s, z] for s in range(n_supply_centers) for z in range(n_disaster_zones)) +
            quicksum(1000 * disruption_vars[s] for s in range(n_supply_centers) if disruptions[s]),
            "minimize"
        )
        
        # Constraints: Each disaster zone's demand must be satisfied
        for z in range(n_disaster_zones):
            model.addCons(quicksum(supply_assignment_vars[s, z] for s in range(n_supply_centers)) >= demand[z], f"Zone_{z}_Demand")
        
        # Constraints: Supply center capacity constraints
        for s in range(n_supply_centers):
            model.addCons(quicksum(supply_assignment_vars[s, z] for z in range(n_disaster_zones)) <= capacities[s], f"Supply_{s}_Capacity")
        
        # Constraints: Supplies must be transported from open supply centers - Using Big M Formulation
        for s in range(n_supply_centers):
            for z in range(n_disaster_zones):
                model.addCons(supply_assignment_vars[s, z] <= M * supply_open_vars[s], f"BigM_Open_Supply_{s}_For_Zone_{z}")
        
        # Constraints: Handle potential disruptions
        for s in range(n_supply_centers):
            if disruptions[s]:
                model.addCons(supply_open_vars[s] <= disruption_vars[s], f"Disruption_{s}")

        # Time-sensitive delivery constraints (penalizing late deliveries)
        for s in range(n_supply_centers):
            for z in range(n_disaster_zones):
                max_acceptable_time = 12.0
                over_time_penalty = 10.0
                if transport_times[s, z] > max_acceptable_time:
                    model.addCons(supply_assignment_vars[s, z] * over_time_penalty <= M * (1 - supply_open_vars[s]), f"TimePenalty_{s}_Zone_{z}")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time, model.getObjVal()
    
if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_supply_centers': 135,
        'n_disaster_zones': 315,
        'min_transport_cost': 900,
        'max_transport_cost': 1000,
        'min_supply_cost': 3000,
        'max_supply_cost': 5000,
        'min_supply_capacity': 200,
        'max_supply_capacity': 5000,
        'min_transport_time': 0.38,
        'max_transport_time': 100.0,
    }
    supply_distribution_optimizer = EmergencySupplyDistribution(parameters, seed=42)
    instance = supply_distribution_optimizer.generate_instance()
    solve_status, solve_time, objective_value = supply_distribution_optimizer.solve(instance)
    
    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")