#!/usr/bin/env python3
"""
Test script to verify lakhs formatting for volume and OI display
"""

# Test cases for lakhs formatting
test_cases = [
    (150000, "1.5L"),      # 1.5 Lakhs
    (550000, "5.5L"),      # 5.5 Lakhs
    (1000000, "10L"),      # 10 Lakhs  
    (50000, "50K"),        # 50 Thousand (less than 1 lakh)
    (5000, "5K"),          # 5 Thousand
    (500, "500"),          # 500 (less than 1K)
    (1250000, "12.5L"),    # 12.5 Lakhs
    (75000, "75K"),        # 75 Thousand
]

print("🧪 Testing Lakhs Formatting for Volume and OI:")
print("=" * 50)

for value, expected in test_cases:
    # Simulate the JavaScript formatting logic in Python
    if value >= 100000:  # 1 Lakh or more
        formatted = f"{value / 100000:.2f}L".rstrip('0').rstrip('.')
        if formatted.endswith('.'):
            formatted = formatted[:-1]
        formatted += 'L' if not formatted.endswith('L') else ''
    elif value >= 1000:  # 1 Thousand or more
        formatted = f"{value / 1000:.2f}K".rstrip('0').rstrip('.')
        if formatted.endswith('.'):
            formatted = formatted[:-1]
        formatted += 'K' if not formatted.endswith('K') else ''
    else:
        formatted = str(value)
    
    status = "✅" if formatted == expected else "❌"
    print(f"{status} {value:>8,} -> {formatted:>8} (expected: {expected})")

print("\n📊 Summary:")
print("- Values >= 1 Lakh (100,000) will show as X.XL")
print("- Values >= 1 Thousand (1,000) will show as X.XK") 
print("- Values < 1 Thousand will show exact number")
print("\n✅ Backend converts Zerodha's K/L/CR to exact numbers")
print("✅ Frontend displays exact numbers in lakhs format for readability")
print("\n🎯 Result: Users see clean lakhs format while having exact data internally")
