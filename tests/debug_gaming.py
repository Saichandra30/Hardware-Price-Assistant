import sys, io, warnings
sys.path.insert(0, '.')
warnings.filterwarnings('ignore')
from services.search_service import SearchService
from llm.tool_definitions import ToolManager

s = SearchService()
tool = ToolManager()

# What does 'gaming motherboard' return?
r = s.search_product('gaming motherboard')
print("status:", r.get('status'))
p = r.get('product', {})
print("matched product:", p.get('product_name'), "| score:", r.get('score'))
print("suggestions:", len(r.get('suggestions', [])))

# Inspect the exact match — it finds an exact product named with GAMING
# because 'gaming motherboard' alias points to 'GAMING' and fuzzy matches a board

print()
print("--- sub_category=Gaming boards ---")
cats = [p for p in s.catalog if p.get('sub_category','').upper() == 'GAMING']
print(f"Total Gaming sub_category: {len(cats)}")
for p in cats[:6]:
    name = p.get('product_name','')
    brand = p.get('brand','')
    chip = p.get('chipset','')
    print(f"  {brand} {name} [{chip}]")

print()
print("--- filter_products with 'gaming' series hint ---")
res = tool.filter_products(category="Motherboard")
gaming = [p for p in res.get('results',[]) if p.get('sub_category','').upper() == 'GAMING']
print(f"Motherboards with Gaming sub_category: {len(gaming)}")
for p in gaming[:5]:
    name = p.get('product_name','')
    brand = p.get('brand','')
    print(f"  {brand} {name}")
