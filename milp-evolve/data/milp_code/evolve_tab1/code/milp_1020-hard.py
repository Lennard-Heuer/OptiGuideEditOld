import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class SimplifiedFacilityLocation:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_instance(self):
        assert self.n_facilities > 0 and self.n_neighborhoods >= self.n_facilities
        assert self.min_fixed_cost >= 0 and self.max_fixed_cost >= self.min_fixed_cost
        assert self.min_transport_cost >= 0 and self.max_transport_cost >= self.min_transport_cost
        assert self.min_capacity > 0 and self.max_capacity >= self.min_capacity
        
        fixed_costs = np.random.randint(self.min_fixed_cost, self.max_fixed_cost + 1, self.n_facilities)
        transport_costs = np.random.randint(self.min_transport_cost, self.max_transport_cost + 1, (self.n_facilities, self.n_neighborhoods))
        capacities = np.random.randint(self.min_capacity, self.max_capacity + 1, self.n_facilities)
        financial_rewards = np.random.uniform(10, 100, self.n_neighborhoods)
        energy_consumption = np.random.uniform(0.5, 2.0, self.n_facilities).tolist()
        labor_cost = np.random.uniform(10, 50, self.n_facilities).tolist()
        environmental_impact = np.random.normal(20, 5, self.n_facilities).tolist()
        
        return {
            "fixed_costs": fixed_costs,
            "transport_costs": transport_costs,
            "capacities": capacities,
            "financial_rewards": financial_rewards,
            "energy_consumption": energy_consumption,
            "labor_cost": labor_cost,
            "environmental_impact": environmental_impact,
        }

    def solve(self, instance):
        fixed_costs = instance['fixed_costs']
        transport_costs = instance['transport_costs']
        capacities = instance['capacities']
        financial_rewards = instance['financial_rewards']
        energy_consumption = instance['energy_consumption']
        labor_cost = instance['labor_cost']
        environmental_impact = instance['environmental_impact']

        model = Model("SimplifiedFacilityLocation")
        n_facilities = len(fixed_costs)
        n_neighborhoods = len(transport_costs[0])
        
        facility_vars = {f: model.addVar(vtype="B", name=f"Facility_{f}") for f in range(n_facilities)}
        allocation_vars = {(f, n): model.addVar(vtype="B", name=f"Facility_{f}_Neighborhood_{n}") for f in range(n_facilities) for n in range(n_neighborhoods)}
        energy_vars = {f: model.addVar(vtype="C", name=f"Energy_{f}", lb=0) for f in range(n_facilities)}
        labor_cost_vars = {f: model.addVar(vtype="C", name=f"LaborCost_{f}", lb=0) for f in range(n_facilities)}
        environmental_impact_vars = {f: model.addVar(vtype="C", name=f"EnvironmentalImpact_{f}", lb=0) for f in range(n_facilities)}

        model.setObjective(
            quicksum(financial_rewards[n] * allocation_vars[f, n] for f in range(n_facilities) for n in range(n_neighborhoods)) -
            quicksum(fixed_costs[f] * facility_vars[f] for f in range(n_facilities)) -
            quicksum(transport_costs[f][n] * allocation_vars[f, n] for f in range(n_facilities) for n in range(n_neighborhoods)) -
            quicksum(energy_vars[f] * energy_consumption[f] for f in range(n_facilities)) -
            quicksum(labor_cost_vars[f] * labor_cost[f] for f in range(n_facilities)) -
            quicksum(environmental_impact_vars[f] * environmental_impact[f] for f in range(n_facilities)),
            "maximize"
        )

        for n in range(n_neighborhoods):
            model.addCons(quicksum(allocation_vars[f, n] for f in range(n_facilities)) == 1, f"Neighborhood_{n}_Assignment")
        
        for f in range(n_facilities):
            for n in range(n_neighborhoods):
                model.addCons(allocation_vars[f, n] <= facility_vars[f], f"Facility_{f}_Service_{n}")
        
        for f in range(n_facilities):
            model.addCons(quicksum(allocation_vars[f, n] for n in range(n_neighborhoods)) <= capacities[f], f"Facility_{f}_Capacity")

        for f in range(n_facilities):
            model.addCons(energy_vars[f] == quicksum(allocation_vars[f, n] * energy_consumption[f] for n in range(n_neighborhoods)), f"EnergyConsumption_{f}")

        for f in range(n_facilities):
            model.addCons(labor_cost_vars[f] <= labor_cost[f], f"LaborCost_{f}")

        for f in range(n_facilities):
            model.addCons(environmental_impact_vars[f] <= environmental_impact[f], f"EnvironmentalImpact_{f}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_facilities': 19,
        'n_neighborhoods': 840,
        'min_fixed_cost': 1125,
        'max_fixed_cost': 1185,
        'min_transport_cost': 2187,
        'max_transport_cost': 2450,
        'min_capacity': 238,
        'max_capacity': 1771,
    }
    
    location_optimizer = SimplifiedFacilityLocation(parameters, seed=42)
    instance = location_optimizer.generate_instance()
    solve_status, solve_time, objective_value = location_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")