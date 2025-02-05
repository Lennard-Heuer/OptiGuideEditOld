import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class SCND:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_random_graph(self):
        G = nx.barabasi_albert_graph(n=self.n_nodes, m=self.ba_edges, seed=self.seed)
        capacities = np.random.uniform(self.cap_min, self.cap_max, size=(self.n_nodes, self.n_nodes))
        transport_costs = np.random.uniform(self.tc_min, self.tc_max, size=(self.n_nodes, self.n_nodes))
        return G, capacities, transport_costs

    def generate_demand(self):
        demands = np.random.uniform(self.demand_min, self.demand_max, size=self.n_nodes)
        return demands

    def generate_facilities(self):
        facilities = np.random.uniform(self.facility_min, self.facility_max, size=self.n_nodes)
        opening_costs = np.random.uniform(self.opening_cost_min, self.opening_cost_max, size=self.n_nodes)
        maintenance_costs = np.random.uniform(self.maintenance_cost_min, self.maintenance_cost_max, size=self.n_nodes)
        equipment_lifespans = np.random.randint(self.equipment_lifespan_min, self.equipment_lifespan_max, size=self.n_nodes)
        return facilities, opening_costs, maintenance_costs, equipment_lifespans

    def generate_environmental_impacts(self):
        environmental_costs = np.random.uniform(self.env_cost_min, self.env_cost_max, size=(self.n_nodes, self.n_nodes))
        return environmental_costs

    def generate_instance(self):
        self.n_nodes = np.random.randint(self.min_n_nodes, self.max_n_nodes+1)
        G, capacities, transport_costs = self.generate_random_graph()
        demands = self.generate_demand()
        facilities, opening_costs, maintenance_costs, equipment_lifespans = self.generate_facilities()
        environmental_costs = self.generate_environmental_impacts()

        res = {
            'graph': G,
            'capacities': capacities,
            'transport_costs': transport_costs,
            'demands': demands,
            'facilities': facilities,
            'opening_costs': opening_costs,
            'maintenance_costs': maintenance_costs,
            'equipment_lifespans': equipment_lifespans,
            'environmental_costs': environmental_costs
        }

        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        G = instance['graph']
        capacities = instance['capacities']
        transport_costs = instance['transport_costs']
        demands = instance['demands']
        facilities = instance['facilities']
        opening_costs = instance['opening_costs']
        maintenance_costs = instance['maintenance_costs']
        equipment_lifespans = instance['equipment_lifespans']
        environmental_costs = instance['environmental_costs']
        
        model = Model("SCND")
        Facility_Open = {i: model.addVar(vtype="B", name=f"Facility_Open_{i}") for i in range(self.n_nodes)}
        Allocation = {(i, j): model.addVar(vtype="C", name=f"Allocation_{i}_{j}") for i in range(self.n_nodes) for j in range(self.n_nodes)}
        Transport_Capacity = {(i, j): model.addVar(vtype="C", name=f"Transport_Capacity_{i}_{j}") for i in range(self.n_nodes) for j in range(self.n_nodes)}
        
        # Objective function
        objective_expr = quicksum(
            opening_costs[i] * Facility_Open[i]
            for i in range(self.n_nodes)
        ) + quicksum(
            Allocation[i, j] * transport_costs[i, j]
            for i in range(self.n_nodes) for j in range(self.n_nodes)
        ) + quicksum(
            environmental_costs[i, j] * Transport_Capacity[i, j]
            for i in range(self.n_nodes) for j in range(self.n_nodes)
        ) + quicksum(
            maintenance_costs[i] * Facility_Open[i]
            for i in range(self.n_nodes)
        )

        model.setObjective(objective_expr, "minimize")

        # Constraints
        for i in range(self.n_nodes):
            # Facility capacity constraint
            model.addCons(
                quicksum(Allocation[i, j] for j in range(self.n_nodes)) <= facilities[i] * Facility_Open[i],
                f"Facility_Capacity_{i}"
            )
            # Demand satisfaction constraint
            model.addCons(
                quicksum(Allocation[j, i] for j in range(self.n_nodes)) == demands[i],
                f"Demand_Satisfaction_{i}"
            )
            # Equipment lifespan constraint
            model.addCons(
                quicksum(Allocation[i, j] for j in range(self.n_nodes)) <= equipment_lifespans[i],
                f"Equipment_Lifespan_{i}"
            )

        for i in range(self.n_nodes):
            for j in range(self.n_nodes):
                # Transport capacity constraint
                model.addCons(
                    Allocation[i, j] <= capacities[i, j] * Transport_Capacity[i, j],
                    f"Transport_Capacity_{i}_{j}"
                )
                # Environmental impact constraint
                model.addCons(
                    environmental_costs[i, j] * Transport_Capacity[i, j] <= self.env_threshold,
                    f"Env_Impact_{i}_{j}"
                )
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time


if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_n_nodes': 80,
        'max_n_nodes': 450,
        'ba_edges': 45,
        'facility_min': 1200,
        'facility_max': 750,
        'opening_cost_min': 5000,
        'opening_cost_max': 20000,
        'cap_min': 783,
        'cap_max': 20,
        'tc_min': 10,
        'tc_max': 1250,
        'demand_min': 600,
        'demand_max': 15,
        'maintenance_cost_min': 175,
        'maintenance_cost_max': 25,
        'equipment_lifespan_min': 225,
        'equipment_lifespan_max': 1500,
        'env_cost_min': 20,
        'env_cost_max': 18,
        'env_threshold': 500,
    }

    scnd = SCND(parameters, seed=seed)
    instance = scnd.generate_instance()
    solve_status, solve_time = scnd.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")