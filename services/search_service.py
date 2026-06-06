"""
Service for searching, filtering, and comparing hardware products using fuzzy matching.
"""
import os
import json
import logging
import math
from rapidfuzz import fuzz, process, utils
from services.catalog_loader import get_catalog

logger = logging.getLogger(__name__)

ALIASES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "product_aliases.json")

class SearchService:
    """
    Service for finding and filtering hardware products.
    """

    def __init__(self):
        self.catalog = get_catalog()
        self.aliases = self._load_aliases()

    def _load_aliases(self) -> dict:
        if os.path.exists(ALIASES_PATH):
            with open(ALIASES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def exact_lookup(self, product_name: str) -> dict:
        """
        Find a product by its exact name or ID (case-insensitive).
        """
        logger.info(f"Performing exact lookup for: {product_name}")
        target = str(product_name).strip().upper()
        
        for item in self.catalog:
            name_upper = str(item.get("product_name", "")).strip().upper()
            id_upper = str(item.get("id", "")).strip().upper()
            if target == name_upper or target == id_upper:
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
        Search for a product using exact, alias, and fuzzy matching.
        """
        logger.info(f"Searching product for query: {query}")
        if not self.catalog:
            return {"status": "error", "message": "Catalog is empty."}

        query_clean = str(query).strip().lower()
        
        # Check if query matches a brand or category exactly
        brands = set(str(item.get("brand", "")).lower() for item in self.catalog if item.get("brand"))
        categories = set(str(item.get("category", "")).lower() for item in self.catalog if item.get("category"))
        
        if query_clean in brands or query_clean in categories:
            matched_items = [item for item in self.catalog if 
                             str(item.get("brand", "")).lower() == query_clean or 
                             str(item.get("category", "")).lower() == query_clean]
            
            return {
                "status": "ask_clarification",
                "score": 100,
                "message": f"You searched for '{query}', which is a broad brand or category. I found {len(matched_items)} items. Could you be more specific on which model you need?",
                "suggestions": matched_items[:5]
            }
        
        # 1. Expand aliases
        search_terms = [query_clean]
        for key, targets in self.aliases.items():
            if key.lower() in query_clean:
                search_terms.extend([t.lower() for t in targets])
                
        choices = [f"{item.get('brand', '')} {item['product_name']}".strip() for item in self.catalog]
        
        best_overall_score = 0
        best_overall_index = -1
        all_results = []
        
        # Search all expanded terms and keep the best scores
        for term in search_terms:
            results = process.extract(term, choices, scorer=fuzz.WRatio, processor=utils.default_process, limit=10)
            for res_str, score, idx in results:
                all_results.append((res_str, score, idx))
                if score > best_overall_score:
                    best_overall_score = score
                    best_overall_index = idx
                    
        if best_overall_index == -1:
             return {
                "status": "ask_clarification",
                "score": 0,
                "message": "No products matched your query. Could you be more specific?",
                "suggestions": []
            }
            
        # Deduplicate and sort all results
        unique_results = {}
        for res_str, score, idx in all_results:
            if idx not in unique_results or unique_results[idx] < score:
                unique_results[idx] = score
                
        sorted_indices = sorted(unique_results.keys(), key=lambda k: unique_results[k], reverse=True)
        top_candidates = [self.catalog[i] for i in sorted_indices[:3]]

        product = self.catalog[best_overall_index]

        # Use confidence thresholds
        if best_overall_score >= 90:
            return {
                "status": "exact_match",
                "score": best_overall_score,
                "product": product
            }
        elif best_overall_score >= 75:
            return {
                "status": "likely_match",
                "score": best_overall_score,
                "product": product,
                "suggestions": top_candidates
            }
        elif best_overall_score >= 50:
            return {
                "status": "ask_clarification",
                "score": best_overall_score,
                "message": f"I found multiple ambiguous matches for '{query}'. Which one did you mean?",
                "suggestions": top_candidates
            }
        else:
            return {
                "status": "not_found",
                "score": best_overall_score,
                "message": f"Could not find any products matching '{query}'. Please check the spelling or try a different product."
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
                prices = [p for p in item.get("prices", {}).values() if p > 0]
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
                prices = [p for p in item.get("prices", {}).values() if p > 0]
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
