import sys
sys.path.insert(0, r"c:\Users\user\Desktop\Moliya")
import os
import io
import json
from app import app, init, db

def test_file_upload_parsing():
    init()
    client = app.test_client()

    # 1. Test CSV file upload
    csv_content = """Date,Type,Category,Amount,Note
2026-10-01,income,sales_products,15000,"Bulk product sale"
2026-10-02,expense,salaries,4200,"Monthly team salary"
2026-10-03,expense,rent,2100,"Main office rent"
"""
    
    data = {
        "text": "Company opening balance cash $50,000, loans $10,000, 5000 shares.",
        "file": (io.BytesIO(csv_content.encode("utf-8")), "transactions.csv")
    }

    res = client.post("/api/ai_parse_file", data=data, content_type="multipart/form-data")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.get_data(as_text=True)}"
    j = res.json

    print("--- PARSED BALANCES FROM FILE + PROMPT ---")
    print(j["balances"])
    assert j["balances"]["opening_cash"] == 50000.0
    assert j["balances"]["opening_loans"] == 10000.0
    assert j["balances"]["share_count"] == 5000

    print("\n--- PARSED TRANSACTIONS FROM CSV FILE ---")
    for tx in j["transactions"]:
        print(" ", tx)

    assert len(j["transactions"]) >= 3

    # 2. Test Image parsing (PIL thumbnail format simulation)
    from PIL import Image
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    img_data = {
        "text": "Invoice #4021: Paid $1,200 for equipment purchase on 2026-10-02",
        "file": (img_byte_arr, "receipt_invoice.png")
    }

    res_img = client.post("/api/ai_parse_file", data=img_data, content_type="multipart/form-data")
    assert res_img.status_code == 200
    j_img = res_img.json

    print("\n--- PARSED TRANSACTIONS FROM IMAGE INVOICE ---")
    print(j_img["transactions"])
    assert len(j_img["transactions"]) >= 1
    assert j_img["transactions"][0]["amount"] == 1200.0

    print("\nALL FILE AND PICTURE UPLOAD AI TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_file_upload_parsing()
