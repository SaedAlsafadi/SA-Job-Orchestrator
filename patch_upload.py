import re

with open("frontend/src/pages/CandidateProfilePage.tsx", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("api.post('/candidates/upload'", "api.post('/candidates/import-resume'")

with open("frontend/src/pages/CandidateProfilePage.tsx", "w", encoding="utf-8") as f:
    f.write(content)
