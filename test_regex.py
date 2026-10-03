import re

def extract_numbers(s):
    # Match numbers like $40,000, 40 000, 40000, $40,000.50
    # Matches strings that start with optional currency, followed by digits with optional commas/dots
    tokens = re.findall(r'\$?\s*\d+(?:[,\s_]\d{3})*(?:\.\d+)?', s)
    res = []
    for t in tokens:
        clean = re.sub(r'[^\d\.]', '', t)
        try:
            val = float(clean)
            if val > 0: res.append(val)
        except ValueError: pass
    return res

test_str1 = "Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares."
print("Test 1:", extract_numbers(test_str1))

test_str2 = "Yesterday we sold $12,000 products."
print("Test 2:", extract_numbers(test_str2))

test_str3 = "Paid $3,500 salaries to employees."
print("Test 3:", extract_numbers(test_str3))

test_str4 = "Paid $1,800 office rent."
print("Test 4:", extract_numbers(test_str4))

test_str5 = "Bought new machine equipment for $4,500."
print("Test 5:", extract_numbers(test_str5))
