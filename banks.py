from http.server import BaseHTTPRequestHandler
import json, urllib.request, time, os

CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,OPTIONS','Content-Type':'application/json'}

_cache = {}

FALLBACK = [
    ("Universal Bank",0.999017,1.004782),("O'zsanoatqurilish",0.999017,1.004782),
    ("MKBank",0.998193,1.004782),("Asakabank",0.998193,1.004782),
    ("Kapitalbank",0.997781,1.005194),("O'zbekiston Milliy",0.997369,1.003958),
    ("InfinBank",0.997369,1.003135),("Trastbank",0.997369,1.004782),
    ("Anorbank",0.997369,1.001487),("Openbank",0.996958,1.002970),
    ("Asia Alliance Bank",0.996546,1.001487),("Garant Bank",0.996546,1.004782),
    ("Aloqabank",0.996546,1.003958),("Orient Finans Bank",0.996134,1.004782),
    ("Ipak Yuli Bank",0.995722,1.003958),("Octobank",0.995722,1.001487),
    ("Turon Bank",0.995722,1.002311),("Hayot Bank",0.995722,1.004782),
    ("Agrobank",0.995722,1.003135),("Tenge Bank",0.995722,1.003958),
    ("Ziraat Bank",0.995722,1.004782),("Ipoteka Bank",0.995310,1.004782),
    ("KDB Bank Uzbekistan",0.995310,1.005605),("Poytaxt Bank",0.995310,1.004782),
]

def get_cbu_rates():
    try:
        req = urllib.request.Request('https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
                                     headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        return {i['Ccy']:float(i['Rate']) for i in data if i['Ccy'] in ['USD','EUR','RUB']}
    except:
        return {'USD':12141.94,'EUR':14289.85,'RUB':162.63}

def load_json_file():
    """GitHub Actions yangilagan faylni o'qish"""
    base = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(base,'..','data','banks_data.json'),
        'data/banks_data.json',
        '/var/task/data/banks_data.json',
    ]
    for p in paths:
        try:
            with open(os.path.normpath(p),'r',encoding='utf-8') as f:
                d = json.load(f)
            if d.get('ok') and d.get('data'):
                return d
        except:
            continue
    return None

def calc_fallback(cbu):
    res = {}
    for cur in ['USD','EUR','RUB']:
        base = cbu.get(cur, 12141.94)
        res[cur] = sorted([{
            'name':name,'buy':round(base*bk),
            'sell':round(base*sk),'spread':round(base*(sk-bk))
        } for name,bk,sk in FALLBACK], key=lambda x:x['buy'], reverse=True)
    return res

def get_banks():
    cached = _cache.get('banks')
    if cached and time.time()-cached['ts'] < 1800:
        return cached['data']

    cbu = get_cbu_rates()
    file_data = load_json_file()

    if file_data:
        stored_usd = file_data.get('cbu_usd', 12141.94)
        current_usd = cbu.get('USD', stored_usd)
        ratio = current_usd / stored_usd if stored_usd else 1.0

        if abs(ratio - 1.0) > 0.005:
            # CBU o'zgardi - qayta hisoblash
            banks = calc_fallback(cbu)
            source = f'recalculated (CBU {ratio:.3f}x)'
        else:
            banks = file_data['data']
            source = f"bank.uz ({file_data.get('updated_at','?')[:10]})"
    else:
        banks = calc_fallback(cbu)
        source = 'cbu.uz (calculated)'

    result = {
        'ok':True,'data':banks,'source':source,
        'bank_count':max(len(v) for v in banks.values()),
        'cbu_usd':cbu.get('USD',12141.94),'ts':int(time.time())
    }
    _cache['banks'] = {'data':result,'ts':time.time()}
    return result

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.end_headers()
    def do_GET(self):
        body = json.dumps(get_banks(),ensure_ascii=False).encode()
        self.send_response(200)
        [self.send_header(k,v) for k,v in CORS.items()]
        self.send_header('Content-Length',len(body))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a): pass
