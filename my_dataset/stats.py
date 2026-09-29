"""
Statistical Analysis and Aggregation Module.
Handles large datasets and provides robust statistical metrics.
"""
from typing import List, Dict
import math
from math_utils import normalize_vector # จำลองการเรียกใช้ไฟล์ข้ามโมดูล

def calculate_mean(numbers: List[float]) -> float:
    """Calculates the arithmetic mean of a list of numbers."""
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)

def calculate_variance(numbers: List[float], sample: bool = True) -> float:
    """
    Calculates the variance of a dataset. 
    Calls calculate_mean() internally.
    """
    if len(numbers) < 2:
        return 0.0
    m = calculate_mean(numbers)
    denominator = len(numbers) - 1 if sample else len(numbers)
    return sum((x - m) ** 2 for x in numbers) / denominator

def calculate_standard_deviation(numbers: List[float]) -> float:
    """
    Calculates the standard deviation.
    Depends on calculate_variance().
    """
    return math.sqrt(calculate_variance(numbers))

def analyze_dataset(data: List[float]) -> Dict[str, float]:
    """
    Performs a full statistical analysis on a dataset.
    Normalizes the data before analysis using math_utils.
    """
    normalized_data = normalize_vector(data)
    return {
        "mean": calculate_mean(normalized_data),
        "variance": calculate_variance(normalized_data),
        "std_dev": calculate_standard_deviation(normalized_data)
    }