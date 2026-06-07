"""
Definitions for the tools available to the LLM for catalog interaction.
"""
import re
import functools
from services.search_service import SearchService
from services.recommendation_service import RecommendationService


class ToolManager:
    """Manager for Gemini and Groq Function Calling Tools."""

    def __init__(self):
        self.search_service = SearchService()
        self.rec_service = RecommendationService()

    @functools.lru_cache(maxsize=128)
    def lookup_product(self, exact_name: str) -> dict:
        """Finds a product by its exact name. Use when you know the exact model name."""
        if not isinstance(exact_name, str):
            return {"error": "Invalid parameter type."}
        try:
            return self.search_service.exact_lookup(str(exact_name).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def search_products(self, query: str) -> dict:
        """
        Searches for a product using fuzzy matching.
        Use this for general product queries to find hardware availability and prices.
        """
        if not isinstance(query, str):
            return {"error": "Invalid parameter type."}
        try:
            return self.search_service.search_product(str(query).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def compare_products(self, product1: str, product2: str) -> dict:
        """Compares two products by finding their best matches in the catalog."""
        if not isinstance(product1, str) or not isinstance(product2, str):
            return {"error": "Invalid parameter types."}
        try:
            return self.search_service.compare_products(
                str(product1).strip()[:200], str(product2).strip()[:200]
            )
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def recommend_products(self, base_product: str) -> dict:
        """
        Recommends Premium, Performance, and Value motherboards for a given CPU.
        """
        if not isinstance(base_product, str):
            return {"error": "Invalid parameter type."}
        try:
            return self.rec_service.recommend_product(str(base_product).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def find_alternatives(self, product_name: str) -> dict:
        """Finds alternatives in the same category and chipset as the given product."""
        if not isinstance(product_name, str):
            return {"error": "Invalid parameter type."}
        try:
            res = self.search_service.search_product(str(product_name).strip()[:200])
            if res["status"] in ["exact_match", "likely_match"]:
                cat = res["product"].get("category")
                chip = res["product"].get("chipset")
                return self.search_service.filter_products(category=cat, chipset=chip)
            return {"error": "Product not found to find alternatives for."}
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def get_related_products(self, product_name: str) -> dict:
        """Finds related products based on product hierarchy (e.g. same series)."""
        if not isinstance(product_name, str):
            return {"error": "Invalid parameter type."}
        try:
            return self.rec_service.get_related_products(str(product_name).strip()[:200])
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def get_catalog_stats(self, query: str = "") -> dict:
        """
        Returns summary statistics about the catalog: total products, brands, categories.
        """
        try:
            catalog = self.search_service.catalog
            brands = sorted(list({item.get("brand") for item in catalog if item.get("brand")}))
            categories = sorted(list({item.get("category") for item in catalog if item.get("category")}))
            category_counts = {}
            for item in catalog:
                cat = item.get("category")
                if cat:
                    category_counts[cat] = category_counts.get(cat, 0) + 1
            return {
                "total_products": len(catalog),
                "brands_available": brands,
                "categories": categories,
                "category_counts": category_counts
            }
        except Exception:
            return {"error": "Internal processing error."}

    @functools.lru_cache(maxsize=128)
    def get_cheapest(self, category: str) -> dict:
        """Gets the cheapest product in a specific category or chipset."""
        if not isinstance(category, str):
            return {"error": "Invalid parameter type."}
        try:
            return self.search_service.get_cheapest(str(category).strip()[:100])
        except Exception:
            return {"error": "Internal processing error."}

    def filter_products(
        self,
        category: str = None,
        brand: str = None,
        chipset: str = None,
        max_price: float = None,
        sub_category: str = None,
        series: str = None,
        name_contains: str = None
    ) -> dict:
        """
        Filters products based on specific criteria.
        Supports: category, brand, chipset, max_price, sub_category, series, name_contains.
        """
        try:
            return self.search_service.filter_products(
                category=category,
                brand=brand,
                chipset=chipset,
                max_price=max_price,
                sub_category=sub_category,
                series=series,
                name_contains=name_contains
            )
        except Exception:
            return {"error": "Internal processing error."}

    def get_callable_tools(self) -> list:
        """Returns a list of callable tool functions."""
        return [
            self.lookup_product,
            self.search_products,
            self.compare_products,
            self.recommend_products,
            self.find_alternatives,
            self.get_related_products,
            self.get_catalog_stats,
            self.get_cheapest,
            self.filter_products
        ]

    def get_groq_tools(self) -> list:
        """Returns the JSON schema definitions for Groq function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_product",
                    "description": "Finds a product by its exact name. Use when you know the exact model name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "exact_name": {
                                "type": "string",
                                "description": "The exact name of the product."
                            }
                        },
                        "required": ["exact_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "Searches for a product. Use this for general product queries to find hardware availability and prices.",
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
                    "name": "recommend_products",
                    "description": "Recommends Premium, Performance, and Value motherboards for a given CPU.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_product": {
                                "type": "string",
                                "description": "The name of the CPU (e.g. '9700X', '9800X3D')."
                            }
                        },
                        "required": ["base_product"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_alternatives",
                    "description": "Finds alternative products in the same category and chipset.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name": {
                                "type": "string",
                                "description": "The name of the product to find alternatives for."
                            }
                        },
                        "required": ["product_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_related_products",
                    "description": "Finds related products based on product hierarchy and series.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name": {
                                "type": "string",
                                "description": "The name of the product to find related items for."
                            }
                        },
                        "required": ["product_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_catalog_stats",
                    "description": "Returns summary statistics about the catalog including total products, available brands, and categories.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cheapest",
                    "description": "Gets the cheapest product in a specific category or chipset. Use for 'cheapest', 'lowest price' queries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The category/chipset to search (e.g. 'motherboard', 'cpu', 'B850', 'am5 motherboard')."
                            }
                        },
                        "required": ["category"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_products",
                    "description": (
                        "Filters products by multiple criteria. Use for queries like "
                        "'MSI boards under 20000', 'ASUS gaming motherboards', "
                        "'WiFi boards under 25000', 'B850 boards under 20000'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Product category: 'Motherboard' or 'CPU'."
                            },
                            "brand": {
                                "type": "string",
                                "description": "Brand name: 'ASUS', 'MSI', 'AMD'."
                            },
                            "chipset": {
                                "type": "string",
                                "description": "Chipset: 'B850', 'X870', 'X870E', 'B840'."
                            },
                            "max_price": {
                                "type": "number",
                                "description": "Maximum dealer price in Indian Rupees (e.g. 20000)."
                            },
                            "sub_category": {
                                "type": "string",
                                "description": "Sub-category filter: 'Gaming', 'Mainstream', 'Professional'."
                            },
                            "series": {
                                "type": "string",
                                "description": "Product series filter: 'ROG', 'TUF', 'PRIME', 'PRO'."
                            },
                            "name_contains": {
                                "type": "string",
                                "description": (
                                    "Filter by keyword in product name. "
                                    "Use 'WIFI' for WiFi boards, 'GAMING' for gaming boards."
                                )
                            }
                        },
                        "required": []
                    }
                }
            }
        ]
