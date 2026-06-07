"""
Service for generating hardware recommendations based on compatibility and tier lists.
"""
import logging
from services.search_service import SearchService

logger = logging.getLogger(__name__)

class RecommendationService:
    """
    Service to provide motherboard recommendations based on a given CPU.
    """

    def __init__(self):
        self.search_service = SearchService()
        
        # Chipset hierarchy mapping to tiers
        self.chipset_hierarchy = {
            "X870E": "Recommended Premium Choice",
            "X870": "Recommended Premium Choice",
            "X670E": "Recommended Premium Choice",
            "X670": "Recommended Premium Choice",
            "B850": "Recommended Performance Choice",
            "B650": "Recommended Performance Choice",
            "B840": "Recommended Value Choice",
            "B550": "Recommended Value Choice",
            "A620": "Recommended Value Choice",
            "A520": "Recommended Value Choice"
        }

    def _determine_chipset(self, product_name: str, extracted_chipset: str) -> str:
        """Helper to extract and normalize the chipset from product data."""
        name_upper = product_name.upper()
        extracted_upper = str(extracted_chipset).upper()
        
        for chipset in sorted(self.chipset_hierarchy.keys(), key=len, reverse=True):
            if chipset in name_upper or chipset == extracted_upper:
                return chipset
        return None

    def recommend_product(self, cpu_name: str) -> dict:
        """
        Recommends a Premium, Performance, and Value motherboard for a given CPU.
        """
        logger.info(f"Generating recommendations for CPU: {cpu_name}")
        
        # 1. Verify CPU exists
        cpu_res = self.search_service.search_product(cpu_name)
        if cpu_res["status"] not in ["exact_match", "likely_match"]:
            logger.warning(f"CPU not found or ambiguous: {cpu_name}")
            return {
                "status": "error",
                "message": "CPU not found in catalog or ambiguous.",
                "search_result": cpu_res
            }
            
        cpu = cpu_res["product"]
        cpu_name_upper = str(cpu.get("product_name", "")).upper()
        
        # Basic AMD Socket AM5 vs AM4 heuristic
        import re
        is_am5 = bool(re.search(r'(?:7|8|9)\d{3}', cpu_name_upper) or "X3D" in cpu_name_upper)
        
        # 2. Filter motherboards
        all_mbs = [p for p in self.search_service.catalog if str(p.get("category", "")).upper() == "MOTHERBOARD"]
        
        tiers = {
            "Recommended Premium Choice": [],
            "Recommended Performance Choice": [],
            "Recommended Value Choice": []
        }
        
        for mb in all_mbs:
            chipset = self._determine_chipset(mb.get("product_name", ""), mb.get("chipset", ""))
            if not chipset:
                continue
                
            # Filter compatibility
            if is_am5 and chipset in ["B550", "A520"]:
                continue
            if not is_am5 and chipset in ["X870E", "X870", "B850", "B840", "X670", "B650", "A620"]:
                continue
                
            tier = self.chipset_hierarchy[chipset]
            
            # Calculate min price for sorting
            prices = [p for p in mb.get("prices", {}).values() if p > 0]
            if prices:
                mb_copy = dict(mb)
                mb_copy["_min_price"] = min(prices)
                tiers[tier].append(mb_copy)
                
        # Double-check validation against current catalog IDs
        catalog_ids = {item.get("id") for item in self.search_service.catalog if item.get("id")}
        recommendations = {}
        
        ordered_tiers = [
            "Recommended Premium Choice",
            "Recommended Performance Choice",
            "Recommended Value Choice"
        ]
        
        for tier_name in ordered_tiers:
            mb_list = tiers[tier_name]
            if not mb_list:
                recommendations[tier_name] = None
                continue
                
            # Sort by price ascending within the tier
            mb_list.sort(key=lambda x: x["_min_price"])
            best_mb = mb_list[0]
            del best_mb["_min_price"]
            
            # Validate that the product exists in the catalog
            if best_mb.get("id") in catalog_ids:
                recommendations[tier_name] = best_mb
            else:
                recommendations[tier_name] = None
            
        # Check if recommendations are empty
        has_recs = any(v is not None for v in recommendations.values())
        if not has_recs:
            return {
                "status": "empty",
                "message": "I couldn't find compatible motherboard recommendations in the current catalog.",
                "cpu": cpu,
                "recommendations": recommendations
            }

        return {
            "status": "success",
            "cpu": cpu,
            "recommendations": recommendations
        }

    def get_related_products(self, product_name: str) -> dict:
        """
        Finds related products based on series or chipset.
        """
        logger.info(f"Finding related products for: {product_name}")
        res = self.search_service.search_product(product_name)
        if res["status"] not in ["exact_match", "likely_match"]:
            return {"status": "error", "message": "Product not found or ambiguous."}
            
        product = res["product"]
        series = product.get("series")
        chipset = product.get("chipset")
        category = product.get("category")
        
        related = []
        for item in self.search_service.catalog:
            if item.get("id") == product.get("id"):
                continue
                
            # Match by series (e.g. other ROG boards)
            if series and item.get("series") == series and item.get("category") == category:
                related.append(item)
            # Or match by chipset if no series
            elif chipset and not series and item.get("chipset") == chipset:
                related.append(item)
                
        # Return top 5 related
        return {
            "status": "success",
            "base_product": product,
            "related_products": related[:5]
        }
