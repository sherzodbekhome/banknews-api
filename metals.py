from http.server import BaseHTTPRequestHandler
import json, urllib.request, time

CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,OPTIONS','Content-Type':'application/json'}

_cache   = {}
_history = {}  # metal trend tarixiy ma'lumot

MAPPING = {
    'pax-gold':'XAU','silver':'XAG','platinum':'XPT','palladium':'XPD'
}

def get_metals():
    cached = _cache.get('metals')
    if cached and time.time() - cached['ts'] < 300:
        return cached['data']
    try:
        ids = ','.join(MAPPING.keys())
        url = (f'https://api.coingecko.com/api/v3/simple/price'
               f'?ids={ids}&vs_currencies=usd&include_24hr_change=true')
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = json.loads(r.read().decode())

        metals = {}
        for cg_id, sym in MAPPING.items():
            if cg_id not in raw:
                continue
            d      = raw[cg_id]
            usd    = d.get('usd', 0)
            change = round(d.get('usd_24h_change', 0), 2)
            trend  = 'up' if change > 0 else ('down' if change < 0 else 'stable')
            gram   = round(usd / 31.1035, 2)  # troy untsiya → gram

            # Haftalik trend
            hist = _history.get(sym, [])
            week_chg = round(usd - hist[0]['usd'], 2) if len(hist) >= 2 else 0
            hist.append({'usd': usd, 'ts': int(time.time())})
            _history[sym] = hist[-7:]

            metals[sym] = {
                'usd':        usd,
                'change_24h': change,
                'trend':      trend,
                'week_change': week_chg,
                'gram_usd':   gram,
                'oz_usd':     usd,
            }

        result = {'ok':True,'data':metals,'source':'coingecko.com','ts':int(time.time())}
        _cache['metals'] = {'data': result, 'ts': time.time()}
        return result

    except Exception as e:
        if _cache.get('metals'):
            d = dict(_cache['metals']['data'])
            d['cached'] = True
            return d
        return {'ok':False,'error':str(e),'data':{}}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.end_headers()
    def do_GET(self):
        body = json.dumps(get_metals(), ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
