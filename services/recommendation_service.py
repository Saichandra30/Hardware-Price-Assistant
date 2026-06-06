"""
Service for generating hardware recommendations based on compatibility and tier lists.
"""
import logging
import math
from services.search_service import SearchService
from services.catalog_loader import get_catalog

logger = logging.getLogger(__name__)

class RecommendationService:
    """
    Service to provide motherboard recommendations based on a given CPU.
    """

    def __init__(self):
        self.search_service = SearchService()
        self.catalog = get_catalog()
        
        # Chipset hierarchy mapping to tiers
        self.chipset_hierarchy = {
            "X870E": "Premium",
            "X870": "Premium",
            "B850": "Mid-range",
            "B840": "Budget",
            "B550": "Budget",
            "A520": "Budget"
        }

    def _determine_chipset(self, product_name: str, extracted_chipset: str) -> str:
        """Helper to extract and normalize the chipset from product data."""
        name_upper = product_name.upper()
        extracted_upper = str(extracted_chipset).upper()
        
        # Sort by length descending to match X870E before X870
        for chipset in sorted(self.chipset_hierarchy.keys(), key=len, reverse=True):
            if chipset in name_upper or chipset == extracted_upper:
                return chipset
        return None

    def recommend_product(self, cpu_name: str) -> dict:
        """
        Recommends a Budget, Mid-range, and Premium motherboard for a given CPU.
        """
        logger.info(f"Generating recommendations for CPU: {cpu_name}")
        
        # 1. Verify CPU exists
        cpu_res = self.search_service.search_product(cpu_name)
        if cpu_res["status"] not in ["exact_match", "likely_match"]:
            logger.warning(f"CPU not found or ambiguous: {cpu_name}")
            return {
                "status": "error",
                "message": "CPU not found in catalog.",
                "search_result": cpu_res
            }
            
        cpu = cpu_res["product"]
        cpu_name_upper = str(cpu.get("product_name", "")).upper()
        
        # Basic AMD Socket AM5 vs AM4 heuristic (to avoid incompatible recommendations)
        import re
        is_am5 = bool(re.search(r'(?:7|8|9)\d{3}', cpu_name_upper) or "X3D" in cpu_name_upper)
        
        # 2. Filter motherboards
        all_mbs = [p for p in self.catalog if str(p.get("category", "")).upper() == "MOTHERBOARD"]
        
        tiers = {
            "Premium": [],
            "Mid-range": [],
            "Budget": []
        }
        
        for mb in all_mbs:
            chipset = self._determine_chipset(mb.get("product_name", ""), mb.get("chipset", ""))
            if not chipset:
                continue
                
            # Filter compatibility
            if is_am5 and chipset in ["B550", "A520"]:
                continue
            if not is_am5 and chipset in ["X870E", "X870", "B850", "B840"]:
                continue
                
            tier = self.chipset_hierarchy[chipset]
            
            # Calculate min price for sorting
            prices = [p for p in mb.get("price_data", {}).values() if not math.isnan(p)]
            if prices:
                mb_copy = dict(mb)
                mb_copy["_min_price"] = min(prices)
                tiers[tier].append(mb_copy)
                
        # 3. Pick the best recommendation for each tier
        recommendations = {
            "Budget": None,
            "Mid-range": None,
            "Premium": None
        }
        
        for tier_name, mb_list in tiers.items():
            if not mb_list:
                continue
                
            # Sort by price ascending. We recommend the most affordable board in that specific tier.
            mb_list.sort(key=lambda x: x["_min_price"])
            best_mb = mb_list[0]
            
            # Clean internal key
            del best_mb["_min_price"]
            recommendations[tier_name] = best_mb
            
        return {
            "status": "success",
            "cpu": cpu,
            "recommendations": recommendations
        }
