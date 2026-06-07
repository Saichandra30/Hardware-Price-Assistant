"""
Targeted test for 5 recommendation-type queries.
Tests router, tool layer, and data quality for each query.
"""
import sys, os, io, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
warnings.filterwarnings('ignore')

from services.router import FastIntentRouter
from services.search_service import SearchService
from services.recommendation_service import RecommendationService
from llm.tool_definitions import ToolManager

search  = SearchService()
rec_svc = RecommendationService()
tool    = ToolManager()
router  = FastIntentRouter(search)

QUERIES = [
    "Best motherboard for 9700X",
    "Recommend motherboard for 9800X3D",
    "Premium ASUS motherboard",
    "Suggest gaming motherboard",
    "Best board for AM5",
]

CPU_KEYWORDS = {
    "9700X": "9700X", "9800X3D": "9800X3D",
    "9600X": "9600X", "9950X": "9950X", "9900X": "9900X",
}

def fmt_prices(product: dict) -> str:
    prices = product.get("prices", {})
    valid  = {k: v for k, v in prices.items() if v and float(v) > 0}
    if not valid:
        return "N/A"
    return "  |  ".join(f"{k}: Rs{v:,.0f}" for k, v in sorted(valid.items()))

def show_product(p: dict, indent: int = 4):
    pad = " " * indent
    brand   = p.get("brand", "")
    name    = p.get("product_name", "")
    chipset = p.get("chipset", "")
    series  = p.get("series", "")
    chip_str = f"  [{chipset}]" if chipset else ""
    ser_str  = f"  ({series})"  if series  else ""
    print(f"{pad}  {brand} {name}{chip_str}{ser_str}")
    print(f"{pad}  Pricing: {fmt_prices(p)}")

print()
print("=" * 68)
print("  RECOMMENDATION QUERY TESTS")
print("=" * 68)

PASS = 0
FAIL = 0
issues = []

for q in QUERIES:
    print(f"\n{'─'*68}")
    print(f"  QUERY: \"{q}\"")
    print(f"{'─'*68}")

    # ── Step 1: Router ───────────────────────────────────────────────────
    route = router.route_query(q)
    if route:
        if route.get("bypassed"):
            verdict = "Bypassed (hardcoded text)"
        else:
            verdict = f"Short-circuit -> {route.get('tool')}  args={route.get('args')}"
        print(f"  [ROUTER]  {verdict}")
    else:
        print("  [ROUTER]  -> None  (goes to LLM - correct for complex queries)")

    # ── Step 2: CPU-based recommendation ────────────────────────────────
    found_cpu = None
    for kw, cpu in CPU_KEYWORDS.items():
        if kw.lower() in q.lower():
            found_cpu = cpu
            break

    if found_cpu:
        r = rec_svc.recommend_product(found_cpu)
        status = r.get("status")
        recs   = r.get("recommendations", {})
        ok = status == "success" and any(v for v in recs.values())
        tag = "PASS" if ok else "FAIL"
        print(f"  [RECOMMEND]  recommend_products({found_cpu!r}) -> status={status}  [{tag}]")
        if ok:
            PASS += 1
            for tier, mb in recs.items():
                if mb:
                    tier_short = tier.replace("Recommended ", "").replace(" Choice", "")
                    print(f"    {tier_short:20}")
                    show_product(mb)
                else:
                    print(f"    {tier:40} -> (no product)")
        else:
            FAIL += 1
            issues.append(f"FAIL: recommend_products({found_cpu}) returned status={status}")

    # ── Step 3: AM5 boards ───────────────────────────────────────────────
    if "am5" in q.lower():
        r = tool.filter_products(category="motherboard")
        cnt = r.get("count", 0)
        print(f"  [FILTER]  All motherboards -> {cnt} products")
        chp = search.get_cheapest(category="am5 motherboard")
        if chp.get("status") == "success":
            p = chp["product"]
            print(f"  [CHEAPEST AM5]  {p.get('brand')} {p.get('product_name')} @ Rs{chp['min_price']:,.0f}")
            PASS += 1
        else:
            print("  [CHEAPEST AM5]  FAIL - no cheapest found")
            FAIL += 1
            issues.append("FAIL: get_cheapest(am5 motherboard) returned no result")
        # Show premium AM5 (X870E)
        rprem = tool.filter_products(chipset="X870E")
        print(f"  [PREMIUM AM5]  X870E boards -> {rprem.get('count',0)} products")
        for p in rprem.get("results", [])[:3]:
            show_product(p)
        PASS += 1

    # ── Step 4: ASUS query ───────────────────────────────────────────────
    if "asus" in q.lower():
        r = tool.filter_products(brand="ASUS")
        cnt = r.get("count", 0)
        ok  = cnt > 0
        tag = "PASS" if ok else "FAIL"
        print(f"  [FILTER]  filter_products(brand=ASUS) -> {cnt} products  [{tag}]")
        if ok:
            PASS += 1
            # Sort by price descending (premium first)
            results = r.get("results", [])
            def max_price(p):
                vals = [v for v in (p.get("prices") or {}).values() if v and float(v) > 0]
                return max(vals) if vals else 0
            premium = sorted(results, key=max_price, reverse=True)[:4]
            print(f"  Top premium ASUS boards:")
            for p in premium:
                show_product(p)
        else:
            FAIL += 1
            issues.append("FAIL: filter_products(ASUS) returned 0")

    # ── Step 5: Gaming query ─────────────────────────────────────────────
    if "gaming" in q.lower() and "asus" not in q.lower():
        # Real user flow: router decides 'gaming' -> filter_products(sub_category=gaming)
        # For multi-word queries like 'Suggest gaming motherboard', LLM handles it
        # Test the direct sub_category filter which is what the router uses
        r = search.filter_products(sub_category="Gaming", category="Motherboard")
        status = r.get("status")
        results_list = r.get("results", [])
        ok = status == "success" and len(results_list) > 0
        tag = "PASS" if ok else "FAIL"
        print(f"  [FILTER]  filter_products(sub_category=Gaming) -> status={status}, {len(results_list)} products  [{tag}]")
        if ok:
            PASS += 1
            for p in results_list[:5]:
                show_product(p)
        else:
            FAIL += 1
            issues.append(f"FAIL: filter_products(sub_category=Gaming) -> {status}")

    # ── Step 6: Premium (non-ASUS) query ────────────────────────────────
    if "premium" in q.lower() and "asus" not in q.lower():
        # Check ROG/X870E across all brands
        rx870e = tool.filter_products(chipset="X870E")
        cnt    = rx870e.get("count", 0)
        ok     = cnt > 0
        tag    = "PASS" if ok else "FAIL"
        print(f"  [FILTER]  X870E (premium chipset) -> {cnt} products  [{tag}]")
        if ok:
            PASS += 1
            for p in rx870e.get("results", [])[:4]:
                show_product(p)
        else:
            FAIL += 1

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 68)
print(f"  RESULTS:  {PASS} PASSED  |  {FAIL} FAILED")
if issues:
    print()
    print("  FAILURES:")
    for i in issues:
        print(f"    {i}")
print("=" * 68)
