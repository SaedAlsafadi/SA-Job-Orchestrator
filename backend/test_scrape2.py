import httpx, re
html = httpx.get('https://apply.workable.com/zhejiang-dingli-machinery-co/', headers={'User-Agent': 'Mozilla/5.0'}).text
print(html[:500])
match = re.search(r'window\.initialState\s*=\s*(\{.*?\});', html)
if match:
    print("Found initialState")
else:
    print("No initialState")
