import re

text = "Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares."

clauses = [c.strip() for c in re.split(r'(?<!\d),(?!\d)|[\n;\.]', text) if c.strip()]

for i, c in enumerate(clauses):
    print(f"{i+1}: {c}")
