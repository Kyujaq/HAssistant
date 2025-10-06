"""
Basic test for deals providers.
"""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/home/runner/work/HAssistant/HAssistant')

from deals.providers import DealsProvider, MockCAProvider


def test_mock_ca_provider_instantiation():
    """Test that MockCAProvider can be instantiated"""
    provider = MockCAProvider()
    assert provider is not None
    assert isinstance(provider, DealsProvider)
    print("✓ MockCAProvider instantiation successful")


def test_mock_ca_provider_returns_deals():
    """Test that MockCAProvider returns deals data"""
    provider = MockCAProvider()
    result = provider.get_prices_for(["chicken", "beef"], "M5H 2N2")
    
    assert "deals" in result
    assert isinstance(result["deals"], list)
    assert len(result["deals"]) > 0
    print(f"✓ MockCAProvider returned {len(result['deals'])} deals")


def test_mock_ca_provider_deal_schema():
    """Test that deals match expected schema"""
    provider = MockCAProvider()
    result = provider.get_prices_for([], "")
    
    deals = result["deals"]
    first_deal = deals[0]
    
    # Check required fields
    assert "item" in first_deal
    assert "best_store" in first_deal
    assert "unit_price" in first_deal
    assert "unit" in first_deal
    assert "valid_to" in first_deal
    
    # Check data types
    assert isinstance(first_deal["item"], str)
    assert isinstance(first_deal["best_store"], str)
    assert isinstance(first_deal["unit_price"], (int, float))
    assert isinstance(first_deal["unit"], str)
    assert isinstance(first_deal["valid_to"], str)
    
    # Check valid_to format (YYYY-MM-DD)
    try:
        datetime.strptime(first_deal["valid_to"], "%Y-%m-%d")
    except ValueError:
        raise AssertionError(f"valid_to date format is incorrect: {first_deal['valid_to']}")
    
    print("✓ Deal schema validation passed")
    print(f"  Sample deal: {first_deal['item']} at {first_deal['best_store']} - ${first_deal['unit_price']}/{first_deal['unit']}")


def test_abstract_base_class():
    """Test that DealsProvider cannot be instantiated directly"""
    try:
        provider = DealsProvider()
        assert False, "Should not be able to instantiate abstract base class"
    except TypeError as e:
        assert "abstract" in str(e).lower()
        print("✓ Abstract base class cannot be instantiated (as expected)")


if __name__ == "__main__":
    print("Running deals provider tests...\n")
    
    test_mock_ca_provider_instantiation()
    test_mock_ca_provider_returns_deals()
    test_mock_ca_provider_deal_schema()
    test_abstract_base_class()
    
    print("\n✅ All tests passed!")
