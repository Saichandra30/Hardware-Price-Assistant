import re
import logging
from services.search_service import SearchService

logger = logging.getLogger(__name__)

class FastIntentRouter:
    """
    O(1) pre-LLM intent router to intercept basic search queries.
    If a query maps deterministically to a tool call without needing an LLM,
    this router returns the tool call parameters to execute it locally.
    
    Index routing priority:
        1. Product index  → search_products
        2. Brand index    → filter_products(brand=)
        3. Chipset index  → filter_products(chipset=)
        4. Category index → filter_products(category=)
        5. Alias index    → search_products
    """
    def __init__(self, search_service: SearchService):
        self.search_service = search_service
        
    def route_query(self, query: str) -> dict:
        """
        Returns a dict with 'tool' and 'args', or None if it needs the LLM.
        The 'tool_type' field in args hints to hybrid_client how to phrase the response.
        """
        query_clean = str(query).strip().lower()
        # Clean typos and key variations
        query_clean = query_clean.replace("morter", "mortar").replace("wiif", "wifi").replace("9700xx", "9700x")
        query_clean = re.sub(r'[^\w\s-]', '', query_clean).strip()
        
        # 1. Greetings → hardcoded bypass
        greetings = {"hi", "hello", "hey", "help", "start"}
        if query_clean in greetings:
            return {
                "bypassed": True,
                "text": (
                    "Hello! 👋 I'm the **Hardware Price Assistant**.\n\n"
                    "I can help you:\n"
                    "• Find CPU & motherboard prices\n"
                    "• Compare products side-by-side\n"
                    "• Get compatibility recommendations\n"
                    "• Filter by brand, chipset, or budget\n\n"
                    "Try asking: `9700X`, `ROG motherboards`, `B850 boards`, or "
                    "`best motherboard for 9800X3D`."
                )
            }
            
        # 2. Catalog stats
        stats_queries = {
            "how many products", "what products", "what categories",
            "what brands", "what do you sell", "inventory"
        }
        for sq in stats_queries:
            if sq in query_clean and len(query_clean) < 30:
                return {"tool": "get_catalog_stats", "args": {}}
                
        # 3. Generic top/best redirects
        generic_recs = {
            "top products", "best products", "recommendations",
            "best motherboards", "best cpus", "what do you recommend",
            "what should i buy", "which board should i buy",
            "recommend a board", "which motherboard should i buy",
            "which board to buy", "suggest a board", "suggest motherboard"
        }
        if query_clean in generic_recs:
            return {
                "bypassed": True,
                "text": (
                    "To give you the best recommendations, I need a bit more context! "
                    "Could you tell me:\n"
                    "1. Which **CPU** you are using (e.g., Ryzen 9700X, 9800X3D)?\n"
                    "2. What is your **budget** or price range (e.g., under 20k, around 30k)?\n"
                    "3. Do you have a preferred **brand** (ASUS or MSI)?"
                )
            }
            
        # 4. Cheapest queries
        cheap_match = re.search(
            r'cheapest\s+([a-zA-Z0-9\s-]+?)(?:\s+motherboard|\s+cpu|\s+board|\s+processor)?$',
            query_clean
        )
        if cheap_match:
            cat_query = cheap_match.group(1).strip()
            if cat_query == "am5":
                cat_query = "am5 motherboard"
            elif cat_query == "am4":
                cat_query = "am4 motherboard"
            return {"tool": "get_cheapest", "args": {"category": cat_query}}

        # Check if the query is a comparison, compatibility, or recommendation request, and if so let the LLM handle it.
        comparison_kws = {"vs", "compare", "comparison", "better", "choose", "worth"}
        compatibility_kws = {"compatible", "compatibility", "support", "supports", "pair", "pairs", "combo", "fit", "use"}
        recommendation_kws = {"best", "recommend", "recommendation", "recommendations", "suggest", "suggestion", "suggestions", "top", "budget"}
        query_words = set(query_clean.split())
        if query_words.intersection(comparison_kws) or query_words.intersection(compatibility_kws) or query_words.intersection(recommendation_kws):
            pass
        else:
            # 5b. Price-filtered queries: "MSI boards under 20000", "WiFi boards under 25k"
            price_match = re.search(
                r'(?:under|below|less than|max|upto|up to|around|approx|near|budget|for|at|within|of)\s*(?:rs\.?\s*|inr\s*)?\b(\d+)(?:k|000)?\b',
                query_clean
            )
            if price_match:
                raw_num = int(price_match.group(1))
                # Handle shorthand: if number < 1000, treat as thousands (e.g. "20k" = 20000)
                max_price = raw_num * 1000 if raw_num < 1000 else float(raw_num)

                # Extract brand, chipset, sub_category, name_contains from the rest of the query
                filter_args: dict = {"max_price": max_price, "tool_type": "price_filter"}

                q_stripped = price_match.string[:price_match.start()].strip()

                brand_map = {"msi": "MSI", "asus": "ASUS", "amd": "AMD"}
                for bkw, bval in brand_map.items():
                    if bkw in q_stripped:
                        filter_args["brand"] = bval
                        break

                chipset_patterns = ["x870e", "x870", "b850", "b840", "x670", "b650"]
                for cp in chipset_patterns:
                    if cp in q_stripped:
                        filter_args["chipset"] = cp.upper()
                        break

                series_map = {"rog": "ROG", "tuf": "TUF", "prime": "PRIME", "pro": "PRO"}
                for skw, sval in series_map.items():
                    if skw in q_stripped:
                        filter_args["series"] = sval
                        # Automatically map brand ASUS/MSI for series when possible
                        if sval in ["ROG", "TUF", "PRIME"]:
                            filter_args["brand"] = "ASUS"
                        elif sval == "PRO" and not filter_args.get("brand"):
                            # PRO series exist on MSI/ASUS, let it search generally unless brand is specified
                            pass
                        break

                if "wifi" in q_stripped:
                    filter_args["name_contains"] = "WIFI"

                if "gaming" in q_stripped:
                    filter_args["sub_category"] = "Gaming"

                # Always filter to motherboards for board/motherboard queries or ROG/TUF series motherboard queries
                if any(kw in q_stripped for kw in ["board", "motherboard", "mobo", "rog", "tuf", "prime"]):
                    filter_args["category"] = "Motherboard"

                return {"tool": "filter_products", "args": filter_args}

            # 4.5. List/Show query routing rule
            list_keywords = {"show", "list", "have", "all", "display", "view", "products", "boards", "motherboard", "motherboards", "mobo", "mobos", "cpu", "cpus", "processor", "processors", "options"}
            words = set(query_clean.split())
            if words.intersection(list_keywords):
                filter_args = {}
                
                # Brand extraction
                brand_map = {"msi": "MSI", "asus": "ASUS", "amd": "AMD"}
                for bkw, bval in brand_map.items():
                    if bkw in query_clean:
                        filter_args["brand"] = bval
                        break
                        
                # Chipset extraction
                chipset_patterns = ["x870e", "x870", "b850", "b840", "x670", "b650", "a620"]
                for cp in chipset_patterns:
                    if cp in query_clean:
                        filter_args["chipset"] = cp.upper()
                        break
                        
                # Series extraction
                series_map = {"rog": "ROG", "tuf": "TUF", "prime": "PRIME", "pro": "PRO", "proart": "PROART"}
                for skw, sval in series_map.items():
                    if re.search(r'\b' + re.escape(skw) + r'\b', query_clean):
                        filter_args["series"] = sval
                        if sval in ["ROG", "TUF", "PRIME", "PROART"]:
                            filter_args["brand"] = "ASUS"
                        break
                        
                # Category extraction
                if any(kw in query_clean for kw in ["board", "motherboard", "mobo", "boards", "motherboards", "mobos"]):
                    filter_args["category"] = "Motherboard"
                elif any(kw in query_clean for kw in ["cpu", "cpus", "processor", "processors"]):
                    filter_args["category"] = "CPU"

                if "wifi" in query_clean:
                    filter_args["name_contains"] = "WIFI"

                if "gaming" in query_clean:
                    filter_args["sub_category"] = "Gaming"
                    
                if any(k in filter_args for k in ["brand", "chipset", "series", "category", "name_contains", "sub_category"]):
                    filter_args["tool_type"] = "list"
                    return {"tool": "filter_products", "args": filter_args}

        # 5. Spaceless & hyphenless exact match check
        query_spaceless = query_clean.replace(" ", "").replace("-", "")
        # Build spaceless product map dynamically if needed (or cached)
        if not hasattr(self, "_spaceless_catalog_mtime") or self._spaceless_catalog_mtime != self.search_service.catalog_mtime:
            self._spaceless_product_index = {}
            for name_clean, item in self.search_service.product_index.items():
                spaceless_name = name_clean.replace(" ", "").replace("-", "")
                self._spaceless_product_index[spaceless_name] = item
            self._spaceless_catalog_mtime = self.search_service.catalog_mtime
            
        if query_spaceless in self._spaceless_product_index:
            matched_item = self._spaceless_product_index[query_spaceless]
            return {
                "tool": "search_products",
                "args": {"query": matched_item.get("product_name", query)}
            }

        # 5. Exact product name match → search_products
        if query_clean in self.search_service.product_index:
            return {"tool": "search_products", "args": {"query": query}}

        # 6. Brand match → filter_products(brand=)
        if query_clean in self.search_service.brand_index:
            return {
                "tool": "filter_products",
                "args": {"brand": query_clean, "tool_type": "brand"}
            }

        # 7. Chipset match → filter_products(chipset=)
        if query_clean in self.search_service.chipset_index:
            return {
                "tool": "filter_products",
                "args": {"chipset": query_clean, "tool_type": "chipset"}
            }

        # 8. Category match → filter_products(category=)
        if query_clean in self.search_service.category_index:
            return {
                "tool": "filter_products",
                "args": {"category": query_clean, "tool_type": "category"}
            }

        # 9. Series match → filter_products(series=)  e.g. "ROG", "TUF", "PRIME"
        if query_clean in self.search_service.series_index:
            return {
                "tool": "filter_products",
                "args": {"series": query_clean, "tool_type": "series"}
            }

        # 10. Sub-category match → filter_products(sub_category=)  e.g. "gaming", "mainstream"
        if query_clean in self.search_service.sub_category_index:
            return {
                "tool": "filter_products",
                "args": {"sub_category": query_clean, "tool_type": "sub_category"}
            }

        # 11. Alias match → search_products
        for alias in self.search_service.alias_index:
            if alias == query_clean:
                return {"tool": "search_products", "args": {"query": query}}
        
        logger.info(f"Router did not find deterministic match for: {query!r}")
        return None
