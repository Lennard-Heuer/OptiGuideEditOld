import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class AdvancedSupplyChainNetwork:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# data generation #################
    def generate_instance(self):
        def choose_next_item(bundle_mask, interests, compats):
            n_items = len(interests)
            prob = (1 - bundle_mask) * interests * compats[bundle_mask, :].mean(axis=0)
            prob /= prob.sum()
            return np.random.choice(n_items, p=prob)
        
        values = self.min_value + (self.max_value - self.min_value) * np.random.rand(self.n_items)
        compats = np.triu(np.random.rand(self.n_items, self.n_items), k=1)
        compats = compats + compats.transpose()
        compats = compats / compats.sum(1)

        bids = []
        n_dummy_items = 0

        while len(bids) < self.n_bids:
            private_interests = np.random.rand(self.n_items)
            private_values = values + self.max_value * self.value_deviation * (2 * private_interests - 1)

            bidder_bids = {}

            prob = private_interests / private_interests.sum()
            item = np.random.choice(self.n_items, p=prob)
            bundle_mask = np.full(self.n_items, 0)
            bundle_mask[item] = 1

            while np.random.rand() < self.add_item_prob:
                if bundle_mask.sum() == self.n_items:
                    break
                item = choose_next_item(bundle_mask, private_interests, compats)
                bundle_mask[item] = 1

            bundle = np.nonzero(bundle_mask)[0]
            price = private_values[bundle].sum() + np.power(len(bundle), 1 + self.additivity)

            if price < 0:
                continue

            bidder_bids[frozenset(bundle)] = price

            sub_candidates = []
            for item in bundle:
                bundle_mask = np.full(self.n_items, 0)
                bundle_mask[item] = 1

                while bundle_mask.sum() < len(bundle):
                    item = choose_next_item(bundle_mask, private_interests, compats)
                    bundle_mask[item] = 1

                sub_bundle = np.nonzero(bundle_mask)[0]
                sub_price = private_values[sub_bundle].sum() + np.power(len(sub_bundle), 1 + self.additivity)
                sub_candidates.append((sub_bundle, sub_price))

            budget = self.budget_factor * price
            min_resale_value = self.resale_factor * values[bundle].sum()
            for bundle, price in [
                sub_candidates[i] for i in np.argsort([-price for bundle, price in sub_candidates])]:

                if len(bidder_bids) >= self.max_n_sub_bids + 1 or len(bids) + len(bidder_bids) >= self.n_bids:
                    break

                if price < 0 or price > budget:
                    continue

                if values[bundle].sum() < min_resale_value:
                    continue

                if frozenset(bundle) in bidder_bids:
                    continue

                bidder_bids[frozenset(bundle)] = price

            if len(bidder_bids) > 2:
                dummy_item = [self.n_items + n_dummy_items]
                n_dummy_items += 1
            else:
                dummy_item = []

            for bundle, price in bidder_bids.items():
                bids.append((list(bundle) + dummy_item, price))

        bids_per_item = [[] for item in range(self.n_items + n_dummy_items)]
        for i, bid in enumerate(bids):
            bundle, price = bid
            for item in bundle:
                bids_per_item[item].append(i)

        mutual_exclusivity_pairs = []
        for _ in range(self.n_exclusive_pairs):
            bid1 = random.randint(0, len(bids) - 1)
            bid2 = random.randint(0, len(bids) - 1)
            if bid1 != bid2:
                mutual_exclusivity_pairs.append((bid1, bid2))

        n_facilities = np.random.randint(self.facility_min_count, self.facility_max_count)
        operating_cost = np.random.randint(5, 20, size=n_facilities).tolist()
        assignment_cost = np.random.randint(1, 10, size=len(bids)).tolist()
        capacity = np.random.randint(5, 50, size=n_facilities).tolist()

        high_priority_bids = random.sample(range(len(bids)), len(bids) // 3)
        patrol_fees = np.random.randint(500, 5000, size=n_facilities).tolist()
        patrol_times = {i: np.random.randint(1, 10, size=n_facilities).tolist() for i in high_priority_bids}

        # New Data: Inventory levels, emission factors, and sustainable packaging
        initial_inventory = np.random.randint(1, 100, size=n_facilities)
        emission_factors = np.random.uniform(0.1, 1.5, size=(len(bids), n_facilities))
        sustainable_packaging = np.random.rand(len(bids), self.n_items)

        return {
            "bids": bids,
            "bids_per_item": bids_per_item,
            "mutual_exclusivity_pairs": mutual_exclusivity_pairs,
            "n_facilities": n_facilities,
            "operating_cost": operating_cost,
            "assignment_cost": assignment_cost,
            "capacity": capacity,
            "high_priority_bids": high_priority_bids,
            "patrol_fees": patrol_fees,
            "patrol_times": patrol_times,
            # New Entries
            "initial_inventory": initial_inventory,
            "emission_factors": emission_factors,
            "sustainable_packaging": sustainable_packaging,
        }

    ################# PySCIPOpt modeling #################
    def solve(self, instance):
        bids = instance['bids']
        bids_per_item = instance['bids_per_item']
        mutual_exclusivity_pairs = instance['mutual_exclusivity_pairs']
        n_facilities = instance['n_facilities']
        operating_cost = instance['operating_cost']
        assignment_cost = instance['assignment_cost']
        capacity = instance['capacity']
        high_priority_bids = instance['high_priority_bids']
        patrol_fees = instance['patrol_fees']
        patrol_times = instance['patrol_times']
        initial_inventory = instance['initial_inventory']
        emission_factors = instance['emission_factors']
        sustainable_packaging = instance['sustainable_packaging']

        model = Model("AdvancedSupplyChainNetwork")

        bid_vars = {i: model.addVar(vtype="B", name=f"Bid_{i}") for i in range(len(bids))}
        y_vars = {j: model.addVar(vtype="B", name=f"y_{j}") for j in range(n_facilities)}
        x_vars = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in range(len(bids)) for j in range(n_facilities)}
        patrol_vars = {(i, j): model.addVar(vtype="B", name=f"patrol_{i}_{j}") for i in high_priority_bids for j in range(n_facilities)}

        ### New Variables
        inv_vars = {j: model.addVar(vtype="I", lb=0, name=f"Inv_{j}") for j in range(n_facilities)}
        emission_vars = {i: model.addVar(vtype="C", lb=0, name=f"Emission_{i}") for i in range(len(bids))}
        waste_vars = {j: model.addVar(vtype="C", lb=0, name=f"Waste_{j}") for j in range(n_facilities)}

        # Enhanced Objective Function
        objective_expr = quicksum(price * bid_vars[i] for i, (bundle, price) in enumerate(bids)) \
                         - quicksum(operating_cost[j] * y_vars[j] for j in range(n_facilities)) \
                         - quicksum(assignment_cost[i] * quicksum(x_vars[i, j] for j in range(n_facilities)) for i in range(len(bids))) \
                         - quicksum(patrol_fees[j] * y_vars[j] for j in range(n_facilities)) \
                         - quicksum(emission_vars[i] * emission_factors[i, j] for i in range(len(bids)) for j in range(n_facilities)) \
                         - quicksum(waste_vars[j] for j in range(n_facilities))

        ### Existing Constraints

        for item, bid_indices in enumerate(bids_per_item):
            model.addCons(quicksum(bid_vars[bid_idx] for bid_idx in bid_indices) <= 1, f"Item_{item}")

        for (bid1, bid2) in mutual_exclusivity_pairs:
            model.addCons(bid_vars[bid1] + bid_vars[bid2] <= 1, f"Exclusive_{bid1}_{bid2}")

        for i in range(len(bids)):
            model.addCons(quicksum(x_vars[i, j] for j in range(n_facilities)) == bid_vars[i], f"BidFacility_{i}")
        
        for j in range(n_facilities):
            model.addCons(quicksum(x_vars[i, j] for i in range(len(bids))) <= capacity[j] * y_vars[j], f"FacilityCapacity_{j}")

        for i in high_priority_bids:
            model.addCons(quicksum(patrol_vars[i, j] for j in range(n_facilities)) >= 1, f"HighPriorityBidPatrol_{i}")

        for i in high_priority_bids:
            for j in range(n_facilities):
                model.addCons(patrol_vars[i, j] <= y_vars[j], f"PatrolCoverage_{i}_{j}")

        for j in range(n_facilities):
            model.addCons(quicksum(x_vars[i, j] for i in range(len(bids))) >= self.min_bids_per_facility * y_vars[j], f"MinBidsPerFacility_{j}")

        ### New Constraints

        # Inventory balance constraints
        for j in range(n_facilities):
            model.addCons(inv_vars[j] <= initial_inventory[j] + quicksum(x_vars[i, j] for i in range(len(bids))), f"InventoryBalance_{j}")

        # Emission penalty constraints
        for i in range(len(bids)):
            model.addCons(emission_vars[i] == quicksum(emission_factors[i, j] * x_vars[i, j] for j in range(n_facilities)), f"Emission_{i}")

        # Waste minimization constraints
        waste_generation = np.random.uniform(0.1, 5.0, size=n_facilities)
        for j in range(n_facilities):
            model.addCons(waste_vars[j] == quicksum(waste_generation[j] * x_vars[i, j] for i in range(len(bids))), f"Waste_{j}")

        # Sustainable packaging constraints
        sustainable_min = 0.4  # At least 40% of the materials should use sustainable packaging
        for i in range(len(bids)):
            for j in range(n_facilities):
                model.addCons(x_vars[i, j] * (1 - sustainable_packaging[i][j]) <= (1 - sustainable_min), f"SustainablePackaging_{i}_{j}")

        model.setObjective(objective_expr, "maximize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time


if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_items': 3000,
        'n_bids': 588,
        'min_value': 393,
        'max_value': 1125,
        'value_deviation': 0.66,
        'additivity': 0.17,
        'add_item_prob': 0.17,
        'budget_factor': 2275.0,
        'resale_factor': 0.52,
        'max_n_sub_bids': 1181,
        'n_exclusive_pairs': 1500,
        'facility_min_count': 7,
        'facility_max_count': 74,
        'MaxPatrolBudget': 20000,
        'min_bids_per_facility': 30,
    }

    supply_chain_network = AdvancedSupplyChainNetwork(parameters, seed=seed)
    instance = supply_chain_network.generate_instance()
    solve_status, solve_time = supply_chain_network.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")