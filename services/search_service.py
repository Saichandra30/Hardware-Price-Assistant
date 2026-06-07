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

import functools

class SearchService:
    """
    Service for finding and filtering hardware products.
    """

    def __init__(self):
        self.aliases = self._load_aliases()
        self.catalog_mtime = 0.0
        self._check_and_load_catalog()

    def _check_and_load_catalog(self):
        """Checks if catalog.json has changed on disk, and reloads it if so."""
        from services.catalog_loader import CATALOG_PATH
        current_mtime = 0.0
        if os.path.exists(CATALOG_PATH):
            try:
                current_mtime = os.path.getmtime(CATALOG_PATH)
            except Exception:
                pass
        
        # If catalog is not loaded yet or file has been modified
        if not hasattr(self, "catalog") or current_mtime != self.catalog_mtime:
            logger.info("Catalog file changed or loading for the first time. Building indices...")
            self.catalog = get_catalog()
            self.catalog_mtime = current_mtime
            
            # Clear fuzzy match cache to prevent stale results
            try:
                self._fuzzy_match.cache_clear()
            except Exception:
                pass
            
            # Build O(1) in-memory indices for ultra-low latency routing
            self.product_index = {}
            self.brand_index = {}
            self.chipset_index = {}
            self.category_index = {}
            self.series_index = {}
            self.sub_category_index = {}
            
            for item in self.catalog:
                name_clean = str(item.get("product_name", "")).strip().lower()
                brand_clean = str(item.get("brand", "")).strip().lower()
                chipset_clean = str(item.get("chipset", "")).strip().lower()
                category_clean = str(item.get("category", "")).strip().lower()
                series_clean = str(item.get("series", "")).strip().lower()
                subcat_clean = str(item.get("sub_category", "")).strip().lower()
                
                # Populate product index
                self.product_index[name_clean] = item
                
                # Populate brand index
                if brand_clean:
                    if brand_clean not in self.brand_index:
                        self.brand_index[brand_clean] = []
                    self.brand_index[brand_clean].append(item)
                    
                # Populate chipset index
                if chipset_clean:
                    if chipset_clean not in self.chipset_index:
                        self.chipset_index[chipset_clean] = []
                    self.chipset_index[chipset_clean].append(item)
                    
                # Populate category index
                if category_clean:
                    if category_clean not in self.category_index:
                        self.category_index[category_clean] = []
                    self.category_index[category_clean].append(item)

                # Populate series index (ROG, TUF, PRIME, PRO)
                if series_clean:
                    if series_clean not in self.series_index:
                        self.series_index[series_clean] = []
                    self.series_index[series_clean].append(item)

                # Populate sub_category index (Gaming, Mainstream, Professional)
                if subcat_clean:
                    if subcat_clean not in self.sub_category_index:
                        self.sub_category_index[subcat_clean] = []
                    self.sub_category_index[subcat_clean].append(item)
                    
            # Expand alias index to directly map alias to product objects if they exist
            self.alias_index = {}
            for alias, targets in self.aliases.items():
                alias_clean = alias.strip().lower()
                self.alias_index[alias_clean] = targets

    def _load_aliases(self) -> dict:
        if os.path.exists(ALIASES_PATH):
            with open(ALIASES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def exact_lookup(self, product_name: str) -> dict:
        """
        Find a product by its exact name (O(1) lookup).
        """
        self._check_and_load_catalog()
        logger.info(f"Performing exact lookup for: {product_name}")
        target = str(product_name).strip().lower()
        
        if target in self.product_index:
            return {
                "status": "success",
                "product": self.product_index[target]
            }
                
        logger.warning(f"Exact match not found for: {product_name}")
        return {
            "status": "not_found",
            "product": None
        }

    def _adjust_score(self, query: str, item: dict, base_score: float) -> float:
        import re
        q = query.lower()
        
        brand = str(item.get("brand", "")).lower()
        chipset = str(item.get("chipset", "")).lower()
        series = str(item.get("series", "")).lower()
        category = str(item.get("category", "")).lower()
        product_name = str(item.get("product_name", "")).lower()
        
        score = base_score
        
        # 1. Brand match/mismatch
        brands = ["msi", "asus", "amd"]
        for b in brands:
            if b in q:
                if brand == b:
                    score += 10
                else:
                    score -= 50
                    
        # 2. Chipset match/mismatch
        chipsets = ["x870e", "x870", "b850", "b840", "x670", "b650", "a620"]
        query_has_chipset = False
        product_matches_chipset = False
        for c in chipsets:
            if c in q:
                query_has_chipset = True
                if chipset == c:
                    product_matches_chipset = True
                    break
        if query_has_chipset:
            if product_matches_chipset:
                score += 15
            else:
                score -= 30
                
        # 3. Series match/mismatch
        series_list = ["rog", "tuf", "prime", "proart"]
        query_has_series = False
        product_matches_series = False
        for s in series_list:
            if s in q:
                query_has_series = True
                if series == s:
                    product_matches_series = True
                    break
        # Special check for "pro" word
        if not query_has_series and re.search(r'\bpro\b', q):
            query_has_series = True
            if series == "pro":
                product_matches_series = True
                
        if query_has_series:
            if product_matches_series:
                score += 10
            else:
                score -= 20
                
        # 4. Exact word match for CPU names
        if category == "cpu" and product_name in q:
            score += 20
            
        return max(0.0, min(100.0, score))

    @functools.lru_cache(maxsize=512)
    def _fuzzy_match(self, term: str) -> list:
        """Cached fuzzy match logic."""
        choices = [f"{item.get('brand', '')} {item['product_name']}".strip() for item in self.catalog]
        return process.extract(term, choices, scorer=fuzz.WRatio, processor=utils.default_process, limit=10)

    def search_product(self, query: str) -> dict:
        """
        Search for a product using exact, alias, and fuzzy matching.
        """
        self._check_and_load_catalog()
        logger.info(f"Searching product for query: {query}")
        if not self.catalog:
            return {"status": "error", "message": "Catalog is empty."}

        query_clean = str(query).strip().lower()
        # Clean typos and specific variations
        query_clean = query_clean.replace("morter", "mortar").replace("wiif", "wifi").replace("9700xx", "9700x")
        
        # 0. Check O(1) precise intent routing mappings
        if query_clean in self.brand_index:
            return {
                "status": "ask_clarification",
                "score": 100,
                "message": f"I found {len(self.brand_index[query_clean])} **{query.upper()}** products. Which type are you interested in?",
                "suggestions": self.brand_index[query_clean][:10]
            }
            
        if query_clean in self.category_index:
            return {
                "status": "ask_clarification",
                "score": 100,
                "message": f"I found {len(self.category_index[query_clean])} **{query.upper()}** products. Would you like to filter by brand, chipset, or price?",
                "suggestions": self.category_index[query_clean][:10]
            }
            
        if query_clean in self.chipset_index:
            return {
                "status": "ask_clarification",
                "score": 100,
                "message": f"I found {len(self.chipset_index[query_clean])} **{query.upper()}** boards. Which brand are you interested in — ASUS or MSI?",
                "suggestions": self.chipset_index[query_clean][:10]
            }
            
        if query_clean in self.product_index:
            return {
                "status": "exact_match",
                "score": 100,
                "product": self.product_index[query_clean]
            }
        
        # 1. Expand aliases
        search_terms = [query_clean]
        for alias, targets in self.alias_index.items():
            if alias in query_clean:
                search_terms.extend([t.lower() for t in targets])
                
        best_overall_score = 0
        best_overall_index = -1
        all_results = []
        
        # Search all expanded terms and keep the best scores
        for term in search_terms:
            results = self._fuzzy_match(term)
            for res_str, score, idx in results:
                adjusted = self._adjust_score(query_clean, self.catalog[idx], score)
                all_results.append((res_str, adjusted, idx))
                if adjusted > best_overall_score:
                    best_overall_score = adjusted
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

    def filter_products(self, category: str = None, brand: str = None, chipset: str = None,
                        max_price: float = None, sub_category: str = None, series: str = None,
                        name_contains: str = None) -> dict:
        """
        Filter products based on specific criteria.
        Supports: category, brand, chipset, max_price, sub_category, series, name_contains
        """
        self._check_and_load_catalog()
        logger.info(
            f"Filtering products - category:{category}, brand:{brand}, chipset:{chipset}, "
            f"max_price:{max_price}, sub_category:{sub_category}, series:{series}, name_contains:{name_contains}"
        )
        results = []
        
        # Parse query-like category strings (e.g. "AM5 Motherboard")
        if category and not chipset:
            cat_upper = category.upper()
            if "AM5" in cat_upper:
                chipset = "AM5"
                category = category.upper().replace("AM5", "").strip()
            elif "AM4" in cat_upper:
                chipset = "AM4"
                category = category.upper().replace("AM4", "").strip()

        for item in self.catalog:
            if category and category.upper() not in str(item.get("category", "")).upper():
                continue
                
            if brand and brand.upper() != str(item.get("brand", "")).upper():
                continue

            if series and series.upper() != str(item.get("series", "")).upper():
                continue

            if sub_category and sub_category.upper() != str(item.get("sub_category", "")).upper():
                continue

            if name_contains:
                item_name_upper = str(item.get("product_name", "")).upper()
                term = name_contains.upper()
                if term == "WIFI":
                    if not any(w in item_name_upper for w in ["WIFI", "WI-FI", "WIIF", "WI FI"]):
                        continue
                else:
                    if term not in item_name_upper:
                        continue

            if chipset:
                target_chipset = chipset.upper()
                item_chipset = str(item.get("chipset", "")).upper()
                item_name = str(item.get("product_name", "")).upper()
                
                # Handle socket aliases
                if target_chipset == "AM5":
                    am5_chipsets = ["X870", "B850", "B840", "X670", "B650", "A620"]
                    if not any(c in item_chipset or c in item_name for c in am5_chipsets):
                        continue
                elif target_chipset == "AM4":
                    am4_chipsets = ["X570", "B550", "A520", "X470", "B450", "A320"]
                    if not any(c in item_chipset or c in item_name for c in am4_chipsets):
                        continue
                else:
                    if target_chipset not in item_chipset and target_chipset not in item_name:
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

    def get_cheapest(self, category: str = None, brand: str = None, chipset: str = None) -> dict:
        """
        Get the cheapest product matching the criteria.
        """
        self._check_and_load_catalog()
        logger.info(f"Finding cheapest product - category:{category}, brand:{brand}, chipset:{chipset}")
        
        # Parse query-like category strings (e.g. "AM5 Motherboard")
        if category and not chipset:
            cat_upper = category.upper()
            if "AM5" in cat_upper:
                chipset = "AM5"
                category = category.upper().replace("AM5", "").strip()
            elif "AM4" in cat_upper:
                chipset = "AM4"
                category = category.upper().replace("AM4", "").strip()
                
        filter_res = self.filter_products(category=category, brand=brand, chipset=chipset)
        if filter_res["count"] == 0:
            return {
                "status": "not_found",
                "message": f"No valid products found matching those criteria."
            }
            
        cheapest_product = None
        min_price = float('inf')
        
        for item in filter_res["results"]:
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
                "message": f"Products found, but none had valid prices."
            }
