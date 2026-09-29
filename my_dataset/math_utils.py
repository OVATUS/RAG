"""
Advanced Mathematical Utility Module.
This module provides complex calculation functions for data science applications.
"""
from typing import List, Union
import math

def calculate_compound_interest(principal: float, rate: float, time: int, n: int = 12) -> float:
    """Calculates compound interest over a given time period."""
    if principal < 0 or rate < 0 or time < 0:
        raise ValueError("Inputs cannot be negative.")
    amount = principal * (math.pow((1 + (rate / n)), (n * time)))
    return amount - principal

def normalize_vector(vector: List[float]) -> List[float]:
    """Normalizes a mathematical vector to have a length of 1."""
    if not vector:
        return []
    magnitude = math.sqrt(sum(x**2 for x in vector))
    if magnitude == 0:
        return vector
    return [x / magnitude for x in vector]

def find_prime_factors(n: int) -> List[int]:
    """Finds all prime factors of a given integer."""
    i = 2
    factors = []
    while i * i <= n:
        if n % i:
            i += 1
        else:
            n //= i
            factors.append(i)
    if n > 1:
        factors.append(n)
    return factors