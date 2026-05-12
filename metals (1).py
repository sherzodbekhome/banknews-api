from http.server import BaseHTTPRequestHandler
import json, urllib.request, time

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Content-Type': 'application/json',
}

_cache = {}
_history = {}

def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

# Har bir metal uchun alohida CoinGecko ID
METAL_IDS = {
    'XAU': ['pax-gold', 'tether-gold'],        # Oltin
    'XAG': ['silver', 'silver-token'],          # Kumush
    'XPT': ['platinum', 'platinum-token'],      # Platina
    'XPD': ['palladium'],                       # Palladiy
}

# Spot narxlar (so'nggi ma'lumot, API ishlamasa)
SPOT_PRICES = {
    'XAU': {'usd': 3320.0,  'change': 0.4},
    'XAG': {'usd': 33.2,    'change': -0.3},
    'XPT': {'usd': 1050.0,  'change': 0.6},
    'XPD': {'usd': 1020.0,  'change': -0.1},
}

def fetch_metal(sym):
    """Bitta metalni CoinGecko dan olish"""
    ids_to_try = METAL_IDS.get(sym, [])
    for cg_id in ids_to_try:
        try:
            url = (f'https://api.coingecko.com/api/v3/simple/price'
                   f'?ids={cg_id}&vs_currencies=usd&include_24hr_change=true')
            d = fetch_json(url, timeout=8)
            if cg_id in d and d[cg_id].get('usd', 0) > 0:
                usd = d[cg_id]['usd']
                change = d[cg_id].get('usd_24h_change', 0) or 0
                return {'usd': usd, 'change': round(change, 2)}
        except:
            continue
    return None

def get_metals():
    cached = _cache.get('metals')
    if cached and time.time() - cached['ts'] < 300:
        return cached['data']

    metals = {}

    for sym in ['XAU', 'XAG', 'XPT', 'XPD']:
        result = fetch_metal(sym)

        if result and result['usd'] > 0:
            usd = result['usd']
            change = result['change']
        else:
            # Spot fallback
            fb = SPOT_PRICES[sym]
            usd = fb['usd']
            change = fb['change']

        # Trend tarix
        hist = _history.get(sym, [])
        week_change = round(usd - hist[0]['usd'], 2) if len(hist) >= 2 else 0
        hist.append({'usd': usd, 'ts': int(time.time())})
        _history[sym] = hist[-7:]

        metals[sym] = {
            'usd':        usd,
            'change_24h': change,
            'gram_usd':   round(usd / 31.1035, 4),
            'week_change': week_change,
            'source':     'live' if result else 'fallback',
        }

    result = {
        'ok': True,
        'data': metals,
        'source': 'coingecko + spot',
        'ts': int(time.time()),
    }
    _cache['metals'] = {'data': result, 'ts': time.time()}
    return result

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k, v) for k, v in CORS.items()]
        self.end_headers()

    def do_GET(self):
        data = get_metals()
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k, v) for k, v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a): pass
