import re

with open('app/api/v1/candidate_profile.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('return draft\n', 'return draft_response\n')

with open('app/api/v1/candidate_profile.py', 'w', encoding='utf-8') as f:
    f.write(content)
