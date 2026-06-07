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
        if query_clean in ["top products", "best products", "recommendations",
                           "best motherboards", "best cpus"]:
            return {
                "bypassed": True,
                "text": (
                    "To give you the best recommendations, I need a bit more context! "
                    "Are you looking for the best **CPU**, the best **Motherboard** "
                    "for a specific processor, or something else?"
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

        # 9. Alias match → search_products
        for alias in self.search_service.alias_index:
            if alias == query_clean:
                return {"tool": "search_products", "args": {"query": query}}
        
        logger.info(f"Router did not find deterministic match for: {query!r}")
        return None
