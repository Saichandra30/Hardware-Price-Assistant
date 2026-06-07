import pytest
import os
from unittest.mock import MagicMock, patch
from streamlit.testing.v1 import AppTest

@pytest.fixture(autouse=True)
def mock_hybrid_client():
    """Mock HybridClient to prevent network/API calls and timeouts during UI tests."""
    with patch('ui.app.HybridClient') as mock_class:
        mock_instance = MagicMock()
        mock_instance.generate_response_stream.return_value = [
            {"type": "status", "data": "Checking catalog..."},
            {"type": "text", "data": "Here is the cheapest AM5 motherboard option."}
        ]
        mock_class.return_value = mock_instance
        yield mock_instance

def test_app_loads():
    """Test if the Streamlit app loads without fatal errors."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    os.environ["GROQ_API_KEY"] = "test-key-ui"
    
    at = AppTest.from_file("ui/app.py").run(timeout=5)
    
    assert not at.exception
    assert "Hardware Price Assistant" in at.title[0].value

def test_clear_chat_button():
    """Test that the clear chat button clears the session state messages."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    os.environ["GROQ_API_KEY"] = "test-key-ui"
    at = AppTest.from_file("ui/app.py").run(timeout=5)
    
    clear_button = next((btn for btn in at.sidebar.button if "Clear Chat" in btn.label), None)
    assert clear_button is not None
    
    clear_button.click().run(timeout=5)
    
    assert len(at.session_state.messages) == 1
    assert "Chat cleared" in at.session_state.messages[0]["content"]

def test_sidebar_example_queries():
    """Test if clicking an example query in the sidebar triggers the query processing."""
    os.environ["GEMINI_API_KEY"] = "test-key-ui"
    os.environ["GROQ_API_KEY"] = "test-key-ui"
    at = AppTest.from_file("ui/app.py").run(timeout=5)
    
    example_btn = next((btn for btn in at.sidebar.button if "What is the cheapest AM5 motherboard" in btn.label), None)
    assert example_btn is not None
    
    example_btn.click().run(timeout=5)
    
    assert len(at.session_state.messages) > 1
    assert any("cheapest AM5" in msg["content"] for msg in at.session_state.messages)
