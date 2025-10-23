"""
Data validation module for schema and business rule validation.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import jsonschema
from jsonschema import validate, ValidationError, FormatChecker
import yaml

logger = logging.getLogger(__name__)


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self, is_valid: bool, violations: List[Dict[str, Any]] = None):
        self.is_valid = is_valid
        self.violations = violations or []
    
    def add_violation(self, violation: Dict[str, Any]):
        """Add a violation to the result."""
        self.is_valid = False
        self.violations.append(violation)


class SchemaValidator:
    """Validates data against JSON schemas."""
    
    def __init__(self, contracts_path: str = "/contracts"):
        self.contracts_path = Path(contracts_path)
        self.schemas: Dict[str, Dict] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all JSON schemas from the contracts directory."""
        if not self.contracts_path.exists():
            logger.warning(f"Contracts path does not exist: {self.contracts_path}")
            return
        
        for domain_dir in self.contracts_path.iterdir():
            if domain_dir.is_dir():
                domain = domain_dir.name
                schema_file = domain_dir / "v1.json"
                if schema_file.exists():
                    try:
                        with open(schema_file, 'r') as f:
                            self.schemas[domain] = json.load(f)
                        logger.info(f"Loaded schema for domain: {domain}")
                    except Exception as e:
                        logger.error(f"Failed to load schema for {domain}: {e}")
    
    def validate(self, domain: str, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against the schema for the given domain.
        
        Args:
            domain: The domain name (e.g., 'customers', 'orders')
            data: The data to validate
            
        Returns:
            ValidationResult with validation status and violations
        """
        result = ValidationResult(is_valid=True)
        
        if domain not in self.schemas:
            result.add_violation({
                "type": "schema_error",
                "domain": domain,
                "field": "_schema",
                "rule_name": "schema_not_found",
                "message": f"No schema found for domain: {domain}",
                "value": None
            })
            return result
        
        schema = self.schemas[domain]
        
        try:
            # Validate with format checking enabled
            validate(
                instance=data,
                schema=schema,
                format_checker=FormatChecker()
            )
            logger.debug(f"Schema validation passed for domain: {domain}")
        except ValidationError as e:
            # Extract field path from validation error
            field_path = ".".join(str(p) for p in e.path) if e.path else e.validator
            
            result.add_violation({
                "type": "schema_error",
                "domain": domain,
                "field": field_path or "unknown",
                "rule_name": f"schema_{e.validator}",
                "message": e.message,
                "value": e.instance if hasattr(e, 'instance') else None
            })
            logger.debug(f"Schema validation failed for domain {domain}: {e.message}")
        except Exception as e:
            result.add_violation({
                "type": "schema_error",
                "domain": domain,
                "field": "unknown",
                "rule_name": "schema_validation_error",
                "message": str(e),
                "value": None
            })
            logger.error(f"Unexpected error during schema validation: {e}")
        
        return result


class BusinessRuleValidator:
    """Validates data against business rules."""
    
    def __init__(self, rules_path: str = "/rules/business_rules.yml"):
        self.rules_path = Path(rules_path)
        self.rules: Dict[str, List[Dict]] = {}
        self._load_rules()
    
    def _load_rules(self):
        """Load business rules from YAML file."""
        if not self.rules_path.exists():
            logger.warning(f"Rules file does not exist: {self.rules_path}")
            return
        
        try:
            with open(self.rules_path, 'r') as f:
                self.rules = yaml.safe_load(f)
            logger.info(f"Loaded business rules: {list(self.rules.keys())}")
        except Exception as e:
            logger.error(f"Failed to load business rules: {e}")
    
    def validate(self, domain: str, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against business rules for the given domain.
        
        Args:
            domain: The domain name (e.g., 'customers', 'orders')
            data: The data to validate
            
        Returns:
            ValidationResult with validation status and violations
        """
        result = ValidationResult(is_valid=True)
        
        if domain not in self.rules:
            logger.debug(f"No business rules defined for domain: {domain}")
            return result
        
        domain_rules = self.rules[domain]
        
        for rule in domain_rules:
            violation = self._apply_rule(domain, data, rule)
            if violation:
                result.add_violation(violation)
        
        return result
    
    def _apply_rule(self, domain: str, data: Dict[str, Any], rule: Dict) -> Optional[Dict[str, Any]]:
        """
        Apply a single business rule to the data.
        
        Returns:
            Violation dict if rule fails, None if rule passes
        """
        rule_name = rule.get('rule_name', 'unknown_rule')
        field = rule.get('field')
        condition = rule.get('condition')
        value = rule.get('value')
        error_message = rule.get('error_message', f"Business rule {rule_name} failed")
        
        # Get field value from data
        field_value = data.get(field)
        
        # Check if field exists
        if field_value is None and condition not in ['exists', 'not_exists']:
            # Field is missing - this might be caught by schema validation
            # Only report if it's a business rule requirement
            return None
        
        try:
            # Apply condition
            if condition == 'gt':
                if not (field_value > value):
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'gte':
                if not (field_value >= value):
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'lt':
                if not (field_value < value):
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'lte':
                if not (field_value <= value):
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'eq':
                if not (field_value == value):
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'in':
                if field_value not in value:
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'not_in':
                if field_value in value:
                    return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'not_in_domains':
                # Check if email domain is in blacklist
                if '@' in str(field_value):
                    email_domain = str(field_value).split('@')[1]
                    if email_domain in value:
                        return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'lte_field':
                # Compare with another field
                compare_field = rule.get('compare_field')
                compare_value = data.get(compare_field)
                if compare_value is not None and field_value is not None:
                    if not (field_value <= compare_value):
                        return self._create_violation(domain, field, rule_name, error_message, field_value)
            
            elif condition == 'calculated_match':
                # Check if calculated value matches
                formula = rule.get('formula')
                tolerance = rule.get('tolerance', 0)
                
                if formula and field_value is not None:
                    calculated = self._evaluate_formula(formula, data)
                    if calculated is not None:
                        if abs(field_value - calculated) > tolerance:
                            return self._create_violation(
                                domain, field, rule_name, 
                                f"{error_message} (expected: {calculated}, got: {field_value})",
                                field_value
                            )
            
            else:
                logger.warning(f"Unknown condition: {condition} for rule: {rule_name}")
        
        except Exception as e:
            logger.error(f"Error applying rule {rule_name}: {e}")
            return self._create_violation(
                domain, field, rule_name,
                f"Rule evaluation error: {str(e)}",
                field_value
            )
        
        return None
    
    def _evaluate_formula(self, formula: str, data: Dict[str, Any]) -> Optional[float]:
        """Safely evaluate a formula with data values."""
        try:
            # Replace field names with values
            expression = formula
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    expression = expression.replace(key, str(value))
            
            # Safely evaluate (only allow basic math operations)
            allowed_names = {"__builtins__": {}}
            result = eval(expression, allowed_names)
            return float(result)
        except Exception as e:
            logger.error(f"Formula evaluation error: {e}")
            return None
    
    def _create_violation(self, domain: str, field: str, rule_name: str, 
                         message: str, value: Any) -> Dict[str, Any]:
        """Create a violation dictionary."""
        return {
            "type": "business_rule_error",
            "domain": domain,
            "field": field,
            "rule_name": rule_name,
            "message": message,
            "value": value
        }


class DataValidator:
    """Main validator that combines schema and business rule validation."""
    
    def __init__(self, contracts_path: str = "/contracts", 
                 rules_path: str = "/rules/business_rules.yml"):
        self.schema_validator = SchemaValidator(contracts_path)
        self.business_rule_validator = BusinessRuleValidator(rules_path)
    
    def validate(self, domain: str, data: Dict[str, Any]) -> ValidationResult:
        """
        Perform complete validation: schema + business rules.
        
        Args:
            domain: The domain name
            data: The data to validate
            
        Returns:
            ValidationResult with all violations
        """
        # First validate schema
        schema_result = self.schema_validator.validate(domain, data)
        
        # If schema validation fails, don't proceed to business rules
        if not schema_result.is_valid:
            return schema_result
        
        # Validate business rules
        business_result = self.business_rule_validator.validate(domain, data)
        
        # Combine results
        if not business_result.is_valid:
            schema_result.is_valid = False
            schema_result.violations.extend(business_result.violations)
        
        return schema_result
