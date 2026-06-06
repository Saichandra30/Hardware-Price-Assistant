import pytest
import os
from streamlit.testing.v1 import AppTest

def test_app_loads():
    """Test if the Streamlit app loads without fatal errors."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    
    # Path to main app logic
    at = AppTest.from_file("ui/app.py").run()
    
    assert not at.exception
    # Verify title is present
    assert "Hardware Price Assistant" in at.title[0].value

def test_clear_chat_button():
    """Test that the clear chat button clears the session state messages."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    at = AppTest.from_file("ui/app.py").run()
    
    # Click the clear chat button in sidebar
    clear_button = next((btn for btn in at.sidebar.button if "Clear Chat" in btn.label), None)
    assert clear_button is not None
    
    clear_button.click().run()
    
    # The first message should be the reset message
    assert len(at.session_state.messages) == 1
    assert "Chat cleared" in at.session_state.messages[0]["content"]

def test_sidebar_example_queries():
    """Test if clicking an example query in the sidebar sets the trigger_query state."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    
    # Patch sleep to prevent timeout during retry logic
    from unittest.mock import patch
    with patch('time.sleep', return_value=None):
        at = AppTest.from_file("ui/app.py").run(timeout=10)
        
        # Find the example query button
        example_btn = next((btn for btn in at.sidebar.button if "What is the cheapest AM5 motherboard" in btn.label), None)
        assert example_btn is not None
        
        example_btn.click().run(timeout=10)
        
        # Since it triggers a rerun and injects the query into the chat, 
        # we expect the message to be added to the session state.
        assert len(at.session_state.messages) > 1
        assert "cheapest AM5" in at.session_state.messages[-1]["content"] or "cheapest AM5" in at.session_state.messages[-2]["content"]
