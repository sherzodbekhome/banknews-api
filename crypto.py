from http.server import BaseHTTPRequestHandler
import json, urllib.request, time

CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,OPTIONS','Content-Type':'application/json'}

_cache = {}

MAPPING = {
    'bitcoin':'BTC','ethereum':'ETH','the-open-network':'TON',
    'binancecoin':'BNB','solana':'SOL','tether':'USDT'
}

def get_crypto():
    cached = _cache.get('crypto')
    if cached and time.time() - cached['ts'] < 180:
        return cached['data']
    try:
        ids = ','.join(MAPPING.keys())
        url = (f'https://api.coingecko.com/api/v3/simple/price'
               f'?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true')
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = json.loads(r.read().decode())

        crypto = {}
        for cg_id, sym in MAPPING.items():
            if cg_id not in raw:
                continue
            d = raw[cg_id]
            usd    = d.get('usd', 0)
            change = round(d.get('usd_24h_change', 0), 2)
            mcap   = d.get('usd_market_cap', 0)
            trend  = 'up' if change > 0 else ('down' if change < 0 else 'stable')
            crypto[sym] = {
                'usd':       usd,
                'change_24h': change,
                'change_pct': change,
                'trend':     trend,
                'mcap':      mcap,
            }

        result = {'ok':True,'data':crypto,'source':'coingecko.com','ts':int(time.time())}
        _cache['crypto'] = {'data': result, 'ts': time.time()}
        return result

    except Exception as e:
        # Xato: eski kesh
        if _cache.get('crypto'):
            d = dict(_cache['crypto']['data'])
            d['cached'] = True
            return d
        return {'ok':False,'error':str(e),'data':{}}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.end_headers()
    def do_GET(self):
        body = json.dumps(get_crypto(), ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
