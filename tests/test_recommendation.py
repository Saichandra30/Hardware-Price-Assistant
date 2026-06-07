import pytest
from services.recommendation_service import RecommendationService

MOCK_CATALOG = [
    # CPUs
    {"id": "cp_amd_9700x", "product_name": "Ryzen 7 9700X", "brand": "AMD", "category": "CPU", "prices": {"dealer": 23000.0}},
    {"id": "cp_amd_9800x3d", "product_name": "Ryzen 7 9800X3D", "brand": "AMD", "category": "CPU", "prices": {"dealer": 38000.0}},
    {"id": "cp_amd_5600x", "product_name": "Ryzen 5 5600X", "brand": "AMD", "category": "CPU", "prices": {"dealer": 12000.0}},
    # Motherboards (AM5 chipsets)
    {"id": "mo_asus_rog_x870e", "product_name": "ROG CROSSHAIR X870E HERO", "brand": "ASUS", "category": "Motherboard", "chipset": "X870E", "prices": {"dealer": 55500.0}},
    {"id": "mo_asus_tuf_b850", "product_name": "TUF GAMING B850M-PLUS", "brand": "ASUS", "category": "Motherboard", "chipset": "B850", "prices": {"dealer": 18500.0}},
    {"id": "mo_asus_prime_b840", "product_name": "PRIME B840M-A", "brand": "ASUS", "category": "Motherboard", "chipset": "B840", "prices": {"dealer": 14250.0}}
]

@pytest.fixture
def recommendation_service(mocker):
    mocker.patch('services.search_service.get_catalog', return_value=MOCK_CATALOG)
    return RecommendationService()

def test_recommend_product_9800x3d(recommendation_service):
    """Test recommendation for 9800X3D CPU."""
    recs = recommendation_service.recommend_product("9800X3D")
    
    assert recs["status"] == "success"
    assert "9800X3D" in recs["cpu"]["product_name"]
    
    # Check tiers exist and are correct
    assert recs["recommendations"]["Recommended Premium Choice"]["product_name"] == "ROG CROSSHAIR X870E HERO"
    assert recs["recommendations"]["Recommended Performance Choice"]["product_name"] == "TUF GAMING B850M-PLUS"
    assert recs["recommendations"]["Recommended Value Choice"]["product_name"] == "PRIME B840M-A"

def test_recommend_product_9700x(recommendation_service):
    """Test recommendation for 9700X CPU."""
    recs = recommendation_service.recommend_product("9700X")
    
    assert recs["status"] == "success"
    assert "9700X" in recs["cpu"]["product_name"]
    
    # Check tiers exist and are correct
    assert recs["recommendations"]["Recommended Premium Choice"]["product_name"] == "ROG CROSSHAIR X870E HERO"
    assert recs["recommendations"]["Recommended Performance Choice"]["product_name"] == "TUF GAMING B850M-PLUS"
    assert recs["recommendations"]["Recommended Value Choice"]["product_name"] == "PRIME B840M-A"

def test_recommend_invalid_cpu(recommendation_service):
    """Test recommendation request for an unknown/invalid CPU."""
    recs = recommendation_service.recommend_product("Intel Core i9")
    
    assert recs["status"] == "error"
    assert "not found" in recs["message"].lower()

def test_recommend_empty_result(recommendation_service):
    """Test recommendation when no compatible motherboards exist in the catalog."""
    # 5600X is an AM4 CPU. Our mock catalog has no AM4 motherboards.
    recs = recommendation_service.recommend_product("5600X")
    
    assert recs["status"] == "empty"
    assert recs["message"] == "I couldn't find compatible motherboard recommendations in the current catalog."
    assert recs["recommendations"]["Recommended Premium Choice"] is None
    assert recs["recommendations"]["Recommended Performance Choice"] is None
    assert recs["recommendations"]["Recommended Value Choice"] is None
