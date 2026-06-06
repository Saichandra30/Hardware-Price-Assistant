import os
import json
import logging
import math
import pandas as pd
import streamlit as st
from data.excel_handler import ExcelHandler

logger = logging.getLogger(__name__)

CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "catalog.json")

def _clean_price(price_val) -> float:
    """Clean a price value and convert to float."""
    if pd.isna(price_val):
        return 0.0
        
    try:
        cleaned = str(price_val).replace(',', '').replace('₹', '').replace('Rs', '').strip()
        num_price = float(cleaned)
        return num_price
    except ValueError:
        return 0.0

def normalize_catalog(sheets_data: dict[str, pd.DataFrame]) -> list[dict]:
    """
    Normalize raw sheet DataFrames into a unified product catalog.
    
    Returns:
        list[dict]: A list of normalized product dictionaries in canonical schema.
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
                prices = {"dealer": 0.0, "disti": 0.0, "imp": 0.0}
                price_found = False
                
                for pc in range(c + 1, min(c + 4, cols)):
                    price_val = df.iloc[r, pc]
                    num_price = _clean_price(price_val)
                    if num_price > 0:
                        price_found = True
                        header_name = f"Price_{pc}"
                        for hr in range(max(0, r-2), r):
                            h_val = df.iloc[hr, pc]
                            if not pd.isna(h_val) and isinstance(h_val, str):
                                h_str = str(h_val).strip().lower()
                                if "dealer" in h_str:
                                    header_name = "dealer"
                                elif "disti" in h_str:
                                    header_name = "disti"
                                elif "imp" in h_str:
                                    header_name = "imp"
                                elif len(h_str) > 1 and not h_str.isdigit():
                                    header_name = "dealer" # fallback
                                    
                        # Default to dealer if not matched
                        if header_name not in ["dealer", "disti", "imp"]:
                            header_name = "dealer"
                        
                        prices[header_name] = num_price
                        
                if price_found:
                    # Extract chipset and series
                    chipset = ""
                    series = ""
                    sub_category = ""
                    
                    if "X870E" in upper_val:
                        chipset = "X870E"
                    elif "X870" in upper_val:
                        chipset = "X870"
                    elif "B850" in upper_val:
                        chipset = "B850"
                    elif "B840" in upper_val:
                        chipset = "B840"
                    elif "X670" in upper_val:
                        chipset = "X670"
                    elif "B650" in upper_val:
                        chipset = "B650"
                    elif "A620" in upper_val:
                        chipset = "A620"
                        
                    if "ROG" in upper_val:
                        series = "ROG"
                        sub_category = "Gaming"
                    elif "TUF" in upper_val:
                        series = "TUF"
                        sub_category = "Gaming"
                    elif "PRIME" in upper_val:
                        series = "PRIME"
                        sub_category = "Mainstream"
                    elif "PRO" in upper_val:
                        series = "PRO"
                        sub_category = "Professional"
                        
                    # Generate ID
                    clean_id = f"{current_category[:2]}_{current_brand}_{product_name}".lower()
                    import re
                    clean_id = re.sub(r'[^a-z0-9_]', '_', clean_id)
                    clean_id = re.sub(r'_+', '_', clean_id).strip('_')

                    catalog.append({
                        "id": clean_id,
                        "product_name": product_name,
                        "brand": current_brand,
                        "series": series,
                        "category": current_category,
                        "chipset": chipset,
                        "sub_category": sub_category,
                        "manufacturer": current_brand,
                        "prices": prices
                    })
                    
    return catalog

def generate_catalog_json():
    """Reads from Excel, normalizes, and saves to catalog.json."""
    logger.info("Generating catalog.json from Excel source...")
    handler = ExcelHandler()
    sheets_data = handler.load_data()
    catalog = normalize_catalog(sheets_data)
    
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=4)
    logger.info(f"Saved {len(catalog)} products to catalog.json")

def load_catalog() -> list[dict]:
    """
    Load the catalog from catalog.json.
    
    Returns:
        list[dict]: The normalized catalog.
    """
    if not os.path.exists(CATALOG_PATH):
        generate_catalog_json()
        
    logger.info("Loading catalog from catalog.json...")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    
    # Print statistics
    total_products = len(catalog)
    cpu_count = sum(1 for p in catalog if p.get("category") == "CPU")
    mb_count = sum(1 for p in catalog if p.get("category") == "Motherboard")
    brands_count = len(set(p.get("brand") for p in catalog))
    
    stats_msg = (
        f"Catalog loaded successfully from JSON!\n"
        f"Total Products: {total_products}\n"
        f"CPUs: {cpu_count}\n"
        f"Motherboards: {mb_count}\n"
        f"Brands: {brands_count}"
    )
    logger.info(stats_msg)
    
    return catalog

@st.cache_data
def get_catalog() -> list[dict]:
    """
    Get the catalog with Streamlit caching.
    
    Returns:
        list[dict]: The cached normalized catalog.
    """
    return load_catalog()

