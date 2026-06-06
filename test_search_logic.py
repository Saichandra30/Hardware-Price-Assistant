from services.search_service import SearchService
from rapidfuzz import fuzz, process

svc = SearchService()
choices = [f"{item.get('brand', '')} {item['product_name']}".strip() for item in svc.catalog]

res = process.extract('amd 9700x', choices, scorer=fuzz.WRatio, limit=5)
print(res)
