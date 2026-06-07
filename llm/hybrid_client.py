import logging
import json
import time
from llm.gemini_client import GeminiClient, RateLimitError
from llm.groq_client import GroqClient
from llm.tool_definitions import ToolManager
from services.router import FastIntentRouter

logger = logging.getLogger(__name__)

_FALLBACK_EMPTY = "Sorry, I couldn't generate a response for that. Please try rephrasing your request."
_FALLBACK_FORMAT = "I found matching data but couldn't format the response properly. Please try again."

class HybridClient:
    """
    Client that uses Groq by default for ultra-low latency, falling back to Gemini.
    Features a FastIntentRouter to short-circuit LLM calls completely for simple tasks.
    """
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.groq_client = GroqClient()
        self.tool_manager = ToolManager()
        self.router = FastIntentRouter(self.tool_manager.search_service)
        
        # We start with Groq for low latency
        self.active_backend = "groq"
        self.abstract_history = []
        
    def reset_memory(self):
        self.gemini_client.reset_memory()
        self.groq_client.reset_memory()
        self.abstract_history = []
        self.active_backend = "groq"
        logger.info("HybridClient memory reset.")

    def load_memory(self, abstract_history):
        self.abstract_history = abstract_history
        self.sync_history_to_groq()
        self.gemini_client.load_memory(abstract_history)
        logger.info("HybridClient memory loaded from history.")

    def sync_history_to_groq(self):
        logger.info("Syncing abstract history to Groq Client.")
        self.groq_client.reset_memory()
        for msg in self.abstract_history:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "user" and content:
                self.groq_client.messages.append({"role": "user", "content": content})
            elif role == "assistant" and content:
                self.groq_client.messages.append({"role": "assistant", "content": content})

    def _safe_text(self, text: str, fallback: str = _FALLBACK_EMPTY) -> str:
        """Return text if non-empty, else fallback."""
        if text and str(text).strip():
            return str(text).strip()
        return fallback

    def generate_response_stream(self, prompt: str):
        total_start_time = time.perf_counter()
        components_executed = []
        final_text = ""
        
        # Enforce history limit (last 6 exchanges = 12 messages)
        if len(self.abstract_history) > 12:
            self.abstract_history = self.abstract_history[-12:]
            self.sync_history_to_groq()
            self.gemini_client.load_memory(self.abstract_history)
            
        # Add to abstract history
        current_msg = {"role": "user", "content": prompt}
        self.abstract_history.append(current_msg)
        
        # ─────────────────────────────────────────────────
        # 1. Routing Phase
        # ─────────────────────────────────────────────────
        routing_start = time.perf_counter()
        try:
            route_decision = self.router.route_query(prompt)
        except Exception as e:
            logger.warning(f"Router failed: {e}. Falling through to LLM.")
            route_decision = None
        routing_time = time.perf_counter() - routing_start
        logger.info(f"[Latency] Routing completed in {routing_time:.4f}s")
        
        if route_decision:
            # ── Hardcoded bypass (greetings etc.) ──
            if route_decision.get("bypassed"):
                final_text = route_decision["text"]
                yield {"type": "text", "data": final_text}
                total_time = time.perf_counter() - total_start_time
                logger.info(f"[Latency] LLM Bypassed! Total time: {total_time:.4f}s")
                self.abstract_history.append({
                    "role": "assistant",
                    "content": final_text,
                    "components": components_executed
                })
                return
                
            # ── Tool short-circuit ──
            elif route_decision.get("tool"):
                tool_name = route_decision["tool"]
                args = route_decision.get("args", {})
                search_start = time.perf_counter()
                
                try:
                    if tool_name == "get_catalog_stats":
                        result = self.tool_manager.get_catalog_stats()
                        event = {"type": "tool_result", "func_name": "get_catalog_stats", "data": result}
                        components_executed.append(event)
                        yield event
                        total = result.get("total_products", 0)
                        brands = ", ".join(result.get("brands_available", []))
                        final_text = (
                            f"Here's a summary of our current hardware inventory — "
                            f"**{total} products** across brands: **{brands}**."
                        )

                    elif tool_name == "get_cheapest":
                        result = self.tool_manager.search_service.get_cheapest(args.get("category", ""))
                        event = {"type": "tool_result", "func_name": "get_cheapest", "data": result}
                        components_executed.append(event)
                        yield event
                        if result.get("status") == "success":
                            p = result["product"]
                            price = result.get("min_price", 0)
                            final_text = (
                                f"The cheapest option I found is the "
                                f"**{p.get('brand', '')} {p.get('product_name', '')}** "
                                f"at **₹{price:,.0f}**."
                            )
                        else:
                            final_text = (
                                f"I couldn't find any products in the "
                                f"**{args.get('category', 'requested')}** category. "
                                f"Try a different search."
                            )

                    elif tool_name == "search_products":
                        result = self.tool_manager.search_products(args.get("query", ""))
                        event = {"type": "tool_result", "func_name": "search_products", "data": result}
                        components_executed.append(event)
                        yield event
                        status = result.get("status", "")
                        q = args.get("query", "")
                        if status == "exact_match":
                            p = result.get("product", {})
                            final_text = (
                                f"Found an exact match for **{q}**: "
                                f"**{p.get('brand', '')} {p.get('product_name', '')}**."
                            )
                        elif status == "likely_match":
                            p = result.get("product", {})
                            final_text = (
                                f"Here's the closest match I found for **{q}**: "
                                f"**{p.get('brand', '')} {p.get('product_name', '')}**. "
                                f"Is this the one you were looking for?"
                            )
                        elif status == "ask_clarification":
                            msg = result.get("message", "")
                            suggestions = result.get("suggestions", [])
                            names = [
                                f"• {s.get('brand', '')} {s.get('product_name', '')}"
                                for s in suggestions[:5]
                            ]
                            final_text = (
                                f"{msg}\n\n" + "\n".join(names)
                                if names else msg
                            )
                        else:
                            final_text = (
                                f"I couldn't find **{q}** in the catalog. "
                                f"Try checking the spelling or ask for a broader search."
                            )

                    elif tool_name == "filter_products":
                        brand_arg    = args.get("brand")
                        chipset_arg  = args.get("chipset")
                        category_arg = args.get("category")
                        series_arg   = args.get("series")
                        subcat_arg   = args.get("sub_category")
                        tool_type    = args.get("tool_type", "brand")

                        result = self.tool_manager.search_service.filter_products(
                            brand=brand_arg,
                            chipset=chipset_arg,
                            category=category_arg if category_arg else None,
                            series=series_arg,
                            sub_category=subcat_arg
                        )
                        event = {"type": "tool_result", "func_name": "filter_products", "data": result}
                        components_executed.append(event)
                        yield event

                        count = result.get("count", 0)
                        # Build a human-readable label
                        label = (
                            (chipset_arg or brand_arg or series_arg or subcat_arg or category_arg or "")
                        ).upper()
                        if count > 0:
                            final_text = (
                                f"I found **{count} products** matching **{label}**. "
                                f"Here are the results — let me know if you'd like to "
                                f"compare, check prices, or get a recommendation!"
                            )
                        else:
                            final_text = (
                                f"I couldn't find any products matching **{label}**. "
                                f"Try a broader search or check the spelling."
                            )

                    else:
                        # Unknown tool from router — fall through to LLM
                        logger.warning(f"Router returned unknown tool: {tool_name}. Falling through to LLM.")
                        route_decision = None

                except Exception as e:
                    logger.error(f"Router tool execution failed for {tool_name}: {e}")
                    final_text = _FALLBACK_FORMAT
                    yield {"type": "error", "data": str(e)}

                search_time = time.perf_counter() - search_start
                logger.info(f"[Latency] Direct Tool Execution completed in {search_time:.4f}s")

                if route_decision:  # Only return if route was successfully handled
                    # Guarantee non-empty text
                    final_text = self._safe_text(final_text)
                    yield {"type": "text", "data": final_text}
                    total_time = time.perf_counter() - total_start_time
                    logger.info(f"[Latency] Short-Circuited! Total time: {total_time:.4f}s")
                    self.abstract_history.append({
                        "role": "assistant",
                        "content": final_text,
                        "components": components_executed
                    })
                    return

        # ─────────────────────────────────────────────────
        # 2. LLM Phase
        # ─────────────────────────────────────────────────
        llm_start_time = time.perf_counter()
        
        if self.active_backend == "groq":
            try:
                for event in self.groq_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
            except Exception as e:
                logger.warning(f"Groq failed: {e}. Falling back to Gemini.")
                yield {"type": "status", "data": "Switching to backup AI service..."}
                self.active_backend = "gemini"
                for event in self.gemini_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
        else:
            try:
                for event in self.gemini_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
            except RateLimitError:
                yield {"type": "status", "data": "Switching to backup AI service..."}
                logger.warning("Failover triggered! Switching to Groq API.")
                self.active_backend = "groq"
                self.abstract_history.pop()
                self.sync_history_to_groq()
                self.abstract_history.append(current_msg)
                for event in self.groq_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
                    
        llm_time = time.perf_counter() - llm_start_time
        logger.info(f"[Latency] LLM Generation completed in {llm_time:.4f}s")
        
        # ── Guarantee non-empty final response ──
        if not final_text or not str(final_text).strip():
            logger.warning("LLM returned empty response. Yielding fallback.")
            final_text = _FALLBACK_EMPTY
            yield {"type": "text", "data": final_text}
        
        total_time = time.perf_counter() - total_start_time
        logger.info(f"[Latency] Total Request Time: {total_time:.4f}s")
        
        # Update abstract history
        self.abstract_history.append({
            "role": "assistant",
            "content": final_text,
            "components": components_executed
        })

    def generate_response(self, prompt: str) -> str:
        """Legacy synchronous wrapper."""
        final_text = ""
        for event in self.generate_response_stream(prompt):
            if event["type"] == "text":
                final_text = event["data"]
            elif event["type"] == "error":
                final_text = event["data"]
        return final_text or _FALLBACK_EMPTY
