"""
Utility functions and helpers for the application.
"""
import logging
from rapidfuzz import fuzz, process, utils

logger = logging.getLogger(__name__)


def fuzzy_match_hardware(query: str, hardware_list: list) -> str:
    """
    Perform a fuzzy search to find the closest matching hardware name.

    Args:
        query (str): The user's search query.
        hardware_list (list[str]): List of available hardware names.

    Returns:
        str: The best matching hardware name, or empty string if no match.
    """
    if not query or not hardware_list:
        return ""
    try:
        result = process.extractOne(
            query,
            hardware_list,
            scorer=fuzz.WRatio,
            processor=utils.default_process
        )
        if result and result[1] >= 60:
            return result[0]
        return ""
    except Exception as e:
        logger.warning(f"fuzzy_match_hardware failed: {e}")
        return ""


def normalize_product_name(name: str) -> str:
    """
    Normalize a product name for consistent display.
    Removes extra whitespace and trims the string.

    Args:
        name (str): Raw product name.

    Returns:
        str: Normalized product name.
    """
    import re
    if not name:
        return ""
    return re.sub(r'\s+', ' ', str(name)).strip()


def format_price(price: float) -> str:
    """Format a price as Indian Rupees with commas."""
    if not price or price <= 0:
        return "N/A"
    return f"₹{price:,.0f}"
