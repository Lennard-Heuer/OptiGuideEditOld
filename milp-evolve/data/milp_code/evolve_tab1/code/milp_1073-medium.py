import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class SupplyChainOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_instance(self):
        assert self.n_factories > 0 and self.n_demand_points > 0
        assert self.min_cost_factory >= 0 and self.max_cost_factory >= self.min_cost_factory
        assert self.min_cost_transport >= 0 and self.max_cost_transport >= self.min_cost_transport
        assert self.min_capacity_factory > 0 and self.max_capacity_factory >= self.min_capacity_factory
        assert self.min_demand >= 0 and self.max_demand >= self.min_demand
        assert self.min_cost_transship >= 0 and self.max_cost_transship >= self.min_cost_transship

        fixed_costs = np.random.randint(self.min_cost_factory, self.max_cost_factory + 1, self.n_factories)
        transport_costs = np.random.randint(self.min_cost_transport, self.max_cost_transport + 1, (self.n_factories, self.n_demand_points))
        capacities = np.random.randint(self.min_capacity_factory, self.max_capacity_factory + 1, self.n_factories)
        demands = np.random.randint(self.min_demand, self.max_demand + 1, (self.n_periods, self.n_demand_points))
        penalty_costs = np.random.uniform(10, 50, (self.n_periods, self.n_demand_points)).tolist()
        transship_costs = np.random.randint(self.min_cost_transship, self.max_cost_transship + 1, (self.n_factories, self.n_factories))
        holding_costs = np.random.uniform(1, 10, self.n_factories).tolist()
        backlog_costs = np.random.uniform(20, 60, (self.n_periods, self.n_demand_points)).tolist()

        return {
            "fixed_costs": fixed_costs,
            "transport_costs": transport_costs,
            "capacities": capacities,
            "demands": demands,
            "penalty_costs": penalty_costs,
            "transship_costs": transship_costs,
            "holding_costs": holding_costs,
            "backlog_costs": backlog_costs,
        }

    def solve(self, instance):
        fixed_costs = instance['fixed_costs']
        transport_costs = instance['transport_costs']
        capacities = instance['capacities']
        demands = instance['demands']
        penalty_costs = instance['penalty_costs']
        transship_costs = instance['transship_costs']
        holding_costs = instance['holding_costs']
        backlog_costs = instance['backlog_costs']
        
        model = Model("SupplyChainOptimization")
        n_factories = len(fixed_costs)
        n_demand_points = len(transport_costs[0])
        n_periods = len(demands)
        
        factory_vars = {(f, t): model.addVar(vtype="B", name=f"Factory_{f}_Period_{t}") for f in range(n_factories) for t in range(n_periods)}
        transport_vars = {(f, d, t): model.addVar(vtype="C", name=f"Transport_{f}_Demand_{d}_Period_{t}") for f in range(n_factories) for d in range(n_demand_points) for t in range(n_periods)}
        unmet_demand_vars = {(d, t): model.addVar(vtype="C", name=f"Unmet_Demand_{d}_Period_{t}") for d in range(n_demand_points) for t in range(n_periods)}
        backlog_vars = {(d, t): model.addVar(vtype="C", name=f"Backlog_Demand_{d}_Period_{t}") for d in range(n_demand_points) for t in range(n_periods)}
        inventory_vars = {(f, t): model.addVar(vtype="C", name=f"Inventory_{f}_Period_{t}") for f in range(n_factories) for t in range(n_periods)}
        transship_vars = {(i, j, t): model.addVar(vtype="C", name=f"Transship_{i}_to_{j}_Period_{t}") for i in range(n_factories) for j in range(n_factories) if i != j for t in range(n_periods)}

        # Objective function: Minimize total cost (fixed + transport + penalty for unmet demand + holding + backlog + transshipment)
        model.setObjective(
            quicksum(fixed_costs[f] * factory_vars[f, t] for f in range(n_factories) for t in range(n_periods)) +
            quicksum(transport_costs[f][d] * transport_vars[f, d, t] for f in range(n_factories) for d in range(n_demand_points) for t in range(n_periods)) +
            quicksum(penalty_costs[t][d] * unmet_demand_vars[d, t] for d in range(n_demand_points) for t in range(n_periods)) +
            quicksum(holding_costs[f] * inventory_vars[f, t] for f in range(n_factories) for t in range(n_periods)) +
            quicksum(backlog_costs[t][d] * backlog_vars[d, t] for d in range(n_demand_points) for t in range(n_periods)) +
            quicksum(transship_costs[i][j] * transship_vars[i, j, t] for i in range(n_factories) for j in range(n_factories) if i != j for t in range(n_periods)),
            "minimize"
        )

        # Constraints

        # Demand satisfaction (supplies, unmet demand, and backlog must cover total demand each period)
        for d in range(n_demand_points):
            for t in range(n_periods):
                model.addCons(
                    quicksum(transport_vars[f, d, t] for f in range(n_factories)) + 
                    unmet_demand_vars[d, t] + backlog_vars[d, t] == demands[t][d], 
                    f"Demand_Satisfaction_{d}_Period_{t}"
                )

        # Capacity limits for each factory each period
        for f in range(n_factories):
            for t in range(n_periods):
                model.addCons(
                    quicksum(transport_vars[f, d, t] for d in range(n_demand_points)) + 
                    quicksum(transship_vars[f, j, t] for j in range(n_factories) if j != f) <= 
                    capacities[f] * factory_vars[f, t], 
                    f"Factory_Capacity_{f}_Period_{t}"
                )
        
        # Transportation only if factory is operational each period
        for f in range(n_factories):
            for d in range(n_demand_points):
                for t in range(n_periods):
                    model.addCons(
                        transport_vars[f, d, t] <= demands[t][d] * factory_vars[f, t], 
                        f"Operational_Constraint_{f}_{d}_Period_{t}"
                    )
        
        # Inventory balance constraints each period
        for f in range(n_factories):
            for t in range(1, n_periods):
                model.addCons(
                    inventory_vars[f, t] == 
                    inventory_vars[f, t-1] + 
                    quicksum(transport_vars[f, d, t-1] for d in range(n_demand_points)) - 
                    quicksum(transport_vars[f, d, t] for d in range(n_demand_points)) + 
                    quicksum(transship_vars[i, f, t-1] for i in range(n_factories) if i != f) - 
                    quicksum(transship_vars[f, j, t] for j in range(n_factories) if j != f), 
                    f"Inventory_Balance_{f}_Period_{t}"
                )
        
        # Initial inventory is zero
        for f in range(n_factories):
            model.addCons(inventory_vars[f, 0] == 0, f"Initial_Inventory_{f}")
        
        # Unmet demand and backlog balance each period
        for d in range(n_demand_points):
            for t in range(1, n_periods):
                model.addCons(
                    backlog_vars[d, t] == 
                    unmet_demand_vars[d, t-1], 
                    f"Backlog_Balance_{d}_Period_{t}"
                )

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()
    
if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_factories': 10,
        'n_demand_points': 3,
        'n_periods': 60,
        'min_cost_factory': 3000,
        'max_cost_factory': 5000,
        'min_cost_transport': 22,
        'max_cost_transport': 150,
        'min_cost_transship': 60,
        'max_cost_transship': 150,
        'min_capacity_factory': 140,
        'max_capacity_factory': 500,
        'min_demand': 50,
        'max_demand': 1600,
    }

    supply_chain_optimizer = SupplyChainOptimization(parameters, seed=42)
    instance = supply_chain_optimizer.generate_instance()
    solve_status, solve_time, objective_value = supply_chain_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")