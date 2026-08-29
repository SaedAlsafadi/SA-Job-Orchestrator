import re

with open("backend/.env", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'LLM__DEFAULT_MODEL=.*', 'LLM__DEFAULT_MODEL=openrouter/liquid/lfm-2.5-2.6b:free', content)

with open("backend/.env", "w", encoding="utf-8") as f:
    f.write(content)
