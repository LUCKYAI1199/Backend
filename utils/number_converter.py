"""
Number conversion utilities for handling Zerodha's abbreviated values
"""

import re
from typing import Union

def convert_abbreviated_to_exact(value: Union[str, int, float]) -> int:
    """
    Convert Zerodha's abbreviated values (K, L, CR) to exact numbers
    
    Examples:
    - "5.2K" -> 5200
    - "1.5L" -> 150000
    - "2.3CR" -> 23000000
    - "100" -> 100
    - 1500 -> 1500
    
    Args:
        value: The value to convert (can be string with K/L/CR suffix or numeric)
        
    Returns:
        int: The exact numerical value
    """
    if value is None:
        return 0
    
    # If it's already a number, return it as is
    if isinstance(value, (int, float)):
        return int(value)
    
    # Convert to string and clean it
    value_str = str(value).strip().upper()
    
    # If it's just a number without suffix, return it
    if value_str.replace('.', '').replace('-', '').isdigit():
        return int(float(value_str))
    
    # Extract the numeric part and suffix
    match = re.match(r'^([+-]?\d*\.?\d+)\s*([KLC]R?)?$', value_str)
    
    if not match:
        # If we can't parse it, try to extract just the number
        numeric_match = re.search(r'([+-]?\d*\.?\d+)', value_str)
        if numeric_match:
            return int(float(numeric_match.group(1)))
        return 0
    
    numeric_part = float(match.group(1))
    suffix = match.group(2) or ''
    
    # Convert based on suffix
    if suffix == 'K':
        return int(numeric_part * 1_000)
    elif suffix == 'L':
        return int(numeric_part * 1_00_000)  # 1 Lakh = 100,000
    elif suffix == 'CR':
        return int(numeric_part * 1_00_00_000)  # 1 Crore = 10,000,000
    else:
        return int(numeric_part)

def convert_volume_oi_data(data: dict) -> dict:
    """
    Convert volume and OI data from abbreviated format to exact numbers
    
    Args:
        data: Dictionary containing volume and OI data
        
    Returns:
        dict: Dictionary with converted exact numbers
    """
    converted_data = data.copy()
    
    # Fields that need conversion
    conversion_fields = [
        'volume', 'oi', 'ce_volume', 'ce_oi', 'pe_volume', 'pe_oi',
        'total_ce_volume', 'total_pe_volume', 'total_ce_oi', 'total_pe_oi'
    ]
    
    for field in conversion_fields:
        if field in converted_data:
            converted_data[field] = convert_abbreviated_to_exact(converted_data[field])
    
    return converted_data

# Test function for validation
def test_conversion():
    """Test the conversion function with various inputs"""
    test_cases = [
        ("5.2K", 5200),
        ("1.5L", 150000),
        ("2.3CR", 23000000),
        ("100", 100),
        ("0.5K", 500),
        ("10.25L", 1025000),
        ("1.234CR", 12340000),
        (1500, 1500),
        (2.5, 2),
        (None, 0),
        ("", 0),
        ("invalid", 0),
        ("12.34", 12),
    ]
    
    print("Testing number conversion:")
    for input_val, expected in test_cases:
        result = convert_abbreviated_to_exact(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_val} -> {result} (expected: {expected})")
    
    return True

if __name__ == "__main__":
    test_conversion()
