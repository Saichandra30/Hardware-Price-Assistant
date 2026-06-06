import pytest
import pandas as pd
import numpy as np
import math
from services.catalog_loader import normalize_catalog

@pytest.fixture
def mock_excel_data():
    """Provides sample dirty data mimicking the Excel layout expected by the parser."""
    return pd.DataFrame({
        "Unnamed: 0": ["AMD CPU", "Ryzen 9 9950X", "Ryzen 5 9600X", "MSI", "MEG X870-P WIFI", "ASUS", "PRIME B840-PLUS"],
        "Unnamed: 1": ["Price_1", "750", " 250 ", "Price_1", "300.5", "Price_1", np.nan],
    })

def test_normalize_catalog(mock_excel_data):
    """Test the parser handles blank rows, spacing, and currencies."""
    df_dict = {"Sheet1": mock_excel_data}
    catalog = normalize_catalog(df_dict)
    
    # Assert total records (header row ignored)
    assert len(catalog) == 3
    
    # Verify Ryzen 9950X
    cpu1 = next(p for p in catalog if "9950X" in p["product_name"])
    assert cpu1["brand"] == "AMD"
    assert cpu1["category"] == "CPU"
    assert "Price_1" in cpu1["price_data"]
    assert cpu1["price_data"]["Price_1"] == 750.0
