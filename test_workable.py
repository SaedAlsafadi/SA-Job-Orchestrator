import urllib.request, json
req = urllib.request.Request(
    'https://apply.workable.com/api/v3/accounts/workable/jobs',
    headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'},
    data=b'{"query":"","location":[],"department":[],"worktype":[],"remote":[]}',
    method='POST'
)
res = urllib.request.urlopen(req)
data = json.loads(res.read())
print(len(data.get("results", [])))
print(data.get("results", [])[0] if data.get("results") else "No jobs")
