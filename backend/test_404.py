import httpx
print(httpx.get('https://apply.workable.com/api/v3/accounts/zhejiang-dingli-machinery-co/jobs', headers={'User-Agent': 'Mozilla/5.0'}).status_code)
