import random
from gitswarm.problem import calculate_tour_distance

def solve(cities, iterations=1000, seed=42):
    n = len(cities)
    rng = random.Random(seed)
    best_tour = list(range(n))
    best_dist = calculate_tour_distance(best_tour, cities)
    for _ in range(iterations):
        cand = list(range(n))
        rng.shuffle(cand)
        d = calculate_tour_distance(cand, cities)
        if d < best_dist:
            best_dist = d
            best_tour = cand
    return best_tour
