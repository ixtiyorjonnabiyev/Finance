import re

text = """
Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares.
Yesterday we sold $12,000 products.
Paid $3,500 salaries to employees.
Paid $1,800 office rent.
Bought new machine equipment for $4,500.
Received $5,000 service fee.
"""

clauses = [c.strip() for c in re.split(r'[\n;\.]|,\s*(?=[a-zA-Z\$\u0400-\u04FF])', text) if c.strip()]

for i, c in enumerate(clauses):
    print(f"{i+1}: {c}")
