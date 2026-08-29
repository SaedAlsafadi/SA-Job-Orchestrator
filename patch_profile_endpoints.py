import re

with open("frontend/src/pages/CandidateProfilePage.tsx", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("api.get('/candidates/profile')", "api.get('/candidate-profile')")
content = content.replace("api.patch('/candidates/profile'", "api.put('/candidate-profile'")
content = content.replace("api.post('/candidates/import-resume'", "api.post('/candidate-profile/import-resume'")
content = content.replace("api.post('/candidates/profile/verify'", "api.post('/candidate-profile/verify'")

with open("frontend/src/pages/CandidateProfilePage.tsx", "w", encoding="utf-8") as f:
    f.write(content)
