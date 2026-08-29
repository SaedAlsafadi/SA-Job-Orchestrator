import urllib.request
import re

req = urllib.request.Request(
    'https://jobs.workable.com/en/view/3PwVgDsFEoHDWgdyeWroUS', 
    headers={'User-Agent': 'Mozilla/5.0'}
)
html = urllib.request.urlopen(req).read().decode('utf-8')
with open('workable_jobs.html', 'w', encoding='utf-8') as f:
    f.write(html)
