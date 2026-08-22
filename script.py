import re
with open(r'C:\Users\saeda\.gemini\antigravity\brain\eb130e87-87ff-4123-8e97-66d3f9098fc3\task.md', 'r') as f:
    content = f.read()

content = content.replace('[/] Rewrite matching.py', '[x] Rewrite matching.py')
content = content.replace('[ ] Refactor KeywordAnalyzer', '[x] Refactor KeywordAnalyzer')
content = content.replace('[ ] Make deterministic score the primary', '[x] Make deterministic score the primary')
content = content.replace('[ ] Gracefully handle LLM failure', '[x] Gracefully handle LLM failure')
content = content.replace('[ ] Update Match/Result UI', '[x] Update Match/Result UI')
content = content.replace('[ ] Write 	est_matching.py', '[x] Write 	est_matching.py')
content = content.replace('[ ] Run Manual Integration script', '[x] Run Manual Integration script')

with open(r'C:\Users\saeda\.gemini\antigravity\brain\eb130e87-87ff-4123-8e97-66d3f9098fc3\task.md', 'w') as f:
    f.write(content)
