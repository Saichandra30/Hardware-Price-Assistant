"""
Utility functions and helpers for the application.
"""

from rapidfuzz import fuzz

def fuzzy_match_hardware(query: str, hardware_list: list[str]) -> str:
    """
    Perform a fuzzy search to find the closest matching hardware name.

    Args:
        query (str): The user's search query.
        hardware_list (list[str]): List of available hardware names.

    Returns:
        str: The best matching hardware name.
    """
    pass
