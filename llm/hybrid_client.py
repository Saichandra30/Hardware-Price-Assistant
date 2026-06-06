import logging
import json
import time
from llm.gemini_client import GeminiClient, RateLimitError
from llm.groq_client import GroqClient
from llm.tool_definitions import ToolManager
from services.router import FastIntentRouter

logger = logging.getLogger(__name__)

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
            content = msg["content"]
            if role == "user" and content:
                self.groq_client.messages.append({"role": "user", "content": content})
            elif role == "assistant" and content:
                self.groq_client.messages.append({"role": "assistant", "content": content})

    def generate_response_stream(self, prompt: str):
        total_start_time = time.perf_counter()
        components_executed = []
        final_text = ""
        
        # Enforce history limit (last 5 messages)
        if len(self.abstract_history) > 5:
            self.abstract_history = self.abstract_history[-5:]
            self.sync_history_to_groq()
            self.gemini_client.load_memory(self.abstract_history)
            
        # Add to abstract history
        current_msg = {"role": "user", "content": prompt}
        self.abstract_history.append(current_msg)
        
        # 1. Routing Phase
        routing_start = time.perf_counter()
        route_decision = self.router.route_query(prompt)
        routing_time = time.perf_counter() - routing_start
        logger.info(f"[Latency] Routing completed in {routing_time:.4f}s")
        
        if route_decision:
            if route_decision.get("bypassed"):
                # Complete bypass with hardcoded text
                final_text = route_decision["text"]
                yield {"type": "text", "data": final_text}
                total_time = time.perf_counter() - total_start_time
                logger.info(f"[Latency] LLM Bypassed! Total time: {total_time:.4f}s")
                self.abstract_history.append({"role": "assistant", "content": final_text, "components": components_executed})
                return
                
            elif route_decision.get("tool"):
                # Execute tool directly and use template
                yield {"type": "status", "data": "Executing optimized search..."}
                
                search_start = time.perf_counter()
                tool_name = route_decision["tool"]
                args = route_decision["args"]
                
                if tool_name == "search_products":
                    result = self.tool_manager.search_products(**args)
                    event = {"type": "tool_result", "data": result}
                    components_executed.append(event)
                    yield event
                    
                    # Python String Template Formatting
                    if result.get("status") == "exact_match":
                        final_text = f"Here is the exact match I found for '{args.get('query')}':"
                    elif result.get("status") == "likely_match":
                        final_text = f"I found a likely match for '{args.get('query')}':"
                    elif result.get("status") == "ask_clarification":
                        final_text = result.get("message", "Could you be more specific?")
                    else:
                        final_text = f"I couldn't find exactly '{args.get('query')}'. Try another search!"
                        
                elif tool_name == "get_catalog_stats":
                    result = self.tool_manager.get_catalog_stats()
                    event = {"type": "tool_result", "data": result}
                    components_executed.append(event)
                    yield event
                    final_text = "Here are the details of our current hardware inventory:"
                    
                elif tool_name == "recommend_products":
                    result = self.tool_manager.recommend_products(**args)
                    event = {"type": "tool_result", "data": result}
                    components_executed.append(event)
                    yield event
                    if result.get("status") == "success":
                        final_text = f"Here are the best motherboard recommendations for the {args.get('base_product')}:"
                    else:
                        final_text = f"I'm sorry, I couldn't find good recommendations for '{args.get('base_product')}'. Are you sure that CPU is in our catalog?"
                    
                elif tool_name == "get_cheapest":
                    result = self.tool_manager.search_service.get_cheapest(args.get("category", ""))
                    event = {"type": "tool_result", "data": result}
                    components_executed.append(event)
                    yield event
                    if result.get("status") == "success":
                        final_text = f"The cheapest {args.get('category')} we have is the {result['product']['product_name']} at ${result['min_price']}."
                    else:
                        final_text = f"I'm sorry, I couldn't find any products in the category '{args.get('category')}'."
                        
                search_time = time.perf_counter() - search_start
                logger.info(f"[Latency] Direct Tool Execution completed in {search_time:.4f}s")
                
                yield {"type": "text", "data": final_text}
                total_time = time.perf_counter() - total_start_time
                logger.info(f"[Latency] Short-Circuited Request! Total time: {total_time:.4f}s")
                
                self.abstract_history.append({"role": "assistant", "content": final_text, "components": components_executed})
                return

        # 2. LLM Phase
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
                yield {"type": "status", "data": "Groq failed. Falling back to Gemini..."}
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
                yield {"type": "status", "data": "Gemini limit reached. Falling back to Groq..."}
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
        return final_text
