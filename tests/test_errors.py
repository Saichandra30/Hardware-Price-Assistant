import pytest
from llm.tool_definitions import ToolManager
from services.search_service import SearchService

@pytest.fixture
def tool_manager(mocker):
    # Mock services to isolate error handling tests
    mocker.patch('services.search_service.get_catalog', return_value=[])
    mocker.patch('services.recommendation_service.get_catalog', return_value=[])
    return ToolManager()

def test_tool_exact_lookup_type_error(tool_manager):
    """Test that passing an invalid type like int or list returns safe error JSON instead of crashing."""
    res = tool_manager.lookup_product(123)
    assert "error" in res
    assert "Invalid parameter type." in res["error"]
    
def test_tool_compare_products_missing_args(tool_manager):
    """Test missing or invalid args in compare products."""
    res = tool_manager.compare_products(None, 123)
    assert "error" in res
    assert "Invalid parameter types" in res["error"]

def test_tool_internal_exception_swallowing(tool_manager, mocker):
    """Test that if the backend service throws an unexpected exception, the tool catches it and masks it."""
    # Force the backend search service to throw a massive Exception
    mocker.patch.object(tool_manager.search_service, 'search_product', side_effect=Exception("Massive Stack Trace Exposing Path C:/Users/Admin/Secret"))
    
    # Tool should catch it
    res = tool_manager.search_products("9600X")
    
    # Verify the secret path is NOT leaked to the LLM
    assert "error" in res
    assert "Internal processing error" in res["error"]
    assert "Secret" not in res["error"]
