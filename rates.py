from http.server import BaseHTTPRequestHandler
import json, urllib.request, time

CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,OPTIONS','Content-Type':'application/json'}

_cache   = {}   # { key: {data, ts} }
_history = {}   # { 'USD': [{rate, ts}, ...] }  — oxirgi 7 ta

def get_cbu():
    cached = _cache.get('cbu')
    if cached and time.time() - cached['ts'] < 3600:
        return cached['data']
    try:
        req = urllib.request.Request(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
            headers={'User-Agent':'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read().decode())

        want = ['USD','EUR','RUB','GBP','CNY','KZT','TRY','JPY','CHF']
        rates = {}
        for item in raw:
            code = item.get('Ccy','')
            if code not in want:
                continue
            rate = float(item['Rate'])
            diff = float(item.get('Diff', 0))

            # Trend
            trend = 'up' if diff > 0 else ('down' if diff < 0 else 'stable')

            # Haftalik o'zgarish (history dan)
            hist = _history.get(code, [])
            week_chg = round(rate - hist[0]['rate'], 2) if len(hist) >= 2 else 0

            # Foiz o'zgarish
            prev = rate - diff
            diff_pct = round((diff / prev) * 100, 3) if prev else 0

            # Tarixga yozish (max 7 ta)
            hist.append({'rate': rate, 'ts': int(time.time())})
            _history[code] = hist[-7:]

            rates[code] = {
                'rate':       rate,
                'diff':       diff,
                'diff_pct':   diff_pct,
                'trend':      trend,
                'week_change': week_chg,
                'name_uz':    item.get('CcyNm_UZ', code),
                'name_ru':    item.get('CcyNm_RU', code),
                'name_en':    item.get('CcyNm_EN', code),
            }

        result = {'ok':True,'data':rates,'source':'cbu.uz','ts':int(time.time())}
        _cache['cbu'] = {'data': result, 'ts': time.time()}
        return result

    except Exception as e:
        # Xato: eski kesh qaytarish
        if _cache.get('cbu'):
            d = dict(_cache['cbu']['data'])
            d['cached'] = True
            return d
        return {'ok':False,'error':str(e),'data':{}}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.end_headers()
    def do_GET(self):
        body = json.dumps(get_cbu(), ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
