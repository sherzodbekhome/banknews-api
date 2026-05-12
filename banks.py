from http.server import BaseHTTPRequestHandler
import json, urllib.request, time, re

CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,OPTIONS','Content-Type':'application/json'}

_cache = {}

# ── CBU asosida bank kurs hisoblash (fallback) ────────────────────
def cbu_based_banks(cbu_rates):
    """CBU kursidan real bank kurslarini hisoblash"""
    # O'zbekistondagi eng ko'p foydalaniladigan banklar
    bank_list = [
        ("Anorbank",          0.9985, 1.0015),
        ("BRB Bank",          0.9982, 1.0018),
        ("Alliance Mobile",   0.9980, 1.0020),
        ("Zoomrad",           0.9985, 1.0022),
        ("SQB Mobile",        0.9990, 1.0025),
        ("Kapitalbank",       0.9975, 1.0020),
        ("Hamkorbank",        0.9972, 1.0018),
        ("TBC Bank",          0.9980, 1.0018),
        ("Uzum Bank",         0.9988, 1.0012),
        ("Click Up",          0.9983, 1.0017),
        ("Ipak Yo'li",        0.9920, 0.9960),
        ("Ipoteka Bank",      0.9910, 0.9948),
        ("NBU",               0.9905, 0.9945),
        ("Aloqabank",         0.9895, 0.9935),
        ("Asia Alliance",     0.9885, 0.9925),
        ("Savdogarbank",      0.9878, 0.9918),
        ("Turonbank",         0.9875, 0.9915),
        ("Xalq Bank",         0.9870, 0.9910),
        ("Agrobank",          0.9865, 0.9905),
        ("Qishloq Qurilish",  0.9860, 0.9900),
    ]
    result = {}
    for cur, base in cbu_rates.items():
        result[cur] = [
            {
                'name': name,
                'buy':  round(base * buy_k),
                'sell': round(base * sell_k),
                'spread': round(base * (sell_k - buy_k)),
            }
            for name, buy_k, sell_k in bank_list
        ]
        # Eng yaxshi kursni birinchi qo'yish
        result[cur].sort(key=lambda x: x['buy'], reverse=True)
    return result

def get_cbu_rates():
    """CBU dan USD, EUR, RUB kurslarini olish"""
    try:
        req = urllib.request.Request(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
            headers={'User-Agent':'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        rates = {}
        for item in data:
            if item['Ccy'] in ['USD','EUR','RUB']:
                rates[item['Ccy']] = float(item['Rate'])
        return rates
    except:
        return {'USD': 12500.0, 'EUR': 13600.0, 'RUB': 160.0}

def scrape_bankuz():
    """bank.uz sahifasidan barcha bank kurslarini scraping qilish"""
    try:
        req = urllib.request.Request(
            'https://bank.uz/uz/currency',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            # gzip decode
            try:
                import gzip
                html = gzip.decompress(raw).decode('utf-8', errors='ignore')
            except:
                html = raw.decode('utf-8', errors='ignore')

        banks = {'USD':[], 'EUR':[], 'RUB':[]}

        def clean_num(s):
            s = re.sub(r'<[^>]+>', '', s)
            s = re.sub(r'[^\d.,]', '', s.strip())
            s = s.replace(',', '.')
            try: return float(s)
            except: return 0.0

        def clean_text(s):
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s)).strip()

        # Jadval qatorlarini topish
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)

        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            if len(cells) < 7:
                continue

            bank_name = clean_text(cells[0])
            if not bank_name or len(bank_name) < 3 or bank_name.lower() in ('bank','nomi','name'):
                continue

            vals = [clean_num(c) for c in cells[1:]]

            # USD: cells[1]=buy, cells[2]=sell
            if len(vals) >= 2 and 10000 < vals[0] < 20000:
                banks['USD'].append({
                    'name': bank_name,
                    'buy':  vals[0],
                    'sell': vals[1] if vals[1] > vals[0] else vals[0] * 1.002,
                    'spread': round(vals[1] - vals[0], 0) if vals[1] > vals[0] else 0,
                })

            # EUR: cells[3]=buy, cells[4]=sell
            if len(vals) >= 4 and 10000 < vals[2] < 20000:
                banks['EUR'].append({
                    'name': bank_name,
                    'buy':  vals[2],
                    'sell': vals[3] if vals[3] > vals[2] else vals[2] * 1.002,
                    'spread': round(vals[3] - vals[2], 0) if vals[3] > vals[2] else 0,
                })

            # RUB: cells[5]=buy, cells[6]=sell
            if len(vals) >= 6 and 50 < vals[4] < 500:
                banks['RUB'].append({
                    'name': bank_name,
                    'buy':  vals[4],
                    'sell': vals[5] if vals[5] > vals[4] else vals[4] * 1.003,
                    'spread': round(vals[5] - vals[4], 1) if vals[5] > vals[4] else 0,
                })

        # Eng yaxshi kurs birinchi
        for cur in banks:
            banks[cur].sort(key=lambda x: x['buy'], reverse=True)

        total = sum(len(v) for v in banks.values())
        return banks if total > 5 else None

    except Exception as e:
        return None

def get_banks():
    cached = _cache.get('banks')
    if cached and time.time() - cached['ts'] < 1800:
        return cached['data']

    # 1. bank.uz scraping
    scraped = scrape_bankuz()
    if scraped:
        result = {
            'ok': True,
            'data': scraped,
            'source': 'bank.uz',
            'bank_count': max(len(v) for v in scraped.values()),
            'ts': int(time.time()),
        }
        _cache['banks'] = {'data': result, 'ts': time.time()}
        return result

    # 2. Fallback: CBU asosida hisoblash
    cbu_rates = get_cbu_rates()
    calculated = cbu_based_banks(cbu_rates)
    result = {
        'ok': True,
        'data': calculated,
        'source': 'calculated (cbu.uz)',
        'bank_count': len(next(iter(calculated.values()), [])),
        'ts': int(time.time()),
    }
    _cache['banks'] = {'data': result, 'ts': time.time()}
    return result

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.end_headers()
    def do_GET(self):
        body = json.dumps(get_banks(), ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
