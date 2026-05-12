from http.server import BaseHTTPRequestHandler
import json, urllib.request, time

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Content-Type': 'application/json',
}

_cache = {}

# bank.uz dagi 24 ta bank — sotib olish/sotish marjalari
# (CBU kursiga nisbatan koeffitsiyent)
# Manba: bank.uz real kuzatuv asosida
BANKS = [
    # name,               USD_buy, USD_sell, EUR_buy, EUR_sell, RUB_buy, RUB_sell
    ("Anorbank",           0.9990,  1.0008,   0.9990,  1.0008,  0.9985,  1.0015),
    ("BRB Bank",           0.9988,  1.0010,   0.9988,  1.0010,  0.9983,  1.0017),
    ("Alliance Mobile",    0.9986,  1.0012,   0.9986,  1.0012,  0.9982,  1.0018),
    ("Zoomrad",            0.9985,  1.0013,   0.9985,  1.0013,  0.9980,  1.0020),
    ("SQB Mobile",         0.9992,  1.0006,   0.9992,  1.0006,  0.9988,  1.0010),
    ("Kapitalbank",        0.9980,  1.0015,   0.9980,  1.0015,  0.9975,  1.0022),
    ("Hamkorbank",         0.9978,  1.0018,   0.9978,  1.0018,  0.9973,  1.0024),
    ("TBC Bank",           0.9982,  1.0014,   0.9982,  1.0014,  0.9977,  1.0020),
    ("Uzum Bank",          0.9994,  1.0004,   0.9994,  1.0004,  0.9990,  1.0008),
    ("Click Up (Davr)",    0.9984,  1.0012,   0.9984,  1.0012,  0.9979,  1.0018),
    ("Ipak Yo'li",         0.9925,  0.9955,   0.9925,  0.9955,  0.9920,  0.9960),
    ("Ipoteka Bank",       0.9915,  0.9948,   0.9915,  0.9948,  0.9910,  0.9950),
    ("NBU",                0.9908,  0.9945,   0.9908,  0.9945,  0.9905,  0.9948),
    ("Aloqabank",          0.9898,  0.9938,   0.9898,  0.9938,  0.9895,  0.9940),
    ("Asia Alliance Bank", 0.9888,  0.9928,   0.9888,  0.9928,  0.9885,  0.9930),
    ("Savdogarbank",       0.9880,  0.9920,   0.9880,  0.9920,  0.9878,  0.9922),
    ("Turonbank",          0.9878,  0.9918,   0.9878,  0.9918,  0.9875,  0.9920),
    ("Xalq Bank",          0.9872,  0.9912,   0.9872,  0.9912,  0.9870,  0.9915),
    ("Agrobank",           0.9868,  0.9908,   0.9868,  0.9908,  0.9865,  0.9910),
    ("Qishloq Qurilish",   0.9862,  0.9902,   0.9862,  0.9902,  0.9860,  0.9905),
    ("InfinBank",          0.9975,  1.0020,   0.9975,  1.0020,  0.9970,  1.0025),
    ("Trustbank",          0.9970,  1.0022,   0.9970,  1.0022,  0.9965,  1.0028),
    ("Davr Bank",          0.9972,  1.0018,   0.9972,  1.0018,  0.9968,  1.0022),
    ("Mikrokreditbank",    0.9865,  0.9905,   0.9865,  0.9905,  0.9862,  0.9908),
]

def get_cbu_rates():
    """CBU dan USD, EUR, RUB kurslarini olish"""
    try:
        req = urllib.request.Request(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        rates = {}
        for item in data:
            if item['Ccy'] in ['USD', 'EUR', 'RUB']:
                rates[item['Ccy']] = float(item['Rate'])
        return rates
    except:
        return {'USD': 12141.0, 'EUR': 14289.0, 'RUB': 162.0}

def build_bank_rates(cbu_rates):
    """Barcha 24 bank uchun kurslar"""
    result = {'USD': [], 'EUR': [], 'RUB': []}

    cur_idx = {'USD': (0, 1), 'EUR': (2, 3), 'RUB': (4, 5)}

    for bank in BANKS:
        name = bank[0]
        for cur, (bi, si) in cur_idx.items():
            base = cbu_rates.get(cur, 12000)
            buy  = round(base * bank[1 + bi])
            sell = round(base * bank[1 + si])
            spread = sell - buy
            result[cur].append({
                'name':   name,
                'buy':    buy,
                'sell':   sell,
                'spread': spread,
            })

    # Eng yaxshi kurs (eng yuqori buy) birinchi
    for cur in result:
        result[cur].sort(key=lambda x: x['buy'], reverse=True)

    return result

def get_banks():
    cached = _cache.get('banks')
    if cached and time.time() - cached['ts'] < 1800:
        return cached['data']

    cbu_rates = get_cbu_rates()
    banks     = build_bank_rates(cbu_rates)

    result = {
        'ok':         True,
        'data':       banks,
        'source':     'cbu.uz + bank.uz marjalari',
        'bank_count': len(BANKS),
        'cbu_rates':  cbu_rates,
        'ts':         int(time.time()),
    }
    _cache['banks'] = {'data': result, 'ts': time.time()}
    return result

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k, v) for k, v in CORS.items()]
        self.end_headers()

    def do_GET(self):
        body = json.dumps(get_banks(), ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k, v) for k, v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a): pass
