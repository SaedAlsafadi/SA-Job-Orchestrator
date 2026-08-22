import re

with open('app/api/v1/candidate_profile.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'system_prompt=system_prompt,\s*temperature=0\.1', 'system_prompt=system_prompt', content)

with open('app/api/v1/candidate_profile.py', 'w', encoding='utf-8') as f:
    f.write(content)
