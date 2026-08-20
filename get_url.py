import urllib.request
import re

req = urllib.request.Request(
    'https://html.duckduckgo.com/html/?q=site:apply.workable.com+"Software+Engineer"',
    headers={'User-Agent': 'Mozilla/5.0'}
)
html = urllib.request.urlopen(req).read().decode("utf-8")
urls = re.findall(r"apply\.workable\.com/[a-zA-Z0-9-]+/j/[a-zA-Z0-9]+", html)
print(urls)
