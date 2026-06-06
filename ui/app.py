"""
Main UI module containing the Streamlit application layout and logic.
"""

import streamlit as st
import pandas as pd
from llm.hybrid_client import HybridClient

def render_product_card(product: dict) -> None:
    """Renders a single product inside an expander card."""
    name = product.get('product_name', 'Unknown')
    brand = product.get('brand', 'Unknown')
    cat = product.get('category', 'Unknown')
    chipset = product.get('chipset', '')
    
    label = f"📦 {brand} {name}"
    if chipset:
        label += f" ({chipset})"
        
    with st.expander(label):
        st.markdown(f"**Category:** {cat}  |  **Brand:** {brand}")
        prices = product.get('price_data', {})
        if prices:
            df = pd.DataFrame([{"Vendor/Type": k, "Price (₹)": v} for k, v in prices.items()])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info("No pricing data available.")

def render_comparison_table(res1: dict, res2: dict) -> None:
    """Renders a comparison table between two products."""
    p1 = res1.get("product") or (res1.get("suggestions", [None])[0] if res1.get("suggestions") else None)
    p2 = res2.get("product") or (res2.get("suggestions", [None])[0] if res2.get("suggestions") else None)
    
    if not p1 or not p2:
        st.warning("Comparison failed: Could not find one or both products.")
        return
        
    def get_min_price(p):
        prices = [v for v in p.get("price_data", {}).values() if pd.notna(v)]
        return f"₹{min(prices):,.2f}" if prices else "N/A"
        
    data = [
        {"Feature": "Product", p1["product_name"]: p1["product_name"], p2["product_name"]: p2["product_name"]},
        {"Feature": "Brand", p1["product_name"]: p1.get("brand", ""), p2["product_name"]: p2.get("brand", "")},
        {"Feature": "Category", p1["product_name"]: p1.get("category", ""), p2["product_name"]: p2.get("category", "")},
        {"Feature": "Chipset", p1["product_name"]: p1.get("chipset", ""), p2["product_name"]: p2.get("chipset", "")},
        {"Feature": "Starting Price", p1["product_name"]: get_min_price(p1), p2["product_name"]: get_min_price(p2)},
    ]
    st.table(data)

def render_recommendations(recs: dict) -> None:
    """Renders a row of recommendations."""
    st.markdown("### 💡 Recommended Pairings")
    cols = st.columns(3)
    for idx, (tier, mb) in enumerate(recs.items()):
        if mb:
            with cols[idx % 3]:
                st.markdown(f"**{tier}**")
                render_product_card(mb)

def render_tool_result(event: dict) -> None:
    """Parses tool results and renders rich UI components inline."""
    func = event.get("func_name")
    data = event.get("data", {})
    
    if func in ["search_products", "lookup_product", "get_cheapest"]:
        if data.get("status") in ["success", "exact_match", "likely_match"] and data.get("product"):
            render_product_card(data["product"])
            
    elif func == "compare_products":
        if data.get("status") == "success":
            st.markdown("### 📊 Product Comparison")
            render_comparison_table(data.get("product1_result", {}), data.get("product2_result", {}))
            
    elif func in ["filter_products", "find_alternatives", "get_related_products"]:
        results = data.get("results", []) or data.get("related_products", [])
        if results:
            st.markdown(f"**Found {len(results)} products:**")
            for p in results[:5]:  # limit to 5 to avoid UI spam
                render_product_card(p)
            if len(results) > 5:
                st.caption(f"...and {len(results)-5} more.")
                
    elif func == "recommend_products":
        if data.get("status") == "success":
            render_recommendations(data.get("recommendations", {}))

def run_app() -> None:
    """Renders the main Streamlit application."""
    st.title("💻 Hardware Price Assistant")
    
    # Initialize session state
    if "messages" not in st.session_state:
        greeting = (
            "Hello 👋\n\n"
            "Welcome to Hardware Price Assistant.\n\n"
            "I can help you find:\n"
            "• CPU prices\n"
            "• Motherboard prices\n"
            "• Product comparisons\n"
            "• Recommendations\n"
            "• Cheapest options\n\n"
            "Try asking:\n"
            "\"9700X\"\n"
            "\"ROG motherboard\"\n"
            "\"Best board for 9700X\"\n"
            "\"Show MSI boards under 20k\""
        )
        st.session_state.messages = [
            {"role": "assistant", "content": greeting}
        ]
        
    if "client" not in st.session_state:
        try:
            st.session_state.client = HybridClient()
        except Exception as e:
            st.error(f"Failed to initialize AI Client: {e}. Please check your API key in .env.")
            return

    # Sidebar settings and examples
    with st.sidebar:
        st.title("⚙️ Settings")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = [
                {"role": "assistant", "content": "Chat cleared. How can I help?"}
            ]
            if "client" in st.session_state:
                st.session_state.client.reset_memory()
            st.rerun()
            
        st.divider()
        st.markdown("### 💡 Try asking:")
        examples = [
            "What is the cheapest AM5 motherboard?",
            "Compare 9600X and 9700X",
            "What motherboard do you recommend for a 9800X3D?",
            "Show me all MSI B850 motherboards."
        ]
        
        # When clicked, we inject the query into session state to run immediately
        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.trigger_query = ex
                st.rerun()

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if "content" in msg and msg["content"]:
                st.markdown(msg["content"])
            if "components" in msg:
                for comp in msg["components"]:
                    if comp["type"] == "tool_result":
                        render_tool_result(comp)

    query_raw = st.chat_input("Ask about hardware prices, comparisons, or recommendations...")
    if getattr(st.session_state, "trigger_query", None):
        query_raw = st.session_state.trigger_query
        st.session_state.trigger_query = None

    if query_raw:
        # Input validation and sanitization
        query = str(query_raw).strip()
        if len(query) > 500:
            st.warning("Your query was truncated to 500 characters.")
            query = query[:500]
            
        # Add user message
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)
            
        # Generate Assistant response
        with st.chat_message("assistant"):
            components_to_save = []
            final_text = ""
            
            try:
                with st.status("Analyzing request...", expanded=True) as status_box:
                    for event in st.session_state.client.generate_response_stream(query):
                        if event["type"] == "status":
                            status_box.update(label=event["data"])
                            st.write(f"⚙️ {event['data']}")
                        elif event["type"] == "tool_result":
                            components_to_save.append(event)
                            st.write("✅ Data retrieved.")
                        elif event["type"] == "error":
                            st.error("An internal error occurred. Please try again.")
                        elif event["type"] == "text":
                            final_text = event["data"]
                            status_box.update(label="Response generated", state="complete", expanded=False)
                
                # Render tool results visually
                for comp in components_to_save:
                    render_tool_result(comp)
                    
                # Render final text
                if final_text:
                    st.markdown(final_text)
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_text,
                    "components": components_to_save
                })
            except Exception as e:
                # Do not leak internal exception details to the UI
                st.error("An unexpected error occurred while processing your request. Please try again.")

if __name__ == "__main__":
    run_app()
