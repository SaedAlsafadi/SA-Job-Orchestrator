import re

with open("backend/.env", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'LLM__DEFAULT_MODEL=.*', 'LLM__DEFAULT_MODEL=openrouter/google/gemini-2.0-flash-lite-preview-02-05:free', content)

with open("backend/.env", "w", encoding="utf-8") as f:
    f.write(content)
