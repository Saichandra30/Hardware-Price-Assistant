"""
Service for searching, filtering, and comparing hardware products using fuzzy matching.
"""
import logging
import math
from rapidfuzz import fuzz, process
from services.catalog_loader import get_catalog

logger = logging.getLogger(__name__)

class SearchService:
    """
    Service for finding and filtering hardware products.
    """

    def __init__(self):
        self.catalog = get_catalog()

    def exact_lookup(self, product_name: str) -> dict:
        """
        Find a product by its exact name (case-insensitive).
        """
        logger.info(f"Performing exact lookup for: {product_name}")
        target = str(product_name).strip().upper()
        
        for item in self.catalog:
            if str(item.get("product_name", "")).strip().upper() == target:
                return {
                    "status": "success",
                    "product": item
                }
                
        logger.warning(f"Exact match not found for: {product_name}")
        return {
            "status": "not_found",
            "product": None
        }

    def search_product(self, query: str) -> dict:
        """
        Search for a product using fuzzy matching.
        """
        logger.info(f"Searching product for query: {query}")
        if not self.catalog:
            return {"status": "error", "message": "Catalog is empty."}

        choices = [item["product_name"] for item in self.catalog]
        
        # Get the top matches
        results = process.extract(query, choices, scorer=fuzz.WRatio, limit=5)
        
        if not results:
            return {
                "status": "suggestions",
                "score": 0,
                "suggestions": []
            }
            
        best_match, score, index = results[0]
        
        # Retrieve the full product dictionary
        product = self.catalog[index]

        if score >= 90:
            return {
                "status": "exact_match",
                "score": score,
                "product": product
            }
        elif score >= 70:
            return {
                "status": "likely_match",
                "score": score,
                "product": product
            }
        else:
            suggestions = [{"product_name": r[0], "score": r[1]} for r in results]
            return {
                "status": "suggestions",
                "score": score,
                "suggestions": suggestions
            }

    def compare_products(self, product1_query: str, product2_query: str) -> dict:
        """
        Compare two products by finding their best matches.
        """
        logger.info(f"Comparing: {product1_query} vs {product2_query}")
        res1 = self.search_product(product1_query)
        res2 = self.search_product(product2_query)
        
        return {
            "status": "success",
            "product1_result": res1,
            "product2_result": res2
        }

    def filter_products(self, category: str = None, brand: str = None, chipset: str = None, max_price: float = None) -> dict:
        """
        Filter products based on specific criteria.
        """
        logger.info(f"Filtering products - category:{category}, brand:{brand}, chipset:{chipset}, max_price:{max_price}")
        results = []
        
        for item in self.catalog:
            if category and category.upper() not in str(item.get("category", "")).upper():
                continue
                
            if brand and brand.upper() != str(item.get("brand", "")).upper():
                continue
                
            if chipset and chipset.upper() not in str(item.get("chipset", "")).upper():
                continue
                
            if max_price is not None:
                # Find the minimum valid price for the item
                prices = [p for p in item.get("price_data", {}).values() if not math.isnan(p)]
                if not prices:
                    continue
                min_item_price = min(prices)
                if min_item_price > max_price:
                    continue
                    
            results.append(item)
            
        return {
            "status": "success",
            "count": len(results),
            "results": results
        }

    def get_cheapest(self, category: str) -> dict:
        """
        Get the cheapest product in a specific category.
        """
        logger.info(f"Finding cheapest product for category: {category}")
        cheapest_product = None
        min_price = float('inf')
        
        for item in self.catalog:
            item_category = str(item.get("category", "")).strip().upper()
            if item_category and item_category in category.upper():
                prices = [p for p in item.get("price_data", {}).values() if not math.isnan(p)]
                if prices:
                    item_min = min(prices)
                    if item_min < min_price:
                        min_price = item_min
                        cheapest_product = item
                        
        if cheapest_product:
            return {
                "status": "success",
                "min_price": min_price,
                "product": cheapest_product
            }
        else:
            return {
                "status": "not_found",
                "message": f"No valid products found for category {category}."
            }
