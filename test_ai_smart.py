import re

text = """
Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares.
Yesterday we sold $12,000 products.
Paid $3,500 salaries to employees.
Paid $1,800 office rent.
Bought new machine equipment for $4,500.
Received $5,000 service fee.
"""

def parse_financial_text(raw_text):
    detected_balances = {
        "opening_cash": None,
        "opening_fixed_assets": None,
        "opening_loans": None,
        "opening_equity": None,
        "share_count": None
    }
    detected_txs = []

    clauses = [c.strip() for c in re.split(r'[\n;\.]|,(?=\s*[^0-9])|(?<=[a-zA-Z])\s*,\s*', raw_text) if c.strip()]

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

    def contains_any(str_val, words):
        str_lower = str_val.lower()
        return any(w in str_lower for w in words)

    cat_keywords = {
        "salaries": ["salary", "salaries", "maosh", "zarplata", "payroll", "xodim", "sotrudnik"],
        "rent": ["rent", "ijara", "arenda"],
        "utilities": ["utilities", "kommunal", "electricity", "elektr", "kommunalka", "water"],
        "raw_materials": ["raw material", "xom ashyo", "syryo", "materials"],
        "goods_purchase": ["goods", "inventory", "tovar", "zakupka", "purchase goods", "mahsulot xaridi"],
        "retail_sales": ["retail", "chakana", "roznica", "shop sales"],
        "wholesale_sales": ["wholesale", "ulgurji", "optom"],
        "service_fees": ["service", "xizmat", "uslugi", "contract fee", "freelance"],
        "equipment": ["equipment", "machinery", "machine", "uskuna", "jihoz", "oborudovanie", "technika"],
        "loan_in": ["borrowed", "loan received", "kredit olindi", "qarz olindi", "vzyali kredit", "vzyal zaem"],
        "loan_out": ["loan repaid", "repaid loan", "kredit to'landi", "qarz qaytarildi", "pogasili kredit"],
        "taxes": ["tax", "taxes", "soliq", "nalog", "nalogi"],
        "marketing": ["marketing", "ad", "reklama", "advertising"]
    }

    def infer_category(line_str, default_type):
        l_low = line_str.lower()
        for cat_k, kw_list in cat_keywords.items():
            if any(kw in l_low for kw in kw_list):
                return cat_k
        return "sales_products" if default_type == "income" else "other_expense"

    now_date = "2026-10-02"

    for clause in clauses:
        nums = extract_numbers(clause)
        if not nums: continue
        amt = nums[0]
        l_low = clause.lower()

        # Check for initial balances ONLY if sentence/clause contains startup/onboarding context
        is_startup_clause = contains_any(l_low, ["started", "boshlang'ich", "nachalnyy", "initial", "open with", "opening balance", "starting balance"])
        
        if is_startup_clause:
            if contains_any(l_low, ["equipment", "asset", "uskuna", "jihoz", "oborudovanie"]):
                detected_balances["opening_fixed_assets"] = amt
            elif contains_any(l_low, ["debt", "loan", "kredit", "qarz", "dolg", "zaem"]):
                detected_balances["opening_loans"] = amt
            elif contains_any(l_low, ["capital", "equity", "ustavnyy"]):
                detected_balances["opening_equity"] = amt
            elif contains_any(l_low, ["shares", "stock", "akciya", "ulush"]):
                detected_balances["share_count"] = int(amt)
            elif contains_any(l_low, ["bank", "cash", "naqd", "raschetnyy", "started"]):
                detected_balances["opening_cash"] = amt
            continue

        # Otherwise it's a transaction
        is_income = contains_any(l_low, ["sold", "revenue", "income", "received", "earned", "tushum", "sotildi", "kirim", "vyruchka", "doxod", "popolnenie", "vzyali"])
        is_expense = contains_any(l_low, ["paid", "spent", "bought", "purchase", "cost", "expense", "to'landi", "xarid", "chiqim", "rasxod", "kupili", "potratili"])

        if is_income or is_expense or len(nums) > 0:
            tx_type = "income" if is_income and not is_expense else "expense"
            cat = infer_category(clause, tx_type)
            detected_txs.append({
                "date": now_date,
                "type": tx_type,
                "category": cat,
                "amount": amt,
                "note": clause[:80]
            })

    if detected_balances["opening_cash"] is not None and detected_balances["opening_equity"] is None:
        c = detected_balances["opening_cash"] or 0
        f = detected_balances["opening_fixed_assets"] or 0
        l = detected_balances["opening_loans"] or 0
        detected_balances["opening_equity"] = c + f - l

    return detected_balances, detected_txs

bal, txs = parse_financial_text(text)
print("BALANCES:", bal)
print("TRANSACTIONS COUNT:", len(txs))
for t in txs: print(" ", t)
