import logging
import json
from llm.gemini_client import GeminiClient, RateLimitError
from llm.groq_client import GroqClient

logger = logging.getLogger(__name__)

class HybridClient:
    """
    Client that uses Gemini by default, but seamlessly falls back to Groq
    if the Google Gemini API hits its Free Tier Rate Limits (429 RESOURCE_EXHAUSTED).
    Maintains abstract conversational memory to sync across backends.
    """
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.groq_client = GroqClient()
        
        # We start with Gemini
        self.active_backend = "gemini"
        
        # Abstract conversation history to sync between clients on failover
        self.abstract_history = []
        
    def reset_memory(self):
        self.gemini_client.reset_memory()
        self.groq_client.reset_memory()
        self.abstract_history = []
        self.active_backend = "gemini"
        logger.info("HybridClient memory reset.")

    def sync_history_to_groq(self):
        """Rebuilds the Groq native history array from abstract_history."""
        logger.info("Syncing abstract history to Groq Client.")
        self.groq_client.reset_memory()
        
        for msg in self.abstract_history:
            role = msg["role"]
            content = msg["content"]
            components = msg.get("components", [])
            
            # Reconstruct user message
            if role == "user":
                if content:
                    self.groq_client.messages.append({"role": "user", "content": content})
                
            # Reconstruct assistant messages (skip tool calls to save tokens)
            elif role == "assistant":
                if content:
                    self.groq_client.messages.append({"role": "assistant", "content": content})

    def generate_response_stream(self, prompt: str):
        components_executed = []
        final_text = ""
        
        # Add to abstract history
        current_msg = {"role": "user", "content": prompt}
        self.abstract_history.append(current_msg)
        
        if self.active_backend == "gemini":
            try:
                # Try yielding from Gemini
                for event in self.gemini_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
                    
            except RateLimitError:
                # Failover triggered
                yield {"type": "status", "data": "Gemini limit reached. Falling back to Groq..."}
                logger.warning("Failover triggered! Switching to Groq API.")
                self.active_backend = "groq"
                
                # Sync history up to the current prompt (excluding current prompt since it will be appended internally by groq)
                self.abstract_history.pop() 
                self.sync_history_to_groq()
                self.abstract_history.append(current_msg)
                
                # Retry with Groq
                for event in self.groq_client.generate_response_stream(prompt):
                    if event["type"] == "tool_result":
                        components_executed.append(event)
                    elif event["type"] == "text":
                        final_text = event["data"]
                    yield event
                    
        else:
            # Already failed over to Groq
            for event in self.groq_client.generate_response_stream(prompt):
                if event["type"] == "tool_result":
                    components_executed.append(event)
                elif event["type"] == "text":
                    final_text = event["data"]
                yield event
                
        # Update history
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
