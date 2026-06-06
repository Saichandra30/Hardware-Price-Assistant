import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Searches for a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

messages = [
    {'role': 'system', 'content': 'You are a test.'},
    {'role': 'user', 'content': 'Find 9700X.'},
    {'role': 'assistant', 'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'search_products', 'arguments': '{}'}}]},
    {'role': 'tool', 'tool_call_id': 'call_1', 'name': 'search_products', 'content': '{"status": "success"}'},
    {'role': 'user', 'content': 'thanks!'}
]

try:
    res = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=messages,
        tools=tools,
        temperature=0.0
    )
    print('SUCCESS')
except Exception as e:
    print('ERROR:', e)
