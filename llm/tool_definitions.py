"""
Definitions for the tools available to the LLM for catalog interaction.
"""
from services.search_service import SearchService
from services.recommendation_service import RecommendationService

class ToolManager:
    """Manager for Gemini Function Calling Tools."""
    
    def __init__(self):
        self.search_service = SearchService()
        self.rec_service = RecommendationService()
        
    def exact_lookup(self, product_name: str) -> dict:
        """
        Finds a product by its exact name. Use when you know the exact model name.
        """
        if not isinstance(product_name, str):
            return {"error": "Invalid parameter type: product_name must be a string."}
        try:
            return self.search_service.exact_lookup(str(product_name).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    def search_product(self, query: str) -> dict:
        """
        Searches for a product using fuzzy matching. Use this for general product queries to find hardware availability and prices.
        """
        if not isinstance(query, str):
            return {"error": "Invalid parameter type: query must be a string."}
        try:
            return self.search_service.search_product(str(query).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    def compare_products(self, product1: str, product2: str) -> dict:
        """
        Compares two products by finding their best matches in the catalog.
        """
        if not isinstance(product1, str) or not isinstance(product2, str):
            return {"error": "Invalid parameter types: product names must be strings."}
        try:
            return self.search_service.compare_products(str(product1).strip()[:200], str(product2).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    def filter_products(self, category: str = "", brand: str = "", chipset: str = "", max_price: float = 0.0) -> dict:
        """
        Filters products based on specific criteria. Pass empty strings for unused string filters and 0.0 for unused price filter.
        """
        if not isinstance(category, str) or not isinstance(brand, str) or not isinstance(chipset, str) or not isinstance(max_price, (int, float)):
            return {"error": "Invalid parameter types."}
        try:
            ca = str(category).strip()[:50] if category else None
            b = str(brand).strip()[:100] if brand else None
            c = str(chipset).strip()[:50] if chipset else None
            m = float(max_price) if float(max_price) > 0 else None
            return self.search_service.filter_products(category=ca, brand=b, chipset=c, max_price=m)
        except Exception:
            return {"error": "Internal processing error."}

    def get_cheapest(self, category: str) -> dict:
        """
        Gets the cheapest product in a specific category (e.g., 'CPU' or 'Motherboard').
        """
        if not isinstance(category, str):
            return {"error": "Invalid parameter type: category must be a string."}
        try:
            return self.search_service.get_cheapest(str(category).strip()[:50])
        except Exception:
            return {"error": "Internal processing error."}

    def recommend_product(self, cpu_name: str) -> dict:
        """
        Recommends a Budget, Mid-range, and Premium motherboard for a given CPU.
        """
        if not isinstance(cpu_name, str):
            return {"error": "Invalid parameter type: cpu_name must be a string."}
        try:
            return self.rec_service.recommend_product(str(cpu_name).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}
        
    def get_callable_tools(self) -> list:
        """Returns a list of callable tool functions."""
        return [
            self.exact_lookup,
            self.search_product,
            self.compare_products,
            self.filter_products,
            self.get_cheapest,
            self.recommend_product
        ]

    def get_groq_tools(self) -> list:
        """Returns the JSON schema definitions for Groq function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "exact_lookup",
                    "description": "Finds a product by its exact name. Use when you know the exact model name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name": {
                                "type": "string",
                                "description": "The exact name of the product."
                            }
                        },
                        "required": ["product_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_product",
                    "description": "Searches for a product using fuzzy matching. Use this for general product queries to find hardware availability and prices.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query (e.g., '9600X' or 'MSI B850')."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_products",
                    "description": "Compares two products by finding their best matches in the catalog.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product1": {
                                "type": "string",
                                "description": "Name of the first product."
                            },
                            "product2": {
                                "type": "string",
                                "description": "Name of the second product."
                            }
                        },
                        "required": ["product1", "product2"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_products",
                    "description": "Filters products based on specific criteria. Omit fields you don't want to filter by.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The category name to filter by (e.g., 'CPU', 'Motherboard')."
                            },
                            "brand": {
                                "type": "string",
                                "description": "The brand name to filter by (e.g., 'MSI', 'AMD')."
                            },
                            "chipset": {
                                "type": "string",
                                "description": "The chipset to filter by (e.g., 'B850', 'X870')."
                            },
                            "max_price": {
                                "type": "number",
                                "description": "The maximum price limit."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cheapest",
                    "description": "Gets the cheapest product in a specific category (e.g., 'CPU' or 'Motherboard').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The category name (e.g., 'Motherboard' or 'CPU')."
                            }
                        },
                        "required": ["category"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "recommend_product",
                    "description": "Recommends a Budget, Mid-range, and Premium motherboard for a given CPU.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cpu_name": {
                                "type": "string",
                                "description": "The name of the CPU you need motherboard recommendations for."
                            }
                        },
                        "required": ["cpu_name"]
                    }
                }
            }
        ]
