import httpx, re
html = httpx.get('https://apply.workable.com/zhejiang-dingli-machinery-co/', headers={'User-Agent': 'Mozilla/5.0'}).text
subdomain = re.search(r'\"subdomain\":\"([^\"]+)\"', html)
print(f"Subdomain: {subdomain.group(1) if subdomain else 'Not found'}")
