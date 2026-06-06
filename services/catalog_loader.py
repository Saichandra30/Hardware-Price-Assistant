import logging
import math
import pandas as pd
import streamlit as st
from data.excel_handler import ExcelHandler

logger = logging.getLogger(__name__)

def _clean_price(price_val) -> float:
    """Clean a price value and convert to float."""
    if pd.isna(price_val):
        return math.nan
        
    try:
        cleaned = str(price_val).replace(',', '').replace('₹', '').replace('Rs', '').strip()
        num_price = float(cleaned)
        return num_price
    except ValueError:
        return math.nan

def normalize_catalog(sheets_data: dict[str, pd.DataFrame]) -> list[dict]:
    """
    Normalize raw sheet DataFrames into a unified product catalog.
    
    Args:
        sheets_data (dict[str, pd.DataFrame]): Dictionary mapping sheet name to DataFrame.
        
    Returns:
        list[dict]: A list of normalized product dictionaries.
    """
    catalog = []
    
    for sheet_name, df in sheets_data.items():
        logger.info(f"Normalizing sheet: {sheet_name}")
        rows, cols = df.shape
        
        for c in range(cols):
            current_brand = None
            current_category = None
            
            for r in range(rows):
                val = df.iloc[r, c]
                if pd.isna(val):
                    continue
                
                str_val = str(val).strip()
                upper_val = str_val.upper()
                
                # Detect blocks
                is_header = False
                if "AMD" in upper_val and "CPU" in upper_val:
                    current_brand = "AMD"
                    current_category = "CPU"
                    is_header = True
                elif "ASUS" in upper_val:
                    current_brand = "ASUS"
                    current_category = "Motherboard"
                    is_header = True
                elif "MSI" in upper_val:
                    current_brand = "MSI"
                    current_category = "Motherboard"
                    is_header = True
                    
                if is_header:
                    continue
                    
                if current_brand is None:
                    continue
                    
                # Skip sub-headers and blanks
                if "SOLUTION" in upper_val or str_val == "":
                    continue
                    
                product_name = str_val
                
                # Find prices in adjacent columns
                price_data = {}
                for pc in range(c + 1, min(c + 4, cols)):
                    price_val = df.iloc[r, pc]
                    num_price = _clean_price(price_val)
                    if not math.isnan(num_price):
                        # Attempt to find a header for this price column
                        header_name = f"Price_{pc}"
                        # Look up to 2 rows above for a string header
                        for hr in range(max(0, r-2), r):
                            h_val = df.iloc[hr, pc]
                            if not pd.isna(h_val) and isinstance(h_val, str):
                                h_str = str(h_val).strip()
                                if h_str and not h_str.isdigit() and len(h_str) > 1:
                                    header_name = h_str
                                    
                        price_data[header_name] = num_price
                        
                if price_data:
                    # Extract chipset
                    chipset = ""
                    if "X870" in upper_val:
                        chipset = "X870"
                    elif "B850" in upper_val:
                        chipset = "B850"
                        
                    catalog.append({
                        "product_name": product_name,
                        "brand": current_brand,
                        "category": current_category,
                        "chipset": chipset,
                        "price_data": price_data,
                        "source_sheet": sheet_name
                    })
                    
    return catalog

def load_catalog() -> list[dict]:
    """
    Load the Excel data and normalize it into a catalog.
    
    Returns:
        list[dict]: The normalized catalog.
    """
    logger.info("Loading catalog...")
    handler = ExcelHandler()
    sheets_data = handler.load_data()
    catalog = normalize_catalog(sheets_data)
    
    # Print statistics
    total_products = len(catalog)
    cpu_count = sum(1 for p in catalog if p["category"] == "CPU")
    mb_count = sum(1 for p in catalog if p["category"] == "Motherboard")
    brands_count = len(set(p["brand"] for p in catalog))
    
    stats_msg = (
        f"Catalog loaded successfully!\n"
        f"Total Products: {total_products}\n"
        f"CPUs: {cpu_count}\n"
        f"Motherboards: {mb_count}\n"
        f"Brands: {brands_count}"
    )
    logger.info(stats_msg)
    print(stats_msg)
    
    return catalog

@st.cache_data
def get_catalog() -> list[dict]:
    """
    Get the catalog with Streamlit caching.
    
    Returns:
        list[dict]: The cached normalized catalog.
    """
    return load_catalog()
