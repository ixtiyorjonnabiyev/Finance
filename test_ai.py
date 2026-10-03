import re

def extract_numbers(s):
    matches = re.findall(r'\$?\s*(?:\d{1,3}(?:[,\s_]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)', s)
    nums = []
    for m in matches:
        clean = re.sub(r'[^\d\.]', '', m)
        try:
            v = float(clean)
            if v > 0: nums.append(v)
        except ValueError: pass
    return nums

test_str1 = "Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares."
print("Test 1:", extract_numbers(test_str1))

test_str2 = "Yesterday we sold $12,000 products."
print("Test 2:", extract_numbers(test_str2))

test_str3 = "Paid $3,500 salaries to employees."
print("Test 3:", extract_numbers(test_str3))

test_str4 = "Paid $1,800 office rent."
print("Test 4:", extract_numbers(test_str4))
