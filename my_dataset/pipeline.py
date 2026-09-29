"""
Data Processing Pipeline Module.
Orchestrates data loading, cleaning, and statistical analysis.
"""
from typing import List, Dict, Any
from stats import analyze_dataset # เรียกใช้งานฟังก์ชันจาก stats.py

def fetch_data_from_source(source_url: str) -> List[float]:
    """Simulates fetching raw data from a remote server or database."""
    print(f"Fetching data from {source_url}...")
    # Simulated messy data
    return [15.5, -3.2, 42.0, 0.0, 105.1, -99.9, 8.4]

def clean_data(raw_data: List[float]) -> List[float]:
    """
    Cleans raw data by removing negative numbers and outliers.
    """
    cleaned = [x for x in raw_data if x >= 0 and x <= 100]
    print(f"Data cleaned. Retained {len(cleaned)} items out of {len(raw_data)}.")
    return cleaned

def run_ml_pipeline(source: str) -> Dict[str, Any]:
    """
    Main entry point for the pipeline.
    Calls fetch_data_from_source(), clean_data(), and analyze_dataset().
    """
    raw_data = fetch_data_from_source(source)
    cleaned_data = clean_data(raw_data)
    
    if not cleaned_data:
         return {"status": "error", "message": "No valid data found."}
         
    analysis_results = analyze_dataset(cleaned_data)
    
    return {
        "status": "success",
        "processed_count": len(cleaned_data),
        "statistics": analysis_results
    }