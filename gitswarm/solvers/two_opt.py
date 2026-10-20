from gitswarm.problem import calculate_tour_distance
from gitswarm.solvers import greedy

def solve(cities):
    n = len(cities)
    best = greedy.solve(cities)
    best_dist = calculate_tour_distance(best, cities)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                new_t = best[:i] + best[i:k+1][::-1] + best[k+1:]
                d = calculate_tour_distance(new_t, cities)
                if d < best_dist:
                    best = new_t
                    best_dist = d
                    improved = True
                    break
            if improved:
                break
    return best
