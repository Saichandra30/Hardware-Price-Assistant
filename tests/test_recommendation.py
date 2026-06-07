import pytest
from services.recommendation_service import RecommendationService

MOCK_CATALOG = [
    {"product_name": "Ryzen 9 9950X", "brand": "AMD", "category": "CPU", "prices": {"V1": 750.0}},
    {"product_name": "MEG X870E GODLIKE", "brand": "MSI", "category": "MOTHERBOARD", "chipset": "X870E", "prices": {"V1": 1200.0}},
    {"product_name": "B850M GAMING", "brand": "ASUS", "category": "MOTHERBOARD", "chipset": "B850", "prices": {"V1": 150.0}},
    {"product_name": "PRIME B840", "brand": "ASUS", "category": "MOTHERBOARD", "chipset": "B840", "prices": {"V1": 90.0}}
]

@pytest.fixture
def recommendation_service(mocker):
    mocker.patch('services.recommendation_service.get_catalog', return_value=MOCK_CATALOG)
    mocker.patch('services.search_service.get_catalog', return_value=MOCK_CATALOG)
    return RecommendationService()

def test_recommend_product_am5(recommendation_service):
    recs = recommendation_service.recommend_product("9950X")
    
    assert recs["status"] == "success"
    assert recs["cpu"]["product_name"] == "Ryzen 9 9950X"
    
    # Check tiers
    assert recs["recommendations"]["Recommended Premium Choice"]["product_name"] == "MEG X870E GODLIKE"
    assert recs["recommendations"]["Recommended Performance Choice"]["product_name"] == "B850M GAMING"
    assert recs["recommendations"]["Recommended Value Choice"]["product_name"] == "PRIME B840"

def test_recommend_invalid_cpu(recommendation_service):
    recs = recommendation_service.recommend_product("Intel Core i9")
    assert recs["status"] == "error"
    assert "not found" in recs["message"]
