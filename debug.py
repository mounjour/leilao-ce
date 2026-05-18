from playwright.sync_api import sync_playwright

URL = "https://leilo.com.br/leilao/eusebio-ceara/carros/chevrolet/spin-1-8l-at-activ7/ano.2022/35b6fc10-2530-11f1-a639-02420a000005"

with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    page = b.new_page()
    page.goto(URL, timeout=60000)
    
    # Espera mais tempo para JS carregar
    page.wait_for_timeout(8000)
    
    # Rola a página para forçar lazy loading
    page.keyboard.press("End")
    page.wait_for_timeout(2000)
    page.keyboard.press("Home")
    page.wait_for_timeout(2000)

    print("=== IMAGENS (src, data-src, srcset) ===\n")
    imgs = page.query_selector_all('img')
    for img in imgs:
        src     = img.get_attribute("src") or ""
        datasrc = img.get_attribute("data-src") or ""
        srcset  = img.get_attribute("srcset") or ""
        alt     = img.get_attribute("alt") or ""
        cls     = img.get_attribute("class") or ""
        if any([src, datasrc, srcset]):
            print(f"SRC:      {src[:100]}")
            print(f"DATA-SRC: {datasrc[:100]}")
            print(f"ALT: {alt} | CLASS: {cls[:50]}")
            print()

    print("\n=== HTML com 'leilomaster' ou 'cdndp' ===\n")
    html = page.content()
    import re
    matches = re.findall(r'https?://[^\s"\']+(?:leilomaster|cdndp)[^\s"\']*', html)
    for m in set(matches[:10]):
        print(m)

    b.close()