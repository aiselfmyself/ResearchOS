import math
import random
from gitswarm.problem import calculate_tour_distance
from gitswarm.solvers import two_opt

def solve(cities, temp=150.0, cooling=0.995, steps=5000, seed=42):
    n = len(cities)
    rng = random.Random(seed)
    current = two_opt.solve(cities)
    current_dist = calculate_tour_distance(current, cities)
    best = list(current)
    best_dist = current_dist
    t = temp
    for step in range(steps):
        i, k = sorted(rng.sample(range(1, n), 2))
        cand = current[:i] + current[i:k+1][::-1] + current[k+1:]
        cand_dist = calculate_tour_distance(cand, cities)
        diff = cand_dist - current_dist
        if diff < 0 or rng.random() < math.exp(-diff / max(t, 1e-8)):
            current = cand
            current_dist = cand_dist
            if current_dist < best_dist:
                best = list(current)
                best_dist = current_dist
        t *= cooling
    return best
