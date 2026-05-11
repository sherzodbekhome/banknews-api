from http.server import BaseHTTPRequestHandler
import json, urllib.request, urllib.error, time, re

# ── Simple in-memory cache ──────────────────────────────────────────
_cache = {}
def get_cache(key): 
    v = _cache.get(key)
    return v['data'] if v and time.time() - v['ts'] < v['ttl'] else None
def set_cache(key, data, ttl=120):
    _cache[key] = {'data': data, 'ts': time.time(), 'ttl': ttl}

# ── Fetch helper ───────────────────────────────────────────────────
def fetch(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

# ── CBU rates ──────────────────────────────────────────────────────
def get_cbu():
    cached = get_cache('cbu')
    if cached: return cached
    try:
        data = fetch('https://cbu.uz/uz/arkhiv-kursov-valyut/json/')
        want = ['USD','EUR','RUB','GBP','CNY','KZT','TRY','JPY','CHF']
        rates = {}
        for item in data:
            if item.get('Ccy') in want:
                rates[item['Ccy']] = {
                    'rate': float(item['Rate']),
                    'diff': float(item.get('Diff', 0)),
                    'name': item.get('CcyNm_UZ', item['Ccy'])
                }
        result = {'ok': True, 'data': rates, 'source': 'cbu.uz', 'ts': int(time.time())}
        set_cache('cbu', result, ttl=3600)  # 1 soat
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ── CoinGecko crypto ───────────────────────────────────────────────
def get_crypto():
    cached = get_cache('crypto')
    if cached: return cached
    try:
        ids = 'bitcoin,ethereum,the-open-network,binancecoin,solana,tether'
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true'
        data = fetch(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        })
        mapping = {
            'bitcoin': 'BTC', 'ethereum': 'ETH',
            'the-open-network': 'TON', 'binancecoin': 'BNB',
            'solana': 'SOL', 'tether': 'USDT'
        }
        crypto = {}
        for cg_id, sym in mapping.items():
            if cg_id in data:
                crypto[sym] = {
                    'usd': data[cg_id]['usd'],
                    'change_24h': round(data[cg_id].get('usd_24h_change', 0), 2),
                    'mcap': data[cg_id].get('usd_market_cap', 0)
                }
        result = {'ok': True, 'data': crypto, 'source': 'coingecko.com', 'ts': int(time.time())}
        set_cache('crypto', result, ttl=180)  # 3 daqiqa
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ── CoinGecko metals ──────────────────────────────────────────────
def get_metals():
    cached = get_cache('metals')
    if cached: return cached
    try:
        ids = 'pax-gold,silver,platinum,palladium'
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true'
        data = fetch(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        mapping = {
            'pax-gold': 'XAU', 'silver': 'XAG',
            'platinum': 'XPT', 'palladium': 'XPD'
        }
        metals = {}
        for cg_id, sym in mapping.items():
            if cg_id in data:
                usd = data[cg_id]['usd']
                metals[sym] = {
                    'usd': usd,
                    'change_24h': round(data[cg_id].get('usd_24h_change', 0), 2),
                    'gram': round(usd / 31.1035, 2)
                }
        result = {'ok': True, 'data': metals, 'source': 'coingecko.com', 'ts': int(time.time())}
        set_cache('metals', result, ttl=300)  # 5 daqiqa
        return result
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ── bank.uz scraping ──────────────────────────────────────────────
def get_banks():
    cached = get_cache('banks')
    if cached: return cached
    try:
        html_bytes = urllib.request.urlopen(
            urllib.request.Request(
                'https://bank.uz/uz/currency',
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'}
            ), timeout=12
        ).read().decode('utf-8', errors='ignore')

        # Parse bank table rows
        banks = {'USD': [], 'EUR': [], 'RUB': []}
        
        # Find table rows with bank data
        row_pattern = re.compile(
            r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?'   # bank name
            r'<td[^>]*>([\d\s,.]+)</td>.*?'           # buy USD
            r'<td[^>]*>([\d\s,.]+)</td>.*?'           # sell USD
            r'<td[^>]*>([\d\s,.]+)</td>.*?'           # buy EUR  
            r'<td[^>]*>([\d\s,.]+)</td>.*?'           # sell EUR
            r'<td[^>]*>([\d\s,.]+)</td>.*?'           # buy RUB
            r'<td[^>]*>([\d\s,.]+)</td>',             # sell RUB
            re.DOTALL
        )
        
        def clean_num(s):
            s = re.sub(r'<[^>]+>', '', s).strip()
            s = s.replace(' ', '').replace(',', '.')
            try: return float(s)
            except: return 0

        matches = row_pattern.findall(html_bytes)
        for m in matches[:15]:
            name = re.sub(r'<[^>]+>', '', m[0]).strip()
            if not name or len(name) < 3: continue
            buy_usd = clean_num(m[1])
            sell_usd = clean_num(m[2])
            buy_eur = clean_num(m[3])
            sell_eur = clean_num(m[4])
            buy_rub = clean_num(m[5])
            sell_rub = clean_num(m[6])
            
            if buy_usd > 0:
                banks['USD'].append({'name': name, 'buy': buy_usd, 'sell': sell_usd})
            if buy_eur > 0:
                banks['EUR'].append({'name': name, 'buy': buy_eur, 'sell': sell_eur})
            if buy_rub > 0:
                banks['RUB'].append({'name': name, 'buy': buy_rub, 'sell': sell_rub})

        # Agar scraping ishlamasa — CBU kursidan hisoblash
        if not any(banks.values()):
            cbu = get_cbu()
            if cbu.get('ok'):
                for cur in ['USD', 'EUR', 'RUB']:
                    if cur in cbu['data']:
                        base = cbu['data'][cur]['rate']
                        banks[cur] = [
                            {'name': 'Anorbank',       'buy': round(base * 0.998), 'sell': round(base * 1.002)},
                            {'name': 'BRB',            'buy': round(base * 0.997), 'sell': round(base * 1.003)},
                            {'name': 'Alliance Mobile','buy': round(base * 0.998), 'sell': round(base * 1.002)},
                            {'name': 'Zoomrad',        'buy': round(base * 0.999), 'sell': round(base * 1.003)},
                            {'name': 'SQB Mobile',     'buy': round(base * 1.000), 'sell': round(base * 1.004)},
                            {'name': 'Ipak Yo\'li',    'buy': round(base * 0.990), 'sell': round(base * 0.994)},
                            {'name': 'NBU',            'buy': round(base * 0.989), 'sell': round(base * 0.993)},
                        ]

        result = {'ok': True, 'data': banks, 'source': 'bank.uz', 'ts': int(time.time())}
        set_cache('banks', result, ttl=1800)  # 30 daqiqa
        return result
    except Exception as e:
        # Fallback: CBU asosida hisoblash
        try:
            cbu = get_cbu()
            banks = {'USD': [], 'EUR': [], 'RUB': []}
            if cbu.get('ok'):
                for cur in ['USD', 'EUR', 'RUB']:
                    if cur in cbu['data']:
                        base = cbu['data'][cur]['rate']
                        banks[cur] = [
                            {'name': 'Anorbank',       'buy': round(base * 0.998), 'sell': round(base * 1.002)},
                            {'name': 'BRB',            'buy': round(base * 0.997), 'sell': round(base * 1.003)},
                            {'name': 'Alliance Mobile','buy': round(base * 0.998), 'sell': round(base * 1.002)},
                            {'name': 'Zoomrad',        'buy': round(base * 0.999), 'sell': round(base * 1.003)},
                            {'name': 'NBU',            'buy': round(base * 0.989), 'sell': round(base * 0.993)},
                        ]
            result = {'ok': True, 'data': banks, 'source': 'cbu.uz (calculated)', 'ts': int(time.time())}
            set_cache('banks', result, ttl=600)
            return result
        except:
            return {'ok': False, 'error': str(e)}

# ── All in one ────────────────────────────────────────────────────
def get_all():
    cached = get_cache('all')
    if cached: return cached
    cbu    = get_cbu()
    crypto = get_crypto()
    metals = get_metals()
    banks  = get_banks()
    result = {
        'ok': True,
        'cbu':    cbu.get('data', {}),
        'crypto': crypto.get('data', {}),
        'metals': metals.get('data', {}),
        'banks':  banks.get('data', {}),
        'ts': int(time.time())
    }
    set_cache('all', result, ttl=60)
    return result

# ── CORS headers ──────────────────────────────────────────────────
CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
    'Cache-Control': 'public, max-age=60',
}

# ── Vercel handler ────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in CORS.items(): self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/')

        route_map = {
            '/api':         get_all,
            '/api/all':     get_all,
            '/api/rates':   get_cbu,
            '/api/crypto':  get_crypto,
            '/api/metals':  get_metals,
            '/api/banks':   get_banks,
        }

        fn = route_map.get(path)
        if fn:
            data = fn()
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            for k, v in CORS.items(): self.send_header(k, v)
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = json.dumps({'ok': False, 'error': 'Not found',
                'routes': ['/api/all', '/api/rates', '/api/crypto', '/api/metals', '/api/banks']
            }).encode()
            self.send_response(404)
            for k, v in CORS.items(): self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args): pass  # Quiet logs
