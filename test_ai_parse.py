import sys; sys.path.insert(0, '.')
import app

app.init()
client = app.app.test_client()

c_res = client.post('/api/companies', json={'name': 'AI Smart Corp', 'type': 'company'})
cid = c_res.json['id']

sample_prompt = """
Company started with $40,000 in bank, $60,000 equipment, $15,000 loan, 2000 shares.
Yesterday we sold $12,000 products.
Paid $3,500 salaries to employees.
Paid $1,800 office rent.
Bought new machine equipment for $4,500.
Received $5,000 service fee.
"""

parse_res = client.post('/api/ai_parse', json={'text': sample_prompt, 'company_id': cid}).json

print('--- AI PARSED BALANCES ---')
print(parse_res['balances'])

print('\n--- AI PARSED TRANSACTIONS ---')
for tx in parse_res['transactions']:
    print(' ', tx)

assert parse_res['balances']['opening_cash'] == 40000.0
assert parse_res['balances']['opening_fixed_assets'] == 60000.0
assert parse_res['balances']['opening_loans'] == 15000.0
assert parse_res['balances']['share_count'] == 2000
assert len(parse_res['transactions']) == 5

apply_res = client.post('/api/ai_apply', json={
    'company_id': cid,
    'balances': parse_res['balances'],
    'transactions': parse_res['transactions']
}).json

print('\n--- AI APPLY RESULT ---')
print(apply_res)
assert apply_res['ok'] == True
assert apply_res['inserted'] == 5

report = client.get(f'/api/report?company={cid}').json
print('\nCompany Opening Cash after AI:', report['opening'])
print('Company Net Profit after AI:', report['pnl']['net_profit'])
print('Company Balance Sheet is Balanced?:', report['balance_sheet']['is_balanced'])

assert report['opening'] == 40000.0
assert report['balance_sheet']['is_balanced'] == True

print('\nALL AI ASSISTANT TESTS PASSED SUCCESSFULLY!')
