import pytest
from unittest.mock import patch
from services.search_service import SearchService

MOCK_CATALOG = [
    {"product_name": "Ryzen 9 9950X", "brand": "AMD", "category": "CPU", "prices": {"VendorA": 750.0}},
    {"product_name": "MEG X870E GODLIKE", "brand": "MSI", "category": "MOTHERBOARD", "chipset": "X870E", "prices": {"VendorA": 1200.0}},
    {"product_name": "B850M GAMING", "brand": "ASUS", "category": "MOTHERBOARD", "chipset": "B850", "prices": {"VendorB": 150.0}}
]

@pytest.fixture
def search_service(mocker):
    mocker.patch('services.search_service.get_catalog', return_value=MOCK_CATALOG)
    return SearchService()

def test_exact_lookup(search_service):
    res = search_service.exact_lookup("Ryzen 9 9950X")
    assert res["status"] == "success"
    assert res["product"]["brand"] == "AMD"

    res_fail = search_service.exact_lookup("Invalid")
    assert res_fail["status"] == "not_found"

def test_search_product_fuzzy(search_service):
    res = search_service.search_product("Ryzen 9950X")
    assert res["status"] in ["exact_match", "likely_match"]
    assert res["product"]["product_name"] == "Ryzen 9 9950X"

def test_get_cheapest(search_service):
    res = search_service.get_cheapest("MOTHERBOARD")
    assert res["product"]["product_name"] == "B850M GAMING"
    assert res["min_price"] == 150.0

def test_filter_products(search_service):
    res = search_service.filter_products(brand="MSI")
    assert len(res["results"]) == 1
    assert res["results"][0]["product_name"] == "MEG X870E GODLIKE"
