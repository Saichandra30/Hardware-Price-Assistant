import re
import logging
from services.search_service import SearchService

logger = logging.getLogger(__name__)

class FastIntentRouter:
    """
    O(1) pre-LLM intent router to intercept basic search queries.
    If a query maps deterministically to a tool call without needing an LLM,
    this router returns the tool call parameters to execute it locally.
    """
    def __init__(self, search_service: SearchService):
        self.search_service = search_service
        
    def route_query(self, query: str) -> dict:
        """
        Returns a dict with 'tool' and 'args', or None if it needs the LLM.
        """
        import re
        query_clean = str(query).strip().lower()
        query_clean = re.sub(r'[^\w\s-]', '', query_clean).strip()
        
        
        # 1. Check for basic greeting or conversational prompts
        greetings = {"hi", "hello", "hey", "help", "start"}
        if query_clean in greetings:
            return {
                "bypassed": True,
                "text": "Hello! 👋 I am the Hardware Price Assistant. I can help you find hardware prices, compare products, and give recommendations. Try asking me to find a '9700X' or 'show me ASUS motherboards'!"
            }
            
        # 2. Check catalog stats
        stats_queries = {"how many products", "what products", "what categories", "what brands", "what do you sell", "inventory"}
        for sq in stats_queries:
            if sq in query_clean and len(query_clean) < 30:
                return {
                    "tool": "get_catalog_stats",
                    "args": {}
                }
                
        # 3. Check for top/best products generic queries and recommendations
        import re
        rec_match = re.search(r'(?:best|top|recommend).*?(?:for|with)\s+a?\s*([a-zA-Z0-9\s-]+)', query_clean)
        if rec_match:
            target_cpu = rec_match.group(1).strip()
            # If they provided a CPU, pass it to the deterministic python tool
            return {
                "tool": "recommend_products",
                "args": {"base_product": target_cpu}
            }
            
        if query_clean in ["top products", "best products", "recommendations", "best motherboards", "best cpus"]:
            return {
                "bypassed": True,
                "text": "To give you the best recommendations, I need a little more context! Are you looking for the best CPU, the best Motherboard for a specific processor, or something else?"
            }
            
        # 4. Check for cheapest queries
        cheap_match = re.search(r'cheapest\s+([a-zA-Z0-9\s-]+?)(?:\s+motherboard|\s+cpu|\s+board|\s+processor)?$', query_clean)
        if cheap_match:
            cat_query = cheap_match.group(1).strip()
            if cat_query == "am5":
                cat_query = "am5 motherboard"
            elif cat_query == "am4":
                cat_query = "am4 motherboard"
                
            return {
                "tool": "get_cheapest",
                "args": {"category": cat_query}
            }

        # 6. Check for exact hardware matches in indices
        # We only want to trigger this if the query is EXACTLY the product name, 
        # or if it's very short. Otherwise, it intercepts things like "What is the price of Asus?"
        if query_clean in self.search_service.product_index:
            return {
                "tool": "search_products",
                "args": {"query": query_clean}
            }
            
        if query_clean in self.search_service.brand_index:
            return {
                "tool": "search_products",
                "args": {"query": query_clean}
            }
            
        if query_clean in self.search_service.chipset_index:
            return {
                "tool": "search_products",
                "args": {"query": query_clean}
            }
            
        if query_clean in self.search_service.category_index:
            return {
                "tool": "search_products",
                "args": {"query": query_clean}
            }
            
        for alias in self.search_service.alias_index:
            if alias == query_clean:
                return {
                    "tool": "search_products",
                    "args": {"query": query_clean}
                }
        
        logger.info(f"Router did not find deterministic match for: {query}")
        return None
