import json
from gitswarm.problem import generate_cities, calculate_tour_distance, is_valid_tour
from gitswarm.solvers import greedy, random_search, two_opt, simulated_annealing

SEEDS = [42, 100, 777, 999, 2026]

def run_benchmarks():
    results = {"greedy": [], "random": [], "two_opt": [], "simulated_annealing": []}
    for s in SEEDS:
        cities = generate_cities(30, seed=s)
        n = len(cities)
        
        t_greedy = greedy.solve(cities)
        results["greedy"].append(calculate_tour_distance(t_greedy, cities))
        
        t_rand = random_search.solve(cities, iterations=500, seed=s)
        results["random"].append(calculate_tour_distance(t_rand, cities))
        
        t_2opt = two_opt.solve(cities)
        results["two_opt"].append(calculate_tour_distance(t_2opt, cities))
        
        t_sa = simulated_annealing.solve(cities, seed=s)
        results["simulated_annealing"].append(calculate_tour_distance(t_sa, cities))
        
    summary = {}
    for solver, dists in results.items():
        summary[solver] = {
            "mean_distance": round(sum(dists) / len(dists), 2),
            "min_distance": min(dists),
            "max_distance": max(dists),
            "runs": len(dists)
        }
    return summary
