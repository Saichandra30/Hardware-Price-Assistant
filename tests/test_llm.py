import pytest
import os
from unittest.mock import MagicMock
from llm.hybrid_client import HybridClient
from llm.gemini_client import RateLimitError

@pytest.fixture
def hybrid_client(mocker):
    # Mock OS env for keys
    mocker.patch.dict(os.environ, {"GEMINI_API_KEY": "fake-gemini", "GROQ_API_KEY": "fake-groq"})
    mocker.patch('llm.gemini_client.load_dotenv')
    mocker.patch('llm.groq_client.load_dotenv')
    
    # Mock clients
    mock_genai_client = mocker.patch('llm.gemini_client.genai.Client')
    mock_chat = MagicMock()
    mock_genai_client.return_value.chats.create.return_value = mock_chat
    
    mock_groq_client = mocker.patch('llm.groq_client.Groq')
    mock_groq_chat = MagicMock()
    mock_groq_client.return_value.chat = mock_groq_chat
    
    client = HybridClient()
    return client

def test_hybrid_client_default_groq(hybrid_client):
    """Test if HybridClient uses Groq by default."""
    assert hybrid_client.active_backend == "groq"
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.content = "Groq response"
    hybrid_client.groq_client.client.chat.completions.create.return_value = mock_response
    
    result = hybrid_client.generate_response("Test query")
    assert result == "Groq response"
    assert hybrid_client.groq_client.client.chat.completions.create.called
    assert not hybrid_client.gemini_client.chat.send_message.called

def test_hybrid_client_failover_to_groq(hybrid_client, mocker):
    """Test if HybridClient seamlessly falls back to Groq on RateLimitError."""
    # Force Gemini to raise RateLimitError when generate_response_stream is called
    def mock_gemini_stream(prompt):
        raise RateLimitError("Quota exceeded")
        yield {} # need yield to make it a generator
        
    mocker.patch.object(hybrid_client.gemini_client, 'generate_response_stream', side_effect=mock_gemini_stream)
    
    # Mock Groq to return a successful response
    def mock_groq_stream(prompt):
        yield {"type": "text", "data": "Groq response"}
        
    mocker.patch.object(hybrid_client.groq_client, 'generate_response_stream', side_effect=mock_groq_stream)
    
    result = hybrid_client.generate_response("Test query")
    
    assert result == "Groq response"
    assert hybrid_client.active_backend == "groq"
