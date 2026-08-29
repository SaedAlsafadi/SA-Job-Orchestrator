import re

with open("frontend/src/pages/CandidateProfilePage.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# I will replace the whole fetchProfile block
old_block_pattern = r"const fetchProfile = async \(\) => \{.*?setLoading\(false\);\n  \};"
new_block = """const fetchProfile = async () => {
    try {
      const res = await api.get('/candidate-profile');
      setFormData(res.data);
      setDraftMode(res.data.status === "draft");
    } catch (e: any) {
      if (e.response?.status === 404) {
        setFormData({
          identity: {}, location: {}, employment: {}, work_authorization: {},
          education: [], experience: [], skills: [], projects: [], certifications: [], languages: [], preferences: {}
        });
      } else {
        setError(e.response?.data?.detail || e.message || "Failed to load profile");
      }
    }
    setLoading(false);
  };"""

content = re.sub(old_block_pattern, new_block, content, flags=re.DOTALL)

with open("frontend/src/pages/CandidateProfilePage.tsx", "w", encoding="utf-8") as f:
    f.write(content)
