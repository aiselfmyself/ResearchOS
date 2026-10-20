"""
GitSwarm Verification Benchmark Problem: 30-City Euclidean TSP
Deterministic benchmark for evaluating compounding inference across workers.
"""
import math
import random

def generate_cities(n=30, seed=42):
    rng = random.Random(seed)
    cities = []
    for i in range(n):
        x = rng.uniform(0, 1000)
        y = rng.uniform(0, 1000)
        cities.append((x, y))
    return cities

def euclidean_distance(c1, c2):
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)

def calculate_tour_distance(tour, cities):
    dist = 0.0
    n = len(tour)
    for i in range(n):
        c1 = cities[tour[i]]
        c2 = cities[tour[(i + 1) % n]]
        dist += euclidean_distance(c1, c2)
    return round(dist, 3)

def is_valid_tour(tour, n):
    return len(tour) == n and set(tour) == set(range(n))
