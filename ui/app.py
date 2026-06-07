"""
Main UI module containing the Streamlit application layout and logic.
"""

import streamlit as st
import pandas as pd
from llm.hybrid_client import HybridClient

# ─────────────────────────────────────────────
# UI Component Renderers
# ─────────────────────────────────────────────

def render_product_card(product: dict) -> None:
    """Renders a single product inside a collapsible card."""
    name = product.get('product_name', 'Unknown')
    brand = product.get('brand', 'Unknown')
    cat = product.get('category', 'Unknown')
    chipset = product.get('chipset', '')
    series = product.get('series', '')

    label = f"📦 {brand} {name}"
    if chipset:
        label += f" [{chipset}]"

    with st.expander(label):
        cols = st.columns([1, 1])
        with cols[0]:
            st.markdown(f"**Brand:** {brand}")
            st.markdown(f"**Category:** {cat}")
        with cols[1]:
            if chipset:
                st.markdown(f"**Chipset:** {chipset}")
            if series:
                st.markdown(f"**Series:** {series}")

        # FIX: catalog stores prices under "prices" key, not "price_data"
        prices = product.get('prices') or product.get('price_data') or {}
        valid_prices = {k: v for k, v in prices.items() if v and float(v) > 0}

        if valid_prices:
            df = pd.DataFrame([
                {"Type": k.capitalize(), "Price (₹)": f"₹{v:,.0f}"}
                for k, v in valid_prices.items()
            ])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.caption("Pricing not available for this product.")


def render_comparison_table(res1: dict, res2: dict) -> None:
    """Renders a comparison table between two products."""
    p1 = res1.get("product") or (res1.get("suggestions", [None])[0] if res1.get("suggestions") else None)
    p2 = res2.get("product") or (res2.get("suggestions", [None])[0] if res2.get("suggestions") else None)

    if not p1 or not p2:
        st.warning("Comparison failed: Could not find one or both products.")
        return

    def get_min_price(p):
        prices = (p.get("prices") or p.get("price_data") or {})
        vals = [float(v) for v in prices.values() if v and float(v) > 0]
        return f"₹{min(vals):,.0f}" if vals else "N/A"

    data = [
        {"Feature": "Product",       p1["product_name"]: p1["product_name"],       p2["product_name"]: p2["product_name"]},
        {"Feature": "Brand",         p1["product_name"]: p1.get("brand", ""),       p2["product_name"]: p2.get("brand", "")},
        {"Feature": "Category",      p1["product_name"]: p1.get("category", ""),    p2["product_name"]: p2.get("category", "")},
        {"Feature": "Chipset",       p1["product_name"]: p1.get("chipset", "—"),    p2["product_name"]: p2.get("chipset", "—")},
        {"Feature": "Series",        p1["product_name"]: p1.get("series", "—"),     p2["product_name"]: p2.get("series", "—")},
        {"Feature": "Starting Price",p1["product_name"]: get_min_price(p1),         p2["product_name"]: get_min_price(p2)},
    ]
    st.table(data)


def render_recommendations(recs: dict) -> None:
    """Renders a row of recommendation tier cards."""
    st.markdown("### 💡 Recommended Pairings")
    tier_icons = {
        "Recommended Premium Choice": "🥇",
        "Recommended Performance Choice": "🥈",
        "Recommended Value Choice": "🥉",
    }
    
    # Validation: Confirm recommended product exists in the catalog database.
    from services.catalog_loader import get_catalog
    catalog = get_catalog()
    catalog_ids = {p.get("id") for p in catalog if p.get("id")}
    
    valid_recs = {}
    for k, v in recs.items():
        if v and v.get("id") in catalog_ids:
            valid_recs[k] = v
        else:
            # Reject recommendations not in catalog database
            pass
            
    if not valid_recs:
        st.info("No compatible recommendations found for this product.")
        return
    cols = st.columns(len(valid_recs))
    for idx, (tier, mb) in enumerate(valid_recs.items()):
        icon = tier_icons.get(tier, "⭐")
        with cols[idx]:
            st.markdown(f"**{icon} {tier}**")
            render_product_card(mb)


def render_catalog_stats(data: dict) -> None:
    """Renders catalog statistics as metrics + brand list."""
    if not data or data.get("error"):
        st.warning("Could not load catalog statistics.")
        return
    st.markdown("### 📊 Catalog Overview")
    total = data.get("total_products", 0)
    cats = data.get("category_counts", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Products", total)
    with col2:
        st.metric("Motherboards", cats.get("Motherboard", 0))
    with col3:
        st.metric("CPUs", cats.get("CPU", 0))
    brands = data.get("brands_available", [])
    if brands:
        st.markdown(f"**Available Brands:** {', '.join(brands)}")
    categories = data.get("categories", [])
    if categories:
        st.markdown(f"**Categories:** {', '.join(categories)}")


def render_tool_result(event: dict) -> None:
    """Parses tool results and renders rich UI components inline."""
    func = event.get("func_name")
    data = event.get("data") or {}

    if not data or data.get("error"):
        return  # Silently skip failed tool results

    if func in ["search_products", "lookup_product", "get_cheapest"]:
        # Exact / likely match → show single product card
        if data.get("status") in ["success", "exact_match", "likely_match"] and data.get("product"):
            render_product_card(data["product"])

        # Clarification / likely match → show suggestion list
        if data.get("status") in ["ask_clarification", "likely_match"] and data.get("suggestions"):
            st.markdown("**Matching products:**")
            for p in data["suggestions"][:10]:
                render_product_card(p)

    elif func == "compare_products":
        if data.get("status") == "success":
            st.markdown("### 📊 Product Comparison")
            render_comparison_table(
                data.get("product1_result", {}),
                data.get("product2_result", {})
            )

    elif func in ["filter_products", "find_alternatives", "get_related_products"]:
        results = data.get("results") or data.get("related_products") or []
        count = data.get("count", len(results))
        if results:
            st.markdown(f"**Showing {min(len(results), 10)} of {count} products:**")
            for p in results[:10]:
                render_product_card(p)
            if len(results) > 10:
                with st.expander(f"Show {len(results) - 10} more products"):
                    for p in results[10:]:
                        render_product_card(p)
        elif count == 0:
            st.info("No products found matching that filter.")

    elif func == "recommend_products":
        if data.get("status") == "success":
            render_recommendations(data.get("recommendations", {}))

    elif func == "get_catalog_stats":
        render_catalog_stats(data)


# ─────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────

def run_app() -> None:
    """Renders the main Streamlit application."""
    st.title("💻 Hardware Price Assistant")

    HISTORY_FILE = "data/chat_history.json"

    def save_history():
        import os, json
        os.makedirs("data", exist_ok=True)
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.messages, f, indent=2)
        except Exception:
            pass

    def load_history():
        import os, json
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    # ── Session State Init ──
    if "messages" not in st.session_state:
        loaded = load_history()
        if loaded:
            st.session_state.messages = loaded
        else:
            greeting = (
                "Welcome to **Hardware Price Assistant**! 👋\n\n"
                "I can help you find:\n"
                "• 💰 CPU & motherboard prices\n"
                "• 📊 Product comparisons\n"
                "• 💡 Build recommendations\n"
                "• 🔍 Cheapest options\n\n"
                "**Try asking:**\n"
                "> `9700X` · `ROG motherboard` · `Best board for 9800X3D` · `MSI boards under 20k`"
            )
            st.session_state.messages = [{"role": "assistant", "content": greeting}]

    if "client" not in st.session_state:
        try:
            st.session_state.client = HybridClient()
            if len(st.session_state.messages) > 1:
                abstract_hist = []
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        abstract_hist.append({"role": "user", "content": msg["content"]})
                    elif msg["role"] == "assistant" and msg.get("content") and not msg["content"].startswith("Welcome"):
                        abstract_hist.append({
                            "role": "assistant",
                            "content": msg["content"],
                            "components": msg.get("components", [])
                        })
                st.session_state.client.load_memory(abstract_hist)
        except Exception as e:
            st.error(f"Failed to initialize AI Client: {e}. Please check your API key in .env.")
            return

    # ── Sidebar ──
    with st.sidebar:
        st.title("⚙️ Settings")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = [{"role": "assistant", "content": "Chat cleared. How can I help?"}]
            save_history()
            if "client" in st.session_state:
                st.session_state.client.reset_memory()
            st.rerun()

        st.divider()
        st.markdown("### 💡 Try asking:")
        examples = [
            "What is the cheapest AM5 motherboard?",
            "Compare 9600X and 9700X",
            "What motherboard do you recommend for a 9800X3D?",
            "Show me all MSI B850 motherboards.",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.trigger_query = ex
                st.rerun()

    # ── Chat History Render ──
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("content"):
                st.markdown(msg["content"])
            if "components" in msg:
                for comp in msg["components"]:
                    if comp.get("type") == "tool_result":
                        try:
                            render_tool_result(comp)
                        except Exception:
                            pass  # Never crash while replaying history

    # ── Chat Input ──
    query_raw = st.chat_input("Ask about hardware prices, comparisons, or recommendations...")
    if getattr(st.session_state, "trigger_query", None):
        query_raw = st.session_state.trigger_query
        st.session_state.trigger_query = None

    if query_raw:
        query = str(query_raw).strip()
        if len(query) > 500:
            st.warning("Your query was truncated to 500 characters.")
            query = query[:500]

        st.session_state.messages.append({"role": "user", "content": query})
        save_history()
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            components_to_save = []
            final_text = ""

            try:
                with st.status("Analyzing request...", expanded=True) as status_box:
                    for event in st.session_state.client.generate_response_stream(query):
                        try:
                            if event["type"] == "status":
                                status_box.update(label=event["data"])
                                st.write(f"⚙️ {event['data']}")
                            elif event["type"] == "tool_result":
                                components_to_save.append(event)
                                st.write("✅ Data retrieved.")
                            elif event["type"] == "error":
                                st.error("An internal error occurred. Please try again.")
                            elif event["type"] == "text":
                                final_text = event.get("data") or ""
                                status_box.update(
                                    label="Response ready ✓",
                                    state="complete",
                                    expanded=False
                                )
                        except Exception as ev_err:
                            import logging
                            logging.getLogger(__name__).warning(f"Event render error: {ev_err}")

                # Render tool result cards
                for comp in components_to_save:
                    try:
                        render_tool_result(comp)
                    except Exception:
                        pass

                # Render final text — always show something
                if final_text and str(final_text).strip():
                    st.markdown(final_text)
                else:
                    st.warning(
                        "Sorry, I couldn't generate a response for that. "
                        "Please try rephrasing your request."
                    )
                    final_text = "Sorry, I couldn't generate a response. Please try rephrasing your request."

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_text,
                    "components": components_to_save
                })
                save_history()

            except Exception:
                st.error(
                    "An unexpected error occurred while processing your request. "
                    "Please try again."
                )


if __name__ == "__main__":
    run_app()
