import calendar
import json
import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, g, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="/static")
DB = os.path.join(BASE_DIR, "moliya.db")
TYPES_FILE = os.path.join(BASE_DIR, "static", "types.json")

def load_cats_meta():
    try:
        with open(TYPES_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("cats", {})
    except Exception:
        return {}

def get_last_day_of_month(year_int, month_int):
    return calendar.monthrange(year_int, month_int)[1]

def get_months_in_range(start_ym, end_ym):
    try:
        sy, sm = map(int, start_ym.split("-"))
        ey, em = map(int, end_ym.split("-"))
    except Exception:
        now_ym = datetime.now().strftime("%Y-%m")
        return [now_ym]
    
    if (ey, em) < (sy, sm):
        sy, sm, ey, em = ey, em, sy, sm

    res = []
    cy, cm = sy, sm
    while (cy, cm) <= (ey, em):
        res.append(f"{cy:04d}-{cm:02d}")
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1
    return res

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS companies(
        id INTEGER PRIMARY KEY, 
        name TEXT NOT NULL, 
        opening REAL DEFAULT 0, 
        type TEXT DEFAULT 'other',
        opening_cash REAL DEFAULT 0,
        opening_fixed_assets REAL DEFAULT 0,
        opening_loans REAL DEFAULT 0,
        opening_equity REAL DEFAULT 0,
        share_count INTEGER DEFAULT 1000
    );
    CREATE TABLE IF NOT EXISTS tx(
        id INTEGER PRIMARY KEY, 
        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE, 
        date TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN('income','expense')), 
        category TEXT, 
        amount REAL NOT NULL, 
        note TEXT
    );
    """)
    for col, dtl in [
        ("type", "TEXT DEFAULT 'other'"),
        ("opening_cash", "REAL DEFAULT 0"),
        ("opening_fixed_assets", "REAL DEFAULT 0"),
        ("opening_loans", "REAL DEFAULT 0"),
        ("opening_equity", "REAL DEFAULT 0"),
        ("share_count", "INTEGER DEFAULT 1000")
    ]:
        try: c.execute(f"ALTER TABLE companies ADD COLUMN {col} {dtl}")
        except sqlite3.OperationalError: pass
    c.commit(); c.close()

def rows(q, a=()): return [dict(r) for r in db().execute(q, a).fetchall()]

@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")

@app.get("/api/companies")
def companies(): return jsonify(rows("SELECT * FROM companies ORDER BY name"))

@app.post("/api/companies")
def add_company():
    d = request.json
    opening_cash = float(d.get("opening_cash") or d.get("opening") or 0)
    opening_fa = float(d.get("opening_fixed_assets") or 0)
    opening_loans = float(d.get("opening_loans") or 0)
    
    calc_eq = opening_cash + opening_fa - opening_loans
    opening_equity = float(d.get("opening_equity") if d.get("opening_equity") is not None and d.get("opening_equity") != "" else calc_eq)
    shares = int(d.get("share_count") or 1000)
    if shares <= 0: shares = 1000

    cur = db().execute(
        """INSERT INTO companies(name, opening, type, opening_cash, opening_fixed_assets, opening_loans, opening_equity, share_count) 
           VALUES(?,?,?,?,?,?,?,?)""",
        (d["name"].strip(), opening_cash, d.get("type") or "other", opening_cash, opening_fa, opening_loans, opening_equity, shares)
    )
    db().commit(); return jsonify(id=cur.lastrowid), 201

@app.put("/api/companies/<int:i>")
def upd_company(i):
    d = request.json
    opening_cash = float(d.get("opening_cash") or d.get("opening") or 0)
    opening_fa = float(d.get("opening_fixed_assets") or 0)
    opening_loans = float(d.get("opening_loans") or 0)
    
    calc_eq = opening_cash + opening_fa - opening_loans
    opening_equity = float(d.get("opening_equity") if d.get("opening_equity") is not None and d.get("opening_equity") != "" else calc_eq)
    shares = int(d.get("share_count") or 1000)
    if shares <= 0: shares = 1000

    db().execute(
        """UPDATE companies SET name=?, opening=?, type=?, opening_cash=?, opening_fixed_assets=?, opening_loans=?, opening_equity=?, share_count=? 
           WHERE id=?""",
        (d["name"].strip(), opening_cash, d.get("type") or "other", opening_cash, opening_fa, opening_loans, opening_equity, shares, i)
    )
    db().commit(); return jsonify(ok=True)

@app.delete("/api/companies/<int:i>")
def del_company(i):
    db().execute("DELETE FROM tx WHERE company_id=?", (i,)); db().execute("DELETE FROM companies WHERE id=?", (i,))
    db().commit(); return jsonify(ok=True)

@app.get("/api/tx")
def list_tx():
    return jsonify(rows("SELECT * FROM tx WHERE company_id=? ORDER BY date DESC,id DESC", (request.args["company"],)))

@app.get("/api/account_tx")
def account_tx():
    c = request.args.get("company")
    account = request.args.get("account", "").strip()
    month = request.args.get("month", "").strip()
    from_month = request.args.get("from_month", "").strip()
    to_month = request.args.get("to_month", "").strip()

    all_txs = rows("SELECT * FROM tx WHERE company_id=? ORDER BY date DESC, id DESC", (c,))
    cats_meta = load_cats_meta()

    def matches(t):
        cat = t["category"]
        m = cats_meta.get(cat, {})
        pnl_grp = m.get("pnl_group")
        cf_act = m.get("cf_activity") or "operating"
        bal_grp = m.get("balance_group")
        if cat not in cats_meta:
            pnl_grp = "other_income" if t["type"] == "income" else "other_expense"

        t_ym = t["date"][:7]
        if month and t_ym != month:
            return False
        if from_month and t_ym < from_month:
            return False
        if to_month and t_ym > to_month:
            return False

        if not account or account == "all":
            return True
        if account == cat:
            return True
        if account == pnl_grp:
            return True
        if account == cf_act:
            return True
        if account == bal_grp:
            return True
        if account in ("cash", "cashAndEquivalents"):
            return True
        if account == "loans" and (bal_grp in ("loan_in", "loan_out") or cat in ("loan_in", "loan_out")):
            return True
        if account == "fixed_assets" and (bal_grp == "fixed_asset" or cat == "equipment"):
            return True
        if account == "contributed_capital" and (bal_grp == "equity_contribution" or cat == "investment"):
            return True
        if account == "withdrawn_capital" and (bal_grp == "equity_withdrawal" or cat == "owner_withdrawal"):
            return True
        return False

    filtered = [t for t in all_txs if matches(t)]
    return jsonify(filtered)

def clean(d):
    if d["type"] not in ("income", "expense") or float(d["amount"]) <= 0: raise ValueError
    return (d["date"], d["type"], (d.get("category") or "").strip(), float(d["amount"]), (d.get("note") or "").strip())

@app.post("/api/tx")
def add_tx():
    d = request.json
    try: v = clean(d)
    except (ValueError, KeyError): return jsonify(error="bad data"), 400
    db().execute("INSERT INTO tx(company_id,date,type,category,amount,note) VALUES(?,?,?,?,?,?)", (d["company_id"], *v))
    db().commit(); return jsonify(ok=True), 201

@app.put("/api/tx/<int:i>")
def upd_tx(i):
    try: v = clean(request.json)
    except (ValueError, KeyError): return jsonify(error="bad data"), 400
    db().execute("UPDATE tx SET date=?,type=?,category=?,amount=?,note=? WHERE id=?", (*v, i))
    db().commit(); return jsonify(ok=True)

@app.delete("/api/tx/<int:i>")
def del_tx(i):
    db().execute("DELETE FROM tx WHERE id=?", (i,)); db().commit(); return jsonify(ok=True)

def parse_ai_content(text, filename=None):
    detected_balances = {
        "opening_cash": None,
        "opening_fixed_assets": None,
        "opening_loans": None,
        "opening_equity": None,
        "share_count": None
    }
    detected_txs = []
    now_date = datetime.now().strftime("%Y-%m-%d")

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

    def contains_any(str_val, words):
        str_lower = str_val.lower()
        return any(w in str_lower for w in words)

    def infer_category(line_str, default_type):
        l_low = line_str.lower()
        for cat_k, kw_list in cat_keywords.items():
            if any(kw in l_low for kw in kw_list):
                return cat_k
        return "sales_products" if default_type == "income" else "other_expense"

    def extract_numbers(s):
        # find currency prefixed tokens first e.g. $1,200
        cur_tokens = re.findall(r'\$\s*\d+(?:[,\s_]\d{3})*(?:\.\d+)?', s)
        if cur_tokens:
            res = []
            for t in cur_tokens:
                clean = re.sub(r'[^\d\.]', '', t)
                try:
                    val = float(clean)
                    if val > 0: res.append(val)
                except ValueError: pass
            if res: return res

        # fallback: find tokens, ignoring ID hashtags like #4021
        clean_s = re.sub(r'#\d+', '', s)
        tokens = re.findall(r'\d+(?:[,\s_]\d{3})*(?:\.\d+)?', clean_s)
        res = []
        for t in tokens:
            clean = re.sub(r'[^\d\.]', '', t)
            try:
                val = float(clean)
                if val > 0: res.append(val)
            except ValueError: pass
        return res

    # 1. ALWAYS parse initial opening balances from sentences/lines
    sentences = [s.strip() for s in re.split(r'[\n;\.]', text) if s.strip()]
    for sentence in sentences:
        s_low = sentence.lower()
        is_startup = contains_any(s_low, ["started", "boshlang'ich", "nachalnyy", "initial", "open with", "opening", "starting", "bank balance", "equity", "capital"])
        if is_startup:
            clauses = [c.strip() for c in re.split(r',\s+|\band\b|\bva\b|\bi\b|;', sentence) if c.strip()]
            for clause in clauses:
                nums = extract_numbers(clause)
                if not nums: continue
                amt = nums[0]
                c_low = clause.lower()
                if contains_any(c_low, ["equipment", "asset", "uskuna", "jihoz", "oborudovanie", "property"]):
                    detected_balances["opening_fixed_assets"] = amt
                elif contains_any(c_low, ["debt", "loan", "kredit", "qarz", "dolg", "zaem"]):
                    detected_balances["opening_loans"] = amt
                elif contains_any(c_low, ["capital", "equity", "ustavnyy"]):
                    detected_balances["opening_equity"] = amt
                elif contains_any(c_low, ["shares", "stock", "akciya", "ulush"]):
                    detected_balances["share_count"] = int(amt)
                elif contains_any(c_low, ["bank", "cash", "naqd", "raschetnyy", "started", "money", "pul", "opening"]):
                    detected_balances["opening_cash"] = amt

    # 2. Try line-by-line CSV / tabular parsing if line has CSV structure
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        l_low = line.lower()
        if contains_any(l_low, ["started", "opening", "initial", "equity"]):
            continue  # skip initial balance text lines from transaction table
        if "," in line or "\t" in line or ";" in line or "|" in line:
            parts = [p.strip().strip('"\'') for p in re.split(r'[,;\t|]', line) if p.strip()]
            if len(parts) >= 3 and not contains_any(parts[0].lower(), ["date", "type", "category"]):
                d_val = None
                amt_val = None
                type_val = None
                note_parts = []
                for p in parts:
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', p):
                        d_val = p
                    elif contains_any(p, ["income", "kirim", "vyruchka", "doxod", "plus", "+"]):
                        type_val = "income"
                    elif contains_any(p, ["expense", "chiqim", "rasxod", "minus", "-"]):
                        type_val = "expense"
                    else:
                        nums = extract_numbers(p)
                        if nums and amt_val is None:
                            amt_val = nums[0]
                        else:
                            note_parts.append(p)
                if amt_val and amt_val > 0:
                    if not type_val:
                        note_str = " ".join(note_parts).lower()
                        type_val = "income" if contains_any(note_str, ["sale", "sold", "revenue", "received", "tushum"]) else "expense"
                    cat = infer_category(" ".join(note_parts), type_val)
                    detected_txs.append({
                        "date": d_val or now_date,
                        "type": type_val,
                        "category": cat,
                        "amount": amt_val,
                        "note": " ".join(note_parts)[:80] or "File Import"
                    })

    # 3. General natural language clause parsing for non-CSV prose lines
    if not detected_txs or len(lines) < 3:
        for sentence in sentences:
            s_low = sentence.lower()
            if contains_any(s_low, ["started", "boshlang'ich", "nachalnyy", "initial", "open with", "opening balance", "starting balance", "attached image file", "image file"]):
                continue

            clauses = [c.strip() for c in re.split(r',\s+|\band\b|\bva\b|\bi\b|;', sentence) if c.strip()]

            for clause in clauses:
                nums = extract_numbers(clause)
                if not nums: continue
                amt = nums[0]
                c_low = clause.lower()

                is_income = contains_any(c_low, ["sold", "revenue", "income", "received", "earned", "tushum", "sotildi", "kirim", "vyruchka", "doxod", "popolnenie"])
                is_expense = contains_any(c_low, ["paid", "spent", "bought", "purchase", "cost", "expense", "to'landi", "xarid", "chiqim", "rasxod", "kupili", "potratili", "total"])

                if is_income or is_expense or len(nums) > 0:
                    tx_type = "income" if is_income and not is_expense else "expense"
                    cat = infer_category(clause, tx_type)
                    date_match = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', clause)
                    tx_date = date_match.group(1) if date_match else now_date
                    detected_txs.append({
                        "date": tx_date,
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

    fn_label = f" (File: {filename})" if filename else ""
    summary = f"AI Assistant analyzed content{fn_label} and identified initial balances and {len(detected_txs)} transactions."
    
    return {
        "balances": detected_balances,
        "transactions": detected_txs,
        "summary": summary
    }

def extract_text_from_file_bytes(file_bytes, filename):
    fname = (filename or "").lower()
    text = ""
    # 1. Plain text / CSV / JSON / MD
    if any(fname.endswith(ext) for ext in [".txt", ".csv", ".tsv", ".json", ".md", ".log"]):
        try:
            text = file_bytes.decode("utf-8")
        except Exception:
            text = file_bytes.decode("latin-1", errors="ignore")
    # 2. PDF document
    elif fname.endswith(".pdf"):
        try:
            # Extract plain text streams from PDF
            raw = file_bytes.decode("latin-1", errors="ignore")
            # find text inside parenthesis in Tj or TJ streams or raw BT...ET
            stream_matches = re.findall(r'\(([^)]+)\)', raw)
            if stream_matches:
                text = " ".join([m for m in stream_matches if len(m.strip()) > 1])
            else:
                text = raw
        except Exception:
            text = file_bytes.decode("latin-1", errors="ignore")
    # 3. Excel Spreadsheets (.xlsx, .xls)
    elif fname.endswith(".xlsx") or fname.endswith(".xls"):
        try:
            import pandas as pd
            import io
            df = pd.read_excel(io.BytesIO(file_bytes))
            text = df.to_string()
        except Exception:
            # fallback string extraction
            text = file_bytes.decode("latin-1", errors="ignore")
    # 4. Images (.png, .jpg, .jpeg, .webp, .bmp, .gif)
    elif any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]):
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(file_bytes))
            text = f"Attached image file: {fname}. "
            try:
                import pytesseract
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text.strip():
                    text += ocr_text
            except Exception:
                pass
        except Exception:
            text = ""
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    return text

@app.post("/api/ai_parse")
def ai_parse():
    d = request.json or {}
    text = (d.get("text") or "").strip()
    file_text = (d.get("file_text") or "").strip()
    combined_text = (text + "\n" + file_text).strip()

    if not combined_text:
        return jsonify(error="Empty content"), 400

    parsed = parse_ai_content(combined_text)
    parsed["extracted_text"] = file_text
    return jsonify(parsed)

@app.post("/api/ai_parse_file")
def ai_parse_file():
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify(error="No file selected"), 400
    
    file_bytes = f.read()
    extracted_text = extract_text_from_file_bytes(file_bytes, f.filename)
    
    prompt = (request.form.get("text") or "").strip()
    full_content = (prompt + "\n" + extracted_text).strip()
    
    parsed = parse_ai_content(full_content, filename=f.filename)
    parsed["extracted_text"] = extracted_text
    return jsonify(parsed)

@app.post("/api/ai_apply")
def ai_apply():
    d = request.json or {}
    company_id = d.get("company_id")
    if not company_id:
        return jsonify(error="company_id required"), 400

    balances = d.get("balances") or {}
    transactions = d.get("transactions") or []

    if any(v is not None for v in balances.values()):
        co = rows("SELECT * FROM companies WHERE id=?", (company_id,))
        if co:
            co = co[0]
            c_cash = float(balances.get("opening_cash") if balances.get("opening_cash") is not None else co["opening_cash"])
            c_fa = float(balances.get("opening_fixed_assets") if balances.get("opening_fixed_assets") is not None else co["opening_fixed_assets"])
            c_loans = float(balances.get("opening_loans") if balances.get("opening_loans") is not None else co["opening_loans"])
            c_eq = float(balances.get("opening_equity") if balances.get("opening_equity") is not None else co["opening_equity"])
            c_shares = int(balances.get("share_count") if balances.get("share_count") is not None else co["share_count"])
            if c_shares <= 0: c_shares = 1000

            db().execute(
                """UPDATE companies SET opening=?, opening_cash=?, opening_fixed_assets=?, opening_loans=?, opening_equity=?, share_count=? WHERE id=?""",
                (c_cash, c_cash, c_fa, c_loans, c_eq, c_shares, company_id)
            )

    inserted_count = 0
    for tx in transactions:
        try:
            amt = float(tx.get("amount") or 0)
            if amt > 0 and tx.get("type") in ("income", "expense"):
                db().execute(
                    "INSERT INTO tx(company_id, date, type, category, amount, note) VALUES(?,?,?,?,?,?)",
                    (company_id, tx.get("date") or datetime.now().strftime("%Y-%m-%d"), tx["type"], (tx.get("category") or ("sales_products" if tx["type"]=="income" else "other_expense")).strip(), amt, (tx.get("note") or "AI Assistant Import").strip())
                )
                inserted_count += 1
        except Exception:
            pass

    db().commit()
    return jsonify(ok=True, inserted=inserted_count)

@app.get("/api/report")
def report():
    c = request.args.get("company")
    if not c:
        return jsonify(error="company required"), 400
    co_rows = rows("SELECT * FROM companies WHERE id=?", (c,))
    if not co_rows:
        return jsonify(error="company not found"), 404
    co = co_rows[0]

    all_txs = rows("SELECT * FROM tx WHERE company_id=? ORDER BY date ASC, id ASC", (c,))
    cats_meta = load_cats_meta()

    def get_meta(cat, tx_type):
        m = cats_meta.get(cat, {})
        pnl = m.get("pnl_group")
        cf = m.get("cf_activity") or "operating"
        bal = m.get("balance_group")
        if cat not in cats_meta:
            pnl = "other_income" if tx_type == "income" else "other_expense"
            cf = "operating"
            bal = None
        return pnl, cf, bal

    now_ym = datetime.now().strftime("%Y-%m")
    if all_txs:
        min_tx_ym = all_txs[0]["date"][:7]
        max_tx_ym = all_txs[-1]["date"][:7]
    else:
        min_tx_ym = now_ym
        max_tx_ym = now_ym

    from_month = request.args.get("from_month") or request.args.get("from", "")[:7]
    to_month = request.args.get("to_month") or request.args.get("to", "")[:7]

    if not from_month:
        from_month = min_tx_ym
    if not to_month:
        to_month = max(max_tx_ym, now_ym)

    months_list = get_months_in_range(from_month, to_month)

    start_y, start_m = map(int, months_list[0].split("-"))
    end_y, end_m = map(int, months_list[-1].split("-"))
    from_date = f"{start_y:04d}-{start_m:02d}-01"
    to_date = f"{end_y:04d}-{end_m:02d}-{get_last_day_of_month(end_y, end_m):02d}"

    opening_cash = float(co.get("opening_cash") or co.get("opening") or 0)
    opening_fa = float(co.get("opening_fixed_assets") or 0)
    opening_loans = float(co.get("opening_loans") or 0)
    calc_eq = opening_cash + opening_fa - opening_loans
    opening_eq = float(co.get("opening_equity") if co.get("opening_equity") is not None else calc_eq)

    share_count = int(co.get("share_count") or 1000)
    if share_count <= 0: share_count = 1000

    def calc_pnl(tx_subset):
        res = {
            "revenue": 0.0, "cogs": 0.0, "gross_profit": 0.0,
            "opex": 0.0, "operating_profit": 0.0,
            "other_income": 0.0, "other_expense": 0.0,
            "finance_income": 0.0, "finance_cost": 0.0,
            "profit_before_tax": 0.0, "tax": 0.0, "net_profit": 0.0,
            "eps": 0.0
        }
        for t in tx_subset:
            pnl_grp, _, _ = get_meta(t["category"], t["type"])
            amt = float(t["amount"])
            if pnl_grp in res:
                res[pnl_grp] += amt
        res["gross_profit"] = res["revenue"] - res["cogs"]
        res["operating_profit"] = res["gross_profit"] - res["opex"]
        res["profit_before_tax"] = (
            res["operating_profit"]
            + res["other_income"] - res["other_expense"]
            + res["finance_income"] - res["finance_cost"]
        )
        res["net_profit"] = res["profit_before_tax"] - res["tax"]
        res["eps"] = res["net_profit"] / share_count
        return res

    def calc_balance_sheet(target_date):
        txs_up_to = [t for t in all_txs if t["date"] <= target_date]
        cash = opening_cash + sum(
            float(t["amount"]) if t["type"] == "income" else -float(t["amount"])
            for t in txs_up_to
        )
        fixed_assets = opening_fa + sum(
            float(t["amount"]) if t["type"] == "expense" else -float(t["amount"])
            for t in txs_up_to
            if get_meta(t["category"], t["type"])[2] == "fixed_asset"
        )
        total_assets = cash + fixed_assets

        loans = opening_loans + sum(
            float(t["amount"]) if (t["type"] == "income" and get_meta(t["category"], t["type"])[2] == "loan_in")
            else -float(t["amount"]) if (t["type"] == "expense" and get_meta(t["category"], t["type"])[2] == "loan_out")
            else 0.0
            for t in txs_up_to
        )
        total_liabilities = loans

        initial_capital = opening_eq
        contributed_capital = sum(
            float(t["amount"])
            for t in txs_up_to
            if t["type"] == "income" and get_meta(t["category"], t["type"])[2] == "equity_contribution"
        )
        withdrawn_capital = sum(
            float(t["amount"])
            for t in txs_up_to
            if t["type"] == "expense" and get_meta(t["category"], t["type"])[2] == "equity_withdrawal"
        )

        retained_earnings = 0.0
        for t in txs_up_to:
            pnl_grp, _, _ = get_meta(t["category"], t["type"])
            amt = float(t["amount"])
            if pnl_grp in ("revenue", "other_income", "finance_income"):
                retained_earnings += amt
            elif pnl_grp in ("cogs", "opex", "other_expense", "finance_cost", "tax"):
                retained_earnings -= amt

        total_equity = initial_capital + contributed_capital - withdrawn_capital + retained_earnings
        total_liabilities_and_equity = total_liabilities + total_equity
        is_balanced = abs(total_assets - total_liabilities_and_equity) < 0.001
        bvps = total_equity / share_count

        return {
            "assets": {"cash": cash, "fixed_assets": fixed_assets, "total_assets": total_assets},
            "liabilities": {"loans": loans, "total_liabilities": total_liabilities},
            "equity": {
                "initial_capital": initial_capital,
                "contributed_capital": contributed_capital,
                "withdrawn_capital": withdrawn_capital,
                "retained_earnings": retained_earnings,
                "total_equity": total_equity
            },
            "total_liabilities_and_equity": total_liabilities_and_equity,
            "is_balanced": is_balanced,
            "bvps": bvps
        }

    def calc_cash_flow(m_start_date, m_end_date):
        txs_before = [t for t in all_txs if t["date"] < m_start_date]
        txs_in = [t for t in all_txs if t["date"] >= m_start_date and t["date"] <= m_end_date]

        op_cash_start = opening_cash + sum(
            float(t["amount"]) if t["type"] == "income" else -float(t["amount"])
            for t in txs_before
        )
        op_cf, inv_cf, fin_cf = 0.0, 0.0, 0.0
        for t in txs_in:
            _, cf_act, _ = get_meta(t["category"], t["type"])
            amt = float(t["amount"]) if t["type"] == "income" else -float(t["amount"])
            if cf_act == "investing":
                inv_cf += amt
            elif cf_act == "financing":
                fin_cf += amt
            else:
                op_cf += amt
        net_cf = op_cf + inv_cf + fin_cf
        ending_cash = op_cash_start + net_cf
        return {
            "opening_cash": op_cash_start,
            "operating_cf": op_cf,
            "investing_cf": inv_cf,
            "financing_cf": fin_cf,
            "net_cash_flow": net_cf,
            "ending_cash": ending_cash
        }

    monthly_pnl = {}
    monthly_cash_flow = {}
    monthly_balance_sheet = {}

    for m in months_list:
        my, mm = map(int, m.split("-"))
        m_start = f"{m}-01"
        m_end = f"{m}-{get_last_day_of_month(my, mm):02d}"

        txs_m = [t for t in all_txs if t["date"] >= m_start and t["date"] <= m_end]
        monthly_pnl[m] = calc_pnl(txs_m)
        monthly_cash_flow[m] = calc_cash_flow(m_start, m_end)
        monthly_balance_sheet[m] = calc_balance_sheet(m_end)

    period_txs = [t for t in all_txs if t["date"] >= from_date and t["date"] <= to_date]
    total_pnl = calc_pnl(period_txs)
    total_cash_flow = calc_cash_flow(from_date, to_date)
    latest_balance_sheet = calc_balance_sheet(to_date)

    monthly_pnl["total"] = total_pnl
    monthly_cash_flow["total"] = total_cash_flow
    monthly_balance_sheet["total"] = latest_balance_sheet

    inc = sum(r["amount"] for r in rows("SELECT amount FROM tx WHERE company_id=? AND type='income'", (c,)))
    exp = sum(r["amount"] for r in rows("SELECT amount FROM tx WHERE company_id=? AND type='expense'", (c,)))
    cats = rows("SELECT type,category,SUM(amount) total FROM tx WHERE company_id=? GROUP BY type,category ORDER BY total DESC", (c,))
    months = rows("""SELECT substr(date,1,7) month,
        SUM(CASE WHEN type='income' THEN amount ELSE 0 END) income,
        SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) expense
        FROM tx WHERE company_id=? GROUP BY month ORDER BY month""", (c,))

    valuation = {
        "share_count": share_count,
        "eps": total_pnl["eps"],
        "bvps": latest_balance_sheet["bvps"],
        "net_profit": total_pnl["net_profit"],
        "total_equity": latest_balance_sheet["equity"]["total_equity"],
        "opening_cash": opening_cash,
        "opening_fixed_assets": opening_fa,
        "opening_loans": opening_loans,
        "opening_equity": opening_eq
    }

    return jsonify(
        opening=opening_cash,
        opening_fixed_assets=opening_fa,
        opening_loans=opening_loans,
        opening_equity=opening_eq,
        share_count=share_count,
        income=inc,
        expense=exp,
        profit=inc - exp,
        balance=opening_cash + inc - exp,
        categories=cats,
        months=months,
        start_month=months_list[0],
        end_month=months_list[-1],
        from_date=from_date,
        to_date=to_date,
        months_list=months_list,
        pnl=total_pnl,
        cash_flow=total_cash_flow,
        balance_sheet=latest_balance_sheet,
        monthly_pnl=monthly_pnl,
        monthly_cash_flow=monthly_cash_flow,
        monthly_balance_sheet=monthly_balance_sheet,
        valuation=valuation
    )

init()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

