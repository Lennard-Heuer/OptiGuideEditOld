import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class ComplexFacilityLocation:
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
        transport_costs = np.random.normal(self.mean_transport_cost, self.stddev_transport_cost, (self.n_facilities, self.n_neighborhoods)).astype(int)
        transport_costs = np.clip(transport_costs, self.min_transport_cost, self.max_transport_cost)
        capacities = np.random.randint(self.min_capacity, self.max_capacity + 1, self.n_facilities)

        financial_rewards = np.random.uniform(10, 100, self.n_neighborhoods)

        G = nx.erdos_renyi_graph(n=self.n_neighborhoods, p=self.route_prob, directed=True, seed=self.seed)
        for node in G.nodes:
            G.nodes[node]['households'] = np.random.randint(50, 500)
        for u, v in G.edges:
            G[u][v]['route_time'] = np.random.randint(5, 15)
            G[u][v]['route_capacity'] = np.random.randint(10, 30)
            G[u][v]['traffic_delay'] = np.random.uniform(1, self.traffic_delay_factor)
            G[u][v]['weather_sensitivity'] = np.random.uniform(0.5, 2.0)

        emergency_call_freq = np.random.randint(1, 5, self.n_neighborhoods)
        
        equipment_types = ['basic', 'intermediate', 'advanced']
        equipment_costs = {'basic': 500, 'intermediate': 1000, 'advanced': 2000}
        skills_levels = ['basic', 'intermediate', 'advanced']

        weather_conditions = {edge: np.random.choice([0, 1], p=[0.7, 0.3]) for edge in G.edges}  # 30% chance of bad weather

        # New instance data generation for additional constraints
        waste_gen_rate = np.random.uniform(self.min_waste_rate, self.max_waste_rate, self.n_facilities)
        water_usage = np.random.uniform(self.min_water_usage, self.max_water_usage, self.n_facilities)
        packaging_materials = np.random.choice(['recyclable', 'biodegradable', 'non-recyclable'], self.n_facilities, p=[0.4, 0.4, 0.2])
        geopolitical_risk = np.random.uniform(0.1, 0.9, self.n_neighborhoods)

        return {
            "fixed_costs": fixed_costs,
            "transport_costs": transport_costs,
            "capacities": capacities,
            "financial_rewards": financial_rewards,
            "G": G,
            "emergency_call_freq": emergency_call_freq,
            "equipment_types": equipment_types,
            "equipment_costs": equipment_costs,
            "skills_levels": skills_levels,
            "weather_conditions": weather_conditions,
            # New data
            "waste_gen_rate": waste_gen_rate,
            "water_usage": water_usage,
            "packaging_materials": packaging_materials,
            "geopolitical_risk": geopolitical_risk
        }

    def solve(self, instance):
        fixed_costs = instance['fixed_costs']
        transport_costs = instance['transport_costs']
        capacities = instance['capacities']
        financial_rewards = instance['financial_rewards']
        G = instance['G']
        emergency_call_freq = instance['emergency_call_freq']
        equipment_types = instance['equipment_types']
        equipment_costs = instance['equipment_costs']
        skills_levels = instance['skills_levels']
        weather_conditions = instance['weather_conditions']
        waste_gen_rate = instance['waste_gen_rate']
        water_usage = instance['water_usage']
        packaging_materials = instance['packaging_materials']
        geopolitical_risk = instance['geopolitical_risk']

        model = Model("ComplexFacilityLocation")
        n_facilities = len(fixed_costs)
        n_neighborhoods = len(transport_costs[0])

        # Decision variables
        facility_vars = {f: model.addVar(vtype="B", name=f"Facility_{f}") for f in range(n_facilities)}
        allocation_vars = {(f, n): model.addVar(vtype="B", name=f"Facility_{f}_Neighborhood_{n}") for f in range(n_facilities) for n in range(n_neighborhoods)}
        route_vars = {(u, v): model.addVar(vtype="C", name=f"Flow_{u}_{v}") for u, v in G.edges}
        energy_vars = {f: model.addVar(vtype="C", name=f"Energy_{f}") for f in range(n_facilities)}
        equipment_allocation_vars = {(f, e): model.addVar(vtype="B", name=f"Facility_{f}_Equipment_{e}") for f in range(n_facilities) for e in equipment_types}
        skill_allocation_vars = {(f, s): model.addVar(vtype="B", name=f"Facility_{f}_Skill_{s}") for f in range(n_facilities) for s in skills_levels}

        # New decision variables
        waste_vars = {f: model.addVar(vtype="C", name=f"Waste_{f}") for f in range(n_facilities)}
        water_vars = {f: model.addVar(vtype="C", name=f"Water_{f}") for f in range(n_facilities)}

        # Energy Consumption Constraints
        for f in range(n_facilities):
            model.addCons(energy_vars[f] == quicksum(allocation_vars[f, n] * self.energy_per_neighborhood for n in range(n_neighborhoods)), f"EnergyConsumption_{f}")

        # Optimize response time by factoring in traffic delay and emergency call frequency
        route_time_adjusted = {(u, v): G[u][v]['route_time'] * G[u][v]['traffic_delay'] * self.peak_hour_multiplier if emergency_call_freq[v] > 2 else G[u][v]['route_time'] * G[u][v]['traffic_delay'] for u, v in G.edges}
        
        # Incorporate weather conditions
        for u, v in G.edges:
            route_time_adjusted[u, v] *= (1 + G[u][v]['weather_sensitivity'] * weather_conditions[(u, v)])
            G[u][v]['route_capacity'] *= (1 - 0.5 * weather_conditions[(u, v)])

        # New Constraints
        # Constraints to ensure sustainable packaging
        for f in range(n_facilities):
            if packaging_materials[f] == 'non-recyclable':
                model.addCons(facility_vars[f] == 0, f"Facility_No_NonRecyclable_{f}")

        # Constraints to limit water usage and waste generation
        for f in range(n_facilities):
            model.addCons(water_vars[f] <= water_usage[f], f"WaterUsage_{f}")
            model.addCons(waste_vars[f] <= waste_gen_rate[f], f"WasteGeneration_{f}")

        # Constraints to account for geopolitical risk in supply chain
        for n in range(n_neighborhoods):
            model.addCons(quicksum(allocation_vars[f, n] for f in range(n_facilities)) >= (1 - geopolitical_risk[n]), f"GeopoliticalRisk_{n}")

        # Modify objective to include new elements
        model.setObjective(
            quicksum(financial_rewards[n] * allocation_vars[f, n] for f in range(n_facilities) for n in range(n_neighborhoods)) -
            quicksum(fixed_costs[f] * facility_vars[f] for f in range(n_facilities)) -
            quicksum(transport_costs[f][n] * allocation_vars[f, n] for f in range(n_facilities) for n in range(n_neighborhoods)) -
            quicksum(route_time_adjusted[u, v] * route_vars[u, v] for u, v in G.edges) -
            quicksum(energy_vars[f] * self.energy_cost for f in range(n_facilities)) -
            quicksum(equipment_costs[e] * equipment_allocation_vars[f, e] for f in range(n_facilities) for e in equipment_types) -
            quicksum(water_vars[f] * self.water_cost for f in range(n_facilities)) -
            quicksum(waste_vars[f] * self.waste_disposal_cost for f in range(n_facilities)),
            "maximize"
        )

        # Constraints: Each neighborhood is served by exactly one facility
        for n in range(n_neighborhoods):
            model.addCons(quicksum(allocation_vars[f, n] for f in range(n_facilities)) == 1, f"Neighborhood_{n}_Assignment")

        # Constraints: Only open facilities can serve neighborhoods
        for f in range(n_facilities):
            for n in range(n_neighborhoods):
                model.addCons(allocation_vars[f, n] <= facility_vars[f], f"Facility_{f}_Service_{n}")

        # Constraints: Facilities cannot exceed their capacity
        for f in range(n_facilities):
            model.addCons(quicksum(allocation_vars[f, n] for n in range(n_neighborhoods)) <= capacities[f], f"Facility_{f}_Capacity")

        # Constraints: Minimum service level for facilities - Factoring in emergency call frequency
        for f in range(n_facilities):
            model.addCons(quicksum(allocation_vars[f, n] for n in range(n_neighborhoods)) >= self.min_service_level * facility_vars[f] * emergency_call_freq.mean(), f"Facility_{f}_MinService")

        # Route and flow constraints
        for u, v in G.edges:
            model.addCons(route_vars[u, v] <= G[u][v]['route_capacity'], f"RouteCapacity_{u}_{v}")

        # Flow conservation constraints
        for node in G.nodes:
            model.addCons(
                quicksum(route_vars[u, node] for u in G.predecessors(node)) ==
                quicksum(route_vars[node, v] for v in G.successors(node)),
                f"FlowConservation_{node}"
            )
        
        # Budget constraint
        total_operational_cost = quicksum(fixed_costs[f] * facility_vars[f] for f in range(n_facilities)) + quicksum(equipment_costs[e] * equipment_allocation_vars[f, e] for f in range(n_facilities) for e in equipment_types)
        model.addCons(total_operational_cost <= self.max_operational_cost, "BudgetConstraint")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_facilities': 81,
        'n_neighborhoods': 314,
        'min_fixed_cost': 210,
        'max_fixed_cost': 1970,
        'mean_transport_cost': 390,
        'stddev_transport_cost': 1265,
        'min_transport_cost': 1138,
        'max_transport_cost': 2844,
        'min_capacity': 522,
        'max_capacity': 2024,
        'min_service_level': 0.56,
        'route_prob': 0.72,
        'energy_per_neighborhood': 2250,
        'energy_cost': 0.24,
        'traffic_delay_factor': 540.0,
        'peak_hour_multiplier': 72.0,
        'max_operational_cost': 100000,
        'min_waste_rate': 0.45,
        'max_waste_rate': 6.0,
        'min_water_usage': 2000,
        'max_water_usage': 10000,
        'waste_disposal_cost': 9.0,
        'water_cost': 0.77,
    }

    # Define new weather-related parameters
    parameters.update({
        'weather_disruption_prob': 0.3  # Probability that a route is disrupted by weather
    })

    location_optimizer = ComplexFacilityLocation(parameters, seed=42)
    instance = location_optimizer.generate_instance()
    solve_status, solve_time, objective_value = location_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")