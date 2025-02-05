import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class EVChargingStationOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        if seed:
            random.seed(seed)
            np.random.seed(seed)
    
    # Data Generation
    def randint(self, size, interval):
        return np.random.randint(interval[0], interval[1], size)
    
    def unit_transportation_costs(self):
        return np.random.rand(self.n_customers, self.n_stations) * self.transport_cost_scale

    def renewable_energy_supply(self):
        return np.random.rand(self.n_renewables) * self.renewable_capacity_scale

    def generate_instance(self):
        demands = self.randint(self.n_customers, self.demand_interval)
        station_capacities = self.randint(self.n_stations, self.station_capacity_interval)
        renewable_capacities = self.renewable_energy_supply()
        fixed_costs = self.randint(self.n_stations, self.fixed_cost_interval)
        transport_costs = self.unit_transportation_costs()

        res = {
            'demands': demands,
            'station_capacities': station_capacities,
            'renewable_capacities': renewable_capacities,
            'fixed_costs': fixed_costs,
            'transport_costs': transport_costs
        }
        # New instance data
        item_weights = self.randint(self.number_of_items, (1, 10))
        item_profits = self.randint(self.number_of_items, (10, 100))
        knapsack_capacities = self.randint(self.number_of_knapsacks, (30, 100))
        
        res.update({
            'item_weights': item_weights,
            'item_profits': item_profits,
            'knapsack_capacities': knapsack_capacities
        })
        return res

    # MILP Solver
    def solve(self, instance):
        demands = instance['demands']
        station_capacities = instance['station_capacities']
        renewable_capacities = instance['renewable_capacities']
        fixed_costs = instance['fixed_costs']
        transport_costs = instance['transport_costs']
        item_weights = instance['item_weights']
        item_profits = instance['item_profits']
        knapsack_capacities = instance['knapsack_capacities']
        
        n_customers = len(demands)
        n_stations = len(station_capacities)
        n_renewables = len(renewable_capacities)
        number_of_items = len(item_weights)
        number_of_knapsacks = len(knapsack_capacities)
        
        model = Model("EVChargingStationOptimization")
        
        # Decision variables
        open_stations = {j: model.addVar(vtype="B", name=f"Open_{j}") for j in range(n_stations)}
        flow = {(i, j): model.addVar(vtype="C", name=f"Flow_{i}_{j}") for i in range(n_customers) for j in range(n_stations)}
        renewable_supply = {j: model.addVar(vtype="C", name=f"RenewableSupply_{j}") for j in range(n_renewables)}
        knapsack_vars = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in range(number_of_items) for j in range(number_of_knapsacks)}

        # Objective: minimize the total cost
        objective_expr = quicksum(fixed_costs[j] * open_stations[j] for j in range(n_stations)) + \
                         quicksum(transport_costs[i, j] * flow[i, j] for i in range(n_customers) for j in range(n_stations))
        
        # Demand satisfaction constraints
        for i in range(n_customers):
            model.addCons(quicksum(flow[i, j] for j in range(n_stations)) == demands[i], f"Demand_{i}")
        
        # Station capacity constraints
        for j in range(n_stations):
            model.addCons(quicksum(flow[i, j] for i in range(n_customers)) <= station_capacities[j] * open_stations[j], f"StationCapacity_{j}")
        
        # Renewable supply constraints
        for k in range(n_renewables):
            model.addCons(renewable_supply[k] <= renewable_capacities[k], f"RenewableCapacity_{k}")

        # Linking renewable supply to station energy inflow
        for j in range(n_stations):
            model.addCons(quicksum(renewable_supply[k] for k in range(n_renewables)) >= quicksum(flow[i, j] for i in range(n_customers)) * open_stations[j], f"RenewableSupplyLink_{j}")

        # New MKP Constraints
        # Objective part related to knapsacks
        objective_expr += quicksum(item_profits[i] * knapsack_vars[(i, j)] for i in range(number_of_items) for j in range(number_of_knapsacks))

        # Items in at most one knapsack
        for i in range(number_of_items):
            model.addCons(quicksum(knapsack_vars[(i, j)] for j in range(number_of_knapsacks)) <= 1, f"ItemAssignment_{i}")

        # Knapsack capacity constraints
        for j in range(number_of_knapsacks):
            model.addCons(quicksum(item_weights[i] * knapsack_vars[(i, j)] for i in range(number_of_items)) <= knapsack_capacities[j], f"KnapsackCapacity_{j}")

        # Logical conditions added to enhance complexity
        # Logical Condition 1: Specific items or demand pattern relation
        specific_customer_A, specific_customer_B = 0, 1
        model.addCons(flow[specific_customer_A, j] * open_stations[j] <= flow[specific_customer_B, j] * open_stations[j], "LogicalCondition_1")

        # Logical Condition 2: Linking stations and knapsacks, assume some logical condition
        related_station_and_knapsack = {0: 4, 1: 5} # Example mapping
        for s, k in related_station_and_knapsack.items():
            for i in range(n_customers):
                model.addCons(flow[i, s] * open_stations[s] == knapsack_vars[(i, k)], f"LogicalCondition_2_{i}_{s}")

        model.setObjective(objective_expr, "minimize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_customers': 100,
        'n_stations': 337,
        'n_renewables': 250,
        'demand_interval': (280, 1400),
        'station_capacity_interval': (700, 2800),
        'renewable_capacity_scale': 1000.0,
        'fixed_cost_interval': (525, 2100),
        'transport_cost_scale': 1620.0,
        'number_of_items': 100,
        'number_of_knapsacks': 10,
    }
    
    ev_charging_optimization = EVChargingStationOptimization(parameters, seed=seed)
    instance = ev_charging_optimization.generate_instance()
    solve_status, solve_time = ev_charging_optimization.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")