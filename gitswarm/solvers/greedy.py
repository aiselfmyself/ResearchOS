from gitswarm.problem import calculate_tour_distance, euclidean_distance

def solve(cities):
    n = len(cities)
    unvisited = set(range(1, n))
    current = 0
    tour = [0]
    while unvisited:
        next_c = min(unvisited, key=lambda c: euclidean_distance(cities[current], cities[c]))
        tour.append(next_c)
        unvisited.remove(next_c)
        current = next_c
    return tour
