import React, { useState, useEffect, useRef } from "react";
import api from "@/services/api";

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px", background: "var(--surface-2)",
  border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
  color: "var(--text)", fontFamily: "var(--font)", fontSize: "14px",
  marginTop: "4px", marginBottom: "16px", boxSizing: "border-box"
};
const textareaStyle: React.CSSProperties = {
  ...inputStyle,
  minHeight: "100px",
  resize: "vertical"
};
const labelStyle: React.CSSProperties = { fontSize: "13px", color: "var(--text-2)", fontWeight: 600, display: "block" };
const cardStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)", padding: "24px", marginBottom: "24px", boxShadow: "var(--shadow-1)"
};
const buttonStyle: React.CSSProperties = {
  background: "var(--accent)", color: "var(--accent-ink)", padding: "12px 24px",
  border: "none", borderRadius: "var(--r-md)", fontWeight: 700, cursor: "pointer", fontSize: "14px"
};

export function CandidateProfilePage() {
  const [formData, setFormData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draftMode, setDraftMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
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
    }, employment: {}, work_authorization: {},
          education: [], experience: [], skills: [], projects: [], certifications: [], languages: [], preferences: {}
        });
      }
    }
    setLoading(false);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsImporting(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api.post('/candidate-profile/import-resume', fd, { headers: { "Content-Type": "multipart/form-data" } });
      setFormData(res.data);
      setDraftMode(true);
    } catch (err: any) {
      alert("Failed to upload CV: " + (err.response?.data?.detail || err.message));
    }
    setIsImporting(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      if (draftMode) {
        await api.post('/candidate-profile/verify', formData);
      } else {
        await api.put('/candidate-profile', formData);
      }
      alert("Profile saved successfully!");
      setDraftMode(false);
    } catch (err: any) {
      alert("Failed to save profile: " + (err.response?.data?.detail || err.message));
    }
    setIsSaving(false);
  };

  const updateField = (category: string, field: string, value: string) => {
    setFormData((prev: any) => {
      const newData = { ...prev };
      const current = newData[category] ? newData[category][field] : null;
      if (!newData[category]) newData[category] = {};
      if (current && typeof current === 'object' && 'value' in current) {
        newData[category][field].value = value;
      } else {
        newData[category][field] = value;
      }
      return newData;
    });
  };

    if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>Loading Profile...</div>;
  if (error) return <div style={{ padding: 40, textAlign: "center", color: "var(--failed)" }}>Error: {error}</div>;
  if (!formData) return null;

  return (
    <div style={{ padding: "32px", maxWidth: "900px", margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "32px" }}>
        <div>
          <h1 style={{ margin: "0 0 8px 0", fontSize: "28px" }}>Candidate Profile</h1>
          <p style={{ color: "var(--text-2)", margin: 0 }}>Manage your master profile or import from your resume to autocomplete fields.</p>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <input type="file" accept=".pdf,.docx" style={{ display: "none" }} ref={fileInputRef} onChange={handleFileUpload} />
          
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isImporting}
            style={{ ...buttonStyle, background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}
          >
            {isImporting ? "Parsing AI..." : "Upload CV / Resume"}
          </button>
          
          <button 
            onClick={handleSave}
            disabled={isSaving}
            style={{ ...buttonStyle, background: draftMode ? "var(--review)" : "var(--accent)" }}
          >
            {isSaving ? "Saving..." : (draftMode ? "Verify & Save Profile" : "Save Changes")}
          </button>
        </div>
      </div>

      {draftMode && (
        <div style={{ background: "var(--warning-soft, rgba(255,193,7,0.1))", border: "1px solid var(--warning, #ffc107)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "24px", color: "var(--warning, #b38600)" }}>
          <h3 style={{ margin: "0 0 8px 0" }}>Review Required (Draft Mode)</h3>
          <p style={{ margin: 0, fontSize: "14px" }}>AI has extracted data from your resume. Review all fields carefully before saving.</p>
        </div>
      )}

      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Identity & Summary</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <label style={labelStyle}>First Name
            <input style={inputStyle} value={formData.identity?.first_name?.value || formData.identity?.first_name || ""} onChange={e => updateField("identity", "first_name", e.target.value)} />
          </label>
          <label style={labelStyle}>Last Name
            <input style={inputStyle} value={formData.identity?.last_name?.value || formData.identity?.last_name || ""} onChange={e => updateField("identity", "last_name", e.target.value)} />
          </label>
          <label style={labelStyle}>Email
            <input type="email" style={inputStyle} value={formData.identity?.email?.value || formData.identity?.email || ""} onChange={e => updateField("identity", "email", e.target.value)} />
          </label>
          <label style={labelStyle}>Phone
            <input style={inputStyle} value={formData.identity?.phone?.value || formData.identity?.phone || ""} onChange={e => updateField("identity", "phone", e.target.value)} />
          </label>
        </div>
        <label style={labelStyle}>Professional Summary
          <textarea style={textareaStyle} value={formData.identity?.professional_summary?.value || formData.identity?.professional_summary || ""} onChange={e => updateField("identity", "professional_summary", e.target.value)} />
        </label>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Location</h2>
          <label style={labelStyle}>Country
            <input style={inputStyle} value={formData.location?.country?.value || formData.location?.country || ""} onChange={e => updateField("location", "country", e.target.value)} />
          </label>
          <label style={labelStyle}>City
            <input style={inputStyle} value={formData.location?.city?.value || formData.location?.city || ""} onChange={e => updateField("location", "city", e.target.value)} />
          </label>
        </div>

        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Work Authorization</h2>
          <label style={labelStyle}>Nationality
            <input style={inputStyle} value={formData.work_authorization?.nationality?.value || formData.work_authorization?.nationality || ""} onChange={e => updateField("work_authorization", "nationality", e.target.value)} />
          </label>
          <label style={labelStyle}>Status
            <input style={inputStyle} value={formData.work_authorization?.work_authorization_status?.value || formData.work_authorization?.work_authorization_status || ""} onChange={e => updateField("work_authorization", "work_authorization_status", e.target.value)} />
          </label>
        </div>
      </div>

      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Experience</h2>
        {formData.experience?.map((exp: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Company
                <input style={inputStyle} value={exp.company?.value || exp.company || ""} onChange={e => { const n = [...formData.experience]; if(n[idx].company?.value) n[idx].company.value=e.target.value; else n[idx].company=e.target.value; setFormData({...formData, experience: n}) }} />
              </label>
              <label style={labelStyle}>Title
                <input style={inputStyle} value={exp.title?.value || exp.title || ""} onChange={e => { const n = [...formData.experience]; if(n[idx].title?.value) n[idx].title.value=e.target.value; else n[idx].title=e.target.value; setFormData({...formData, experience: n}) }} />
              </label>
            </div>
            <label style={labelStyle}>Description
              <textarea style={textareaStyle} value={exp.description?.value || exp.description || ""} onChange={e => { const n = [...formData.experience]; if(n[idx].description?.value) n[idx].description.value=e.target.value; else n[idx].description=e.target.value; setFormData({...formData, experience: n}) }} />
            </label>
          </div>
        ))}
        {(!formData.experience || formData.experience.length === 0) && <p style={{ color: "var(--text-3)" }}>No experience entries found.</p>}
      </div>

    </div>
  );
}
