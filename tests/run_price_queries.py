import sys, io, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
warnings.filterwarnings('ignore')

from services.router import FastIntentRouter
from services.search_service import SearchService

search = SearchService()
router = FastIntentRouter(search)

# Standard Price Filtering Queries (First batch)
PRICE_QUERIES = [
    "Show MSI boards under 20000",
    "Show ASUS boards under 30000",
    "Gaming boards under 25000",
    "WiFi boards under 20000",
    "Cheapest motherboard",
]

# Real-World User style Queries (Second batch)
REAL_WORLD_QUERIES = [
    ("Need good board for 9700x", "LLM", "Should recommend base CPU recommendations"),
    ("best rog board", "LLM", "Should recommend top ROG options via LLM"),
    ("msi wifi motherboard around 20k", "router_filter", "Should filter MSI WiFi boards near 20k"),
    ("9700x motherboard combo", "LLM", "Should recommend CPU + MB combinations"),
    ("budget motherboard for gaming", "LLM", "Should recommend value-oriented gaming motherboard"),
    ("which board should i buy", "router_bypass", "Should ask follow-up questions directly"),
    ("show premium options", "LLM", "Should query premium chipsets/products"),
    ("rog under 30k", "router_filter", "Should filter ROG series under 30k"),
    ("top motherboard for ryzen", "LLM", "Should recommend Ryzen-compatible motherboard"),
    ("what do you recommend", "router_bypass", "Should ask clarifying questions directly"),
]

def fmt_prices(product: dict) -> str:
    prices = product.get("prices", {})
    valid  = {k: v for k, v in prices.items() if v and float(v) > 0}
    if not valid:
        return "N/A"
    return "  |  ".join(f"{k}: Rs{v:,.0f}" for k, v in sorted(valid.items()))

def get_min_price(product: dict) -> float:
    prices = [p for p in product.get("prices", {}).values() if p > 0]
    return min(prices) if prices else float('inf')

print("=" * 80)
print("  BATCH 1: PRICE-FILTERING QUERY TESTS")
print("=" * 80)

PASS = 0
FAIL = 0
issues = []

for q in PRICE_QUERIES:
    print(f"\nQUERY: \"{q}\"")
    print("─" * 80)
    route = router.route_query(q)
    if route:
        tool = route.get("tool")
        args = route.get("args", {})
        print(f"  [ROUTER]  Routes to: {tool} (args={args})")
        if tool == "filter_products":
            res = search.filter_products(
                category=args.get("category"),
                brand=args.get("brand"),
                chipset=args.get("chipset"),
                max_price=args.get("max_price"),
                sub_category=args.get("sub_category"),
                series=args.get("series"),
                name_contains=args.get("name_contains")
            )
            count = res.get("count", 0)
            products = res.get("results", [])
            print(f"  [EXECUTION] filter_products returned {count} results.")
            
            ok = True
            max_price_limit = args.get("max_price")
            for p in products:
                price = get_min_price(p)
                if max_price_limit and price > max_price_limit:
                    ok = False
                    print(f"    FAIL: Product {p.get('brand')} {p.get('product_name')} price {price} exceeds limit {max_price_limit}")
                if args.get("brand") and p.get("brand", "").upper() != args.get("brand").upper():
                    ok = False
                    print(f"    FAIL: Product {p.get('brand')} {p.get('product_name')} brand mismatch for {args.get('brand')}")
                if args.get("sub_category") and p.get("sub_category", "").upper() != args.get("sub_category").upper():
                    ok = False
                    print(f"    FAIL: Product {p.get('brand')} {p.get('product_name')} sub_category mismatch for {args.get('sub_category')}")
                if args.get("name_contains") and args.get("name_contains").upper() not in p.get("product_name", "").upper():
                    # Handle WiFi variations
                    name_upper = p.get("product_name", "").upper()
                    if args.get("name_contains").upper() == "WIFI" and any(x in name_upper for x in ["WIFI", "WI-FI", "WIIF", "WI FI"]):
                        pass
                    else:
                        ok = False
                        print(f"    FAIL: Product {p.get('brand')} {p.get('product_name')} does not contain keyword {args.get('name_contains')}")
            
            if count > 0 and ok:
                print(f"  [VERDICT] PASS")
                PASS += 1
                for p in products[:3]:
                    print(f"    • {p.get('brand')} {p.get('product_name')} | {fmt_prices(p)}")
            else:
                print(f"  [VERDICT] FAIL")
                FAIL += 1
                issues.append(f"Query '{q}' failed: got {count} products, validation={'PASS' if ok else 'FAIL'}")
        elif tool == "get_cheapest":
            res = search.get_cheapest(category=args.get("category"), brand=args.get("brand"), chipset=args.get("chipset"))
            status = res.get("status")
            if status == "success":
                p = res["product"]
                print(f"  [VERDICT] PASS")
                PASS += 1
                print(f"    • Cheapest: {p.get('brand')} {p.get('product_name')} | {fmt_prices(p)}")
            else:
                print(f"  [VERDICT] FAIL")
                FAIL += 1
                issues.append(f"Query '{q}' failed: get_cheapest status={status}")
    else:
        print("  [ROUTER]  None (Sent to LLM)")
        FAIL += 1
        issues.append(f"Query '{q}' did not route (returned None)")

print("\n" + "=" * 80)
print("  BATCH 2: REAL-WORLD USER QUERIES")
print("=" * 80)

for q, expected_behavior, desc in REAL_WORLD_QUERIES:
    print(f"\nQUERY: \"{q}\" ({desc})")
    print("─" * 80)
    route = router.route_query(q)
    
    if expected_behavior == "LLM":
        if route is None:
            print(f"  [VERDICT] PASS (fell through to LLM as expected)")
            PASS += 1
        else:
            print(f"  [VERDICT] FAIL (routed to {route.get('tool')} but expected LLM)")
            FAIL += 1
            issues.append(f"Query '{q}' routed to tool {route.get('tool')} instead of falling through to LLM")
            
    elif expected_behavior == "router_bypass":
        if route and route.get("bypassed") and "context" in route.get("text", "").lower():
            print(f"  [VERDICT] PASS (bypassed with clarifying question text)")
            PASS += 1
            print(f"    Response: {route.get('text')[:120]}...")
        else:
            print(f"  [VERDICT] FAIL (expected router bypass text, got {route})")
            FAIL += 1
            issues.append(f"Query '{q}' failed to bypass with clarifying context questions")
            
    elif expected_behavior == "router_filter":
        if route and route.get("tool") == "filter_products":
            args = route.get("args", {})
            res = search.filter_products(
                category=args.get("category"),
                brand=args.get("brand"),
                chipset=args.get("chipset"),
                max_price=args.get("max_price"),
                sub_category=args.get("sub_category"),
                series=args.get("series"),
                name_contains=args.get("name_contains")
            )
            count = res.get("count", 0)
            print(f"  [EXECUTION] filter_products with args={args} returned {count} results.")
            # For "rog under 30k", count should be 0 because all ROG boards in catalog are > 30k.
            expected_count_ok = (count == 0) if "rog under" in q.lower() else (count > 0)
            if expected_count_ok:
                print(f"  [VERDICT] PASS")
                PASS += 1
                for p in res.get("results", [])[:3]:
                    print(f"    • {p.get('brand')} {p.get('product_name')} | {fmt_prices(p)}")
            else:
                print(f"  [VERDICT] FAIL (got {count} results)")
                FAIL += 1
                issues.append(f"Query '{q}' returned unexpected number of products: {count}")
        else:
            print(f"  [VERDICT] FAIL (expected router_filter, got {route})")
            FAIL += 1
            issues.append(f"Query '{q}' failed to route to filter_products")

print("\n" + "=" * 80)
print(f"  FINAL SUMMARY: {PASS} PASSED  |  {FAIL} FAILED")
if issues:
    print("\n  FAILURES:")
    for iss in issues:
        print(f"    {iss}")
print("=" * 80)
