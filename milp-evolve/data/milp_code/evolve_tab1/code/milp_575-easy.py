import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class DataCenterPlacementOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_instance(self):
        num_data_centers = random.randint(self.min_data_centers, self.max_data_centers)
        num_nodes = random.randint(self.min_nodes, self.max_nodes)

        # Cost matrices
        node_connection_costs = np.random.randint(50, 300, size=(num_nodes, num_data_centers))
        operational_costs = np.random.randint(1000, 5000, size=num_data_centers)

        # Node demands
        nodal_demand = np.random.randint(100, 500, size=num_nodes)

        # MegaServer capacity
        mega_server_capacity = np.random.randint(1000, 5000, size=num_data_centers)

        ### New Data: ReliabilityCosts ###
        reliability_costs = np.random.rand(num_nodes, num_data_centers) * 50  # Random reliability costs

        res = {
            'num_data_centers': num_data_centers,
            'num_nodes': num_nodes,
            'node_connection_costs': node_connection_costs,
            'operational_costs': operational_costs,
            'nodal_demand': nodal_demand,
            'mega_server_capacity': mega_server_capacity,
            'reliability_costs': reliability_costs,
        }
        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        num_data_centers = instance['num_data_centers']
        num_nodes = instance['num_nodes']
        node_connection_costs = instance['node_connection_costs']
        operational_costs = instance['operational_costs']
        nodal_demand = instance['nodal_demand']
        mega_server_capacity = instance['mega_server_capacity']
        reliability_costs = instance['reliability_costs']

        model = Model("DataCenterPlacementOptimization")

        # Variables
        mega_server = {i: model.addVar(vtype="B", name=f"mega_server_{i}") for i in range(num_data_centers)}
        node_connection = {}
        for i in range(num_nodes):
            for j in range(num_data_centers):
                node_connection[i, j] = model.addVar(vtype="B", name=f"node_connection_{i}_{j}")

        # New variables: Connection reliability
        connection_reliability = {i: model.addVar(vtype="C", name=f"connection_reliability_{i}") for i in range(num_nodes)}

        # Objective function: Minimize total cost and maximize reliability
        total_cost = quicksum(node_connection[i, j] * (node_connection_costs[i, j] + reliability_costs[i, j]) for i in range(num_nodes) for j in range(num_data_centers)) + \
                     quicksum(mega_server[j] * operational_costs[j] for j in range(num_data_centers))

        model.setObjective(total_cost, "minimize")

        # Constraints
        for i in range(num_nodes):
            model.addCons(quicksum(node_connection[i, j] for j in range(num_data_centers)) == 1, name=f"node_connection_{i}")

        # Logical constraints: A data center can only connect nodes if it has a mega server
        for j in range(num_data_centers):
            for i in range(num_nodes):
                model.addCons(node_connection[i, j] <= mega_server[j], name=f"data_center_node_{i}_{j}")

        # Connection reliability and capacity constraints
        for j in range(num_data_centers):
            model.addCons(quicksum(node_connection[i, j] * nodal_demand[i] for i in range(num_nodes)) <= mega_server_capacity[j], name=f"mega_server_capacity_{j}")
            for i in range(num_nodes):
                model.addCons(connection_reliability[i] >= 1 - reliability_costs[i, j] * node_connection[i, j], name=f"connection_reliability_{i}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_data_centers': 10,
        'max_data_centers': 300,
        'min_nodes': 50,
        'max_nodes': 600,
    }

    optimization = DataCenterPlacementOptimization(parameters, seed=seed)
    instance = optimization.generate_instance()
    solve_status, solve_time = optimization.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")