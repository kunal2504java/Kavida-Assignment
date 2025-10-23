"""
Unit tests for validation logic.
"""
import pytest
import sys
import os
from pathlib import Path

# Add validator app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "validator" / "app"))

from validation import (
    SchemaValidator,
    BusinessRuleValidator,
    DataValidator,
    ValidationResult
)


class TestSchemaValidator:
    """Test schema validation logic."""
    
    @pytest.fixture
    def validator(self):
        """Create a schema validator with test contracts."""
        contracts_path = Path(__file__).parent.parent / "contracts"
        return SchemaValidator(str(contracts_path))
    
    def test_valid_customer(self, validator):
        """Test validation of a valid customer."""
        customer = {
            "id": "CUST-123456",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "age": 30,
            "signup_date": "2024-01-15"
        }
        
        result = validator.validate("customers", customer)
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_invalid_customer_id_format(self, validator):
        """Test validation fails for invalid customer ID format."""
        customer = {
            "id": "INVALID-ID",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "age": 30,
            "signup_date": "2024-01-15"
        }
        
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert len(result.violations) > 0
        assert any("id" in v.get("field", "") for v in result.violations)
    
    def test_invalid_customer_email(self, validator):
        """Test validation fails for invalid email."""
        customer = {
            "id": "CUST-123456",
            "name": "John Doe",
            "email": "not-an-email",
            "age": 30,
            "signup_date": "2024-01-15"
        }
        
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert len(result.violations) > 0
    
    def test_missing_required_field(self, validator):
        """Test validation fails when required field is missing."""
        customer = {
            "id": "CUST-123456",
            "name": "John Doe",
            "email": "john.doe@example.com",
            # Missing age and signup_date
        }
        
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert len(result.violations) > 0
    
    def test_valid_order(self, validator):
        """Test validation of a valid order."""
        order = {
            "order_id": "ORD-12345678",
            "customer_id": "CUST-123456",
            "order_total": 99.99,
            "items_count": 3,
            "order_date": "2024-01-15T10:30:00Z"
        }
        
        result = validator.validate("orders", order)
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_invalid_order_total(self, validator):
        """Test validation fails for negative order total."""
        order = {
            "order_id": "ORD-12345678",
            "customer_id": "CUST-123456",
            "order_total": -10.00,
            "items_count": 3,
            "order_date": "2024-01-15T10:30:00Z"
        }
        
        result = validator.validate("orders", order)
        assert not result.is_valid
        assert len(result.violations) > 0


class TestBusinessRuleValidator:
    """Test business rule validation logic."""
    
    @pytest.fixture
    def validator(self):
        """Create a business rule validator with test rules."""
        rules_path = Path(__file__).parent.parent / "rules" / "business_rules.yml"
        return BusinessRuleValidator(str(rules_path))
    
    def test_customer_age_minimum(self, validator):
        """Test customer age minimum requirement."""
        # Valid age
        customer = {"age": 25}
        result = validator.validate("customers", customer)
        assert result.is_valid
        
        # Invalid age (under 18)
        customer = {"age": 16}
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert any(v.get("rule_name") == "age_minimum_requirement" for v in result.violations)
    
    def test_order_minimum_value(self, validator):
        """Test order minimum value requirement."""
        # Valid order total
        order = {"order_total": 50.00}
        result = validator.validate("orders", order)
        assert result.is_valid
        
        # Invalid order total (zero)
        order = {"order_total": 0}
        result = validator.validate("orders", order)
        assert not result.is_valid
        assert any(v.get("rule_name") == "minimum_order_value" for v in result.violations)
    
    def test_order_items_count(self, validator):
        """Test order items count requirement."""
        # Valid items count
        order = {"items_count": 5}
        result = validator.validate("orders", order)
        assert result.is_valid
        
        # Invalid items count (zero)
        order = {"items_count": 0}
        result = validator.validate("orders", order)
        assert not result.is_valid
    
    def test_email_domain_blacklist(self, validator):
        """Test email domain blacklist."""
        # Valid email domain
        customer = {"email": "user@example.com"}
        result = validator.validate("customers", customer)
        assert result.is_valid
        
        # Invalid email domain (blacklisted)
        customer = {"email": "user@tempmail.com"}
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert any(v.get("rule_name") == "valid_email_domain" for v in result.violations)
    
    def test_discount_validation(self, validator):
        """Test discount cannot exceed order total."""
        # Valid discount
        order = {"order_total": 100.00, "discount_applied": 20.00}
        result = validator.validate("orders", order)
        assert result.is_valid
        
        # Invalid discount (exceeds total)
        order = {"order_total": 100.00, "discount_applied": 150.00}
        result = validator.validate("orders", order)
        assert not result.is_valid
        assert any(v.get("rule_name") == "discount_validation" for v in result.violations)


class TestDataValidator:
    """Test complete data validation (schema + business rules)."""
    
    @pytest.fixture
    def validator(self):
        """Create a complete data validator."""
        contracts_path = Path(__file__).parent.parent / "contracts"
        rules_path = Path(__file__).parent.parent / "rules" / "business_rules.yml"
        return DataValidator(str(contracts_path), str(rules_path))
    
    def test_fully_valid_customer(self, validator):
        """Test a customer that passes both schema and business rules."""
        customer = {
            "id": "CUST-123456",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "age": 30,
            "signup_date": "2024-01-15",
            "status": "active"
        }
        
        result = validator.validate("customers", customer)
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_schema_invalid_customer(self, validator):
        """Test a customer that fails schema validation."""
        customer = {
            "id": "INVALID",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "age": 30,
            "signup_date": "2024-01-15"
        }
        
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert any(v.get("type") == "schema_error" for v in result.violations)
    
    def test_business_rule_invalid_customer(self, validator):
        """Test a customer that fails business rule validation."""
        customer = {
            "id": "CUST-123456",
            "name": "John Doe",
            "email": "john.doe@tempmail.com",  # Blacklisted domain
            "age": 30,
            "signup_date": "2024-01-15"
        }
        
        result = validator.validate("customers", customer)
        assert not result.is_valid
        assert any(v.get("type") == "business_rule_error" for v in result.violations)
    
    def test_fully_valid_order(self, validator):
        """Test an order that passes both schema and business rules."""
        order = {
            "order_id": "ORD-12345678",
            "customer_id": "CUST-123456",
            "order_total": 150.00,
            "items_count": 3,
            "order_date": "2024-01-15T10:30:00Z",
            "discount_applied": 10.00
        }
        
        result = validator.validate("orders", order)
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_multiple_violations(self, validator):
        """Test a record with multiple violations."""
        order = {
            "order_id": "ORD-12345678",
            "customer_id": "CUST-123456",
            "order_total": 0,  # Business rule violation
            "items_count": 0,  # Business rule violation
            "order_date": "2024-01-15T10:30:00Z"
        }
        
        result = validator.validate("orders", order)
        assert not result.is_valid
        assert len(result.violations) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
