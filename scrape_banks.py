"""
bank.uz dan tijorat banklari kurslarini scraping qilish
GitHub Actions tomonidan ishga tushiriladi
"""
import json, os, time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Fallback koeffitsiyentlar (Playwright ishlamasa)
FALLBACK_COEFFS = [
    ("Universal Bank",         0.999017, 1.004782),
    ("O'zsanoatqurilish",      0.999017, 1.004782),
    ("MKBank",                 0.998193, 1.004782),
    ("Asakabank",              0.998193, 1.004782),
    ("Kapitalbank",            0.997781, 1.005194),
    ("O'zbekiston Milliy",     0.997369, 1.003958),
    ("InfinBank",              0.997369, 1.003135),
    ("Trastbank",              0.997369, 1.004782),
    ("Anorbank",               0.997369, 1.001487),
    ("Openbank",               0.996958, 1.002970),
    ("Asia Alliance Bank",     0.996546, 1.001487),
    ("Garant Bank",            0.996546, 1.004782),
    ("Aloqabank",              0.996546, 1.003958),
    ("Orient Finans Bank",     0.996134, 1.004782),
    ("Ipak Yuli Bank",         0.995722, 1.003958),
    ("Octobank",               0.995722, 1.001487),
    ("Turon Bank",             0.995722, 1.002311),
    ("Hayot Bank",             0.995722, 1.004782),
    ("Agrobank",               0.995722, 1.003135),
    ("Tenge Bank",             0.995722, 1.003958),
    ("Ziraat Bank",            0.995722, 1.004782),
    ("Ipoteka Bank",           0.995310, 1.004782),
    ("KDB Bank Uzbekistan",    0.995310, 1.005605),
    ("Poytaxt Bank",           0.995310, 1.004782),
]

def get_cbu_usd():
    """CBU dan USD kursini olish"""
    import urllib.request
    try:
        req = urllib.request.Request(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        for item in data:
            if item['Ccy'] == 'USD':
                return float(item['Rate'])
    except Exception as e:
        print(f"CBU xatosi: {e}")
    return 12141.94

def scrape_with_playwright():
    """bank.uz dan real narxlarni scraping"""
    result = {'USD': [], 'EUR': [], 'RUB': []}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        for currency in ['USD', 'RUB', 'EUR']:
            try:
                print(f"  {currency} scraping...")
                page.goto(f'https://bank.uz/uz/currency', wait_until='networkidle', timeout=30000)
                time.sleep(2)

                # Valyuta tugmasini bosish
                btn_map = {'USD': 'USD', 'RUB': 'RUB', 'EUR': 'EUR'}
                page.click(f'button:has-text("{btn_map[currency]}")', timeout=5000)
                time.sleep(1)

                # Jadval qatorlarini o'qish
                rows = page.query_selector_all('table tr, .currency-table tr, .rates-table tr')

                banks_cur = []
                for row in rows:
                    cells = row.query_selector_all('td')
                    if len(cells) >= 2:
                        try:
                            name_el = cells[0]
                            buy_el  = cells[1]
                            sell_el = cells[2] if len(cells) > 2 else None

                            name = name_el.inner_text().strip()
                            buy_txt  = buy_el.inner_text().strip().replace(' ', '').replace(',', '.')
                            sell_txt = sell_el.inner_text().strip().replace(' ', '').replace(',', '.') if sell_el else '0'

                            buy  = float(buy_txt.replace('\xa0', '').replace('so\'m', '').strip())
                            sell = float(sell_txt.replace('\xa0', '').replace('so\'m', '').strip())

                            if name and buy > 5000:
                                banks_cur.append({
                                    'name':   name,
                                    'buy':    int(buy),
                                    'sell':   int(sell),
                                    'spread': int(sell - buy),
                                })
                        except:
                            continue

                if banks_cur:
                    banks_cur.sort(key=lambda x: x['buy'], reverse=True)
                    result[currency] = banks_cur
                    print(f"  ✅ {currency}: {len(banks_cur)} ta bank topildi")
                else:
                    print(f"  ⚠️ {currency}: jadval topilmadi")

            except Exception as e:
                print(f"  ❌ {currency} xatosi: {e}")

        browser.close()

    return result

def fallback_from_cbu(cbu_usd):
    """CBU kursidan koeffitsiyentlar bilan hisoblash"""
    import urllib.request
    try:
        req = urllib.request.Request(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        cbu = {item['Ccy']: float(item['Rate']) for item in data if item['Ccy'] in ['USD','EUR','RUB']}
    except:
        cbu = {'USD': cbu_usd, 'EUR': cbu_usd*1.177, 'RUB': cbu_usd*0.01339}

    result = {}
    for cur in ['USD', 'EUR', 'RUB']:
        base = cbu.get(cur, cbu_usd)
        result[cur] = []
        for name, bk, sk in FALLBACK_COEFFS:
            buy  = round(base * bk)
            sell = round(base * sk)
            result[cur].append({
                'name':   name,
                'buy':    buy,
                'sell':   sell,
                'spread': sell - buy,
            })
        result[cur].sort(key=lambda x: x['buy'], reverse=True)
    return result

def main():
    print(f"🏦 Bank kurslari yangilanmoqda... {datetime.now():%Y-%m-%d %H:%M}")

    cbu_usd = get_cbu_usd()
    print(f"📊 CBU USD kursi: {cbu_usd:,.2f} so'm")

    # Playwright bilan scraping
    print("🌐 bank.uz dan scraping...")
    scraped = scrape_with_playwright()

    # Natija tekshirish
    total = sum(len(v) for v in scraped.values())
    print(f"📋 Jami: {total} ta yozuv topildi")

    if total >= 10:
        banks_data = scraped
        source = 'bank.uz (playwright)'
    else:
        print("⚠️ Scraping yetarli emas, CBU fallback ishlatilmoqda...")
        banks_data = fallback_from_cbu(cbu_usd)
        source = 'cbu.uz (calculated)'

    # JSON faylga saqlash
    output = {
        'ok':         True,
        'data':       banks_data,
        'source':     source,
        'bank_count': max(len(v) for v in banks_data.values()),
        'cbu_usd':    cbu_usd,
        'updated_at': datetime.now().isoformat(),
        'ts':         int(time.time()),
    }

    os.makedirs('data', exist_ok=True)
    with open('data/banks_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Saqlandi: data/banks_data.json ({source})")
    print(f"   USD banklari: {len(banks_data.get('USD',[]))} ta")
    print(f"   EUR banklari: {len(banks_data.get('EUR',[]))} ta")
    print(f"   RUB banklari: {len(banks_data.get('RUB',[]))} ta")

if __name__ == '__main__':
    main()
