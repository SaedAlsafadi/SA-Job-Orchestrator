import re

with open("frontend/src/pages/CandidateProfilePage.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Add error state
content = content.replace("const [loading, setLoading] = useState(true);", "const [loading, setLoading] = useState(true);\n  const [error, setError] = useState<string | null>(null);")

# Update catch block
new_catch = """    } catch (e: any) {
      if (e.response?.status === 404) {
        setFormData({
          identity: {}, location: {}, employment: {}, work_authorization: {},
          education: [], experience: [], skills: [], projects: [], certifications: [], languages: [], preferences: {}
        });
      } else {
        setError(e.response?.data?.detail || e.message || "Failed to load profile");
      }
    }"""
content = re.sub(r'\} catch \(e: any\) \{\s*if \(e\.response\?\.status === 404\) \{.*?\}.*?\}', new_catch, content, flags=re.DOTALL)

# Update render
new_render = """  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>Loading Profile...</div>;
  if (error) return <div style={{ padding: 40, textAlign: "center", color: "var(--failed)" }}>Error: {error}</div>;
  if (!formData) return null;"""
content = content.replace('if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>Loading Profile...</div>;\n  if (!formData) return null;', new_render)

with open("frontend/src/pages/CandidateProfilePage.tsx", "w", encoding="utf-8") as f:
    f.write(content)
