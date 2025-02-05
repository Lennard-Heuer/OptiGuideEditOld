import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class CombinatorialAuction:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# data generation #################
    def generate_instance(self):
        assert self.min_value >= 0 and self.max_value >= self.min_value
        assert self.add_item_prob >= 0 and self.add_item_prob <= 1

        def choose_next_item(bundle_mask, interests, compats):
            n_items = len(interests)
            prob = (1 - bundle_mask) * interests * compats[bundle_mask, :].mean(axis=0)
            prob /= prob.sum()
            return np.random.choice(n_items, p=prob)

        # common item values (resale price)
        values = self.min_value + (self.max_value - self.min_value) * np.random.rand(self.n_items)

        # item compatibilities
        compats = np.triu(np.random.rand(self.n_items, self.n_items), k=1)
        compats = compats + compats.transpose()
        compats = compats / compats.sum(1)

        # Generate exchange rates
        exchange_rates = np.random.normal(self.mean_exchange_rate, self.exchange_rate_std, self.n_items)

        # Generate ESG penalties
        esg_penalties = np.random.normal(self.mean_esg_penalty, self.esg_penalty_std, self.n_items)

        # Generate geopolitical risks
        geopolitical_risks = np.random.normal(self.mean_geopolitical_risk, self.geopolitical_risk_std, self.n_items)

        # Generate technological disruptions
        technological_disruptions = np.random.normal(self.mean_technological_disruption, self.technological_disruption_std, self.n_items)

        # Generate logistical constraints
        logistic_constraints = np.random.normal(self.mean_logistic_cost, self.logistic_cost_std, self.n_items)

        bids = []

        # create bids, one bidder at a time
        while len(bids) < self.n_bids:

            # bidder item values (buy price) and interests
            private_interests = np.random.rand(self.n_items)
            private_values = values + self.max_value * self.value_deviation * (2 * private_interests - 1)

            # substitutable bids of this bidder
            bidder_bids = {}

            # generate initial bundle, choose first item according to bidder interests
            prob = private_interests / private_interests.sum()
            item = np.random.choice(self.n_items, p=prob)
            bundle_mask = np.full(self.n_items, 0)
            bundle_mask[item] = 1

            # add additional items, according to bidder interests and item compatibilities
            while np.random.rand() < self.add_item_prob:
                # stop when bundle full (no item left)
                if bundle_mask.sum() == self.n_items:
                    break
                item = choose_next_item(bundle_mask, private_interests, compats)
                bundle_mask[item] = 1

            bundle = np.nonzero(bundle_mask)[0]

            # compute bundle price with value additivity
            price = private_values[bundle].sum() + np.power(len(bundle), 1 + self.additivity)

            # Adjust prices with additional constraints
            esg_penalty = esg_penalties[bundle].sum()
            geopolitical_risk_cost = geopolitical_risks[bundle].sum()
            tech_disruption_cost = technological_disruptions[bundle].sum()
            logistic_cost = logistic_constraints[bundle].sum()

            price_adjustment = exchange_rates[bundle].sum() + esg_penalty + geopolitical_risk_cost + tech_disruption_cost + logistic_cost
            adjusted_price = price - price_adjustment

            # drop negatively priced bundles
            if adjusted_price < 0:
                continue

            # bid on initial bundle
            bidder_bids[frozenset(bundle)] = adjusted_price

            for bundle, price in bidder_bids.items():
                bids.append((list(bundle), price))

        bids_per_item = [[] for item in range(self.n_items)]
        for i, bid in enumerate(bids):
            bundle, price = bid
            for item in bundle:
                bids_per_item[item].append(i)

        station_capacities = np.random.randint(self.station_capacity_interval[0], self.station_capacity_interval[1], self.n_stations)
        renewable_supply = np.random.rand(self.n_stations) * self.renewable_capacity_scale

        return {
            "bids": bids,
            "bids_per_item": bids_per_item,
            "station_capacities": station_capacities,
            "renewable_supply": renewable_supply
        }

    ################# PySCIPOpt modeling #################
    def solve(self, instance):
        bids = instance['bids']
        bids_per_item = instance['bids_per_item']
        station_capacities = instance['station_capacities']
        renewable_supply = instance['renewable_supply']

        model = Model("CombinatorialAuction")

        # Decision variables
        bid_vars = {i: model.addVar(vtype="B", name=f"Bid_{i}") for i in range(len(bids))}
        open_stations = {j: model.addVar(vtype="B", name=f"Open_{j}") for j in range(self.n_stations)}
        renewable_vars = {j: model.addVar(vtype="C", name=f"Renewable_{j}") for j in range(self.n_stations)}

        # Objective: maximize the total price
        objective_expr = quicksum(price * bid_vars[i] for i, (bundle, price) in enumerate(bids))

        # Constraints: Each item can be in at most one bundle
        for item, bid_indices in enumerate(bids_per_item):
            model.addCons(quicksum(bid_vars[bid_idx] for bid_idx in bid_indices) <= 1, f"Item_{item}")

        # Station capacity constraints
        for j in range(self.n_stations):
            model.addCons(quicksum(bid_vars[i] for i, (bundle, price) in enumerate(bids) if j in bundle) <= station_capacities[j] * open_stations[j], f"StationCapacity_{j}")

        # Renewable supply constraints
        for j in range(self.n_stations):
            model.addCons(quicksum(bid_vars[i] * price for i, (bundle, price) in enumerate(bids) if j in bundle) <= renewable_vars[j], f"RenewableSupply_{j}")

        model.setObjective(objective_expr, "maximize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_items': 500,
        'n_bids': 750,
        'min_value': 10,
        'max_value': 1125,
        'value_deviation': 0.52,
        'additivity': 0.8,
        'add_item_prob': 0.8,
        'mean_exchange_rate': 0.24,
        'exchange_rate_std': 0.38,
        'mean_esg_penalty': 0.8,
        'esg_penalty_std': 0.45,
        'mean_geopolitical_risk': 0.8,
        'geopolitical_risk_std': 0.31,
        'mean_technological_disruption': 0.52,
        'technological_disruption_std': 0.1,
        'mean_logistic_cost': 0.66,
        'logistic_cost_std': 0.59,
        'n_stations': 350,
        'station_capacity_interval': (300, 3000),
        'renewable_capacity_scale': 2250.0,
    }
    auction = CombinatorialAuction(parameters, seed)
    instance = auction.generate_instance()
    solve_status, solve_time = auction.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")