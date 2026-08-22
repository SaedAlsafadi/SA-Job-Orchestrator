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

/* ---------- helpers ---------- */

/** Safely extract a display string from a field that could be a plain string, a DraftValue object, or null. */
function dv(field: any): string {
  if (field === null || field === undefined) return "";
  if (typeof field === "string") return field;
  if (typeof field === "object" && "value" in field) return field.value ?? "";
  return String(field);
}

/* ---------- loading overlay styles ---------- */
const overlayStyle: React.CSSProperties = {
  position: "fixed", inset: 0, zIndex: 9999,
  background: "rgba(0,0,0,0.65)",
  display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center",
  color: "#fff",
};

const IMPORT_STEPS = [
  "Uploading document…",
  "Parsing resume text…",
  "AI is extracting your profile data…",
  "Mapping skills, experience & education…",
  "Almost done — finalizing draft…",
];

export function CandidateProfilePage() {
  const [formData, setFormData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importStep, setImportStep] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [draftMode, setDraftMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchProfile();
    return () => { if (stepTimerRef.current) clearInterval(stepTimerRef.current); };
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
    }
    setLoading(false);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Start loading overlay with animated steps
    setIsImporting(true);
    setImportStep(0);
    let step = 0;
    stepTimerRef.current = setInterval(() => {
      step = Math.min(step + 1, IMPORT_STEPS.length - 1);
      setImportStep(step);
    }, 3000);

    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api.post('/candidate-profile/import-resume', fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000, // 2 min — LLM extraction can be slow on free models
      });
      setFormData(res.data);
      setDraftMode(true);
    } catch (err: any) {
      alert("Failed to upload CV: " + (err.response?.data?.detail || err.message));
    }
    if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    setIsImporting(false);

    // Reset file input so same file can be re-uploaded
    if (fileInputRef.current) fileInputRef.current.value = "";
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
      if (!newData[category]) newData[category] = {};
      const current = newData[category][field];
      if (current && typeof current === 'object' && 'value' in current) {
        newData[category] = { ...newData[category], [field]: { ...current, value } };
      } else {
        newData[category] = { ...newData[category], [field]: value };
      }
      return newData;
    });
  };

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>Loading Profile...</div>;
  if (error) return <div style={{ padding: 40, textAlign: "center", color: "var(--failed)" }}>Error: {error}</div>;
  if (!formData) return null;

  return (
    <div style={{ padding: "32px", maxWidth: "900px", margin: "0 auto" }}>

      {/* ========== IMPORT OVERLAY ========== */}
      {isImporting && (
        <div style={overlayStyle}>
          {/* Spinner */}
          <div style={{
            width: 56, height: 56, border: "4px solid rgba(255,255,255,0.2)",
            borderTopColor: "var(--accent, #6366f1)", borderRadius: "50%",
            animation: "spin 1s linear infinite", marginBottom: 24,
          }} />
          <p style={{ fontSize: 20, fontWeight: 700, margin: "0 0 8px 0" }}>
            {IMPORT_STEPS[importStep]}
          </p>
          <p style={{ fontSize: 14, opacity: 0.7, margin: 0 }}>
            This may take 10–30 seconds depending on the model
          </p>
          {/* Progress dots */}
          <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
            {IMPORT_STEPS.map((_, i) => (
              <div key={i} style={{
                width: 10, height: 10, borderRadius: "50%",
                background: i <= importStep ? "var(--accent, #6366f1)" : "rgba(255,255,255,0.25)",
                transition: "background 0.3s",
              }} />
            ))}
          </div>
          {/* Inject keyframes */}
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

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
            Upload CV / Resume
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

      {/* ========== IDENTITY & SUMMARY ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Identity & Summary</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <label style={labelStyle}>First Name
            <input style={inputStyle} value={dv(formData.identity?.first_name)} onChange={e => updateField("identity", "first_name", e.target.value)} />
          </label>
          <label style={labelStyle}>Last Name
            <input style={inputStyle} value={dv(formData.identity?.last_name)} onChange={e => updateField("identity", "last_name", e.target.value)} />
          </label>
          <label style={labelStyle}>Email
            <input type="email" style={inputStyle} value={dv(formData.identity?.email)} onChange={e => updateField("identity", "email", e.target.value)} />
          </label>
          <label style={labelStyle}>Phone
            <input style={inputStyle} value={dv(formData.identity?.phone)} onChange={e => updateField("identity", "phone", e.target.value)} />
          </label>
          <label style={labelStyle}>LinkedIn
            <input style={inputStyle} value={dv(formData.identity?.linkedin)} onChange={e => updateField("identity", "linkedin", e.target.value)} />
          </label>
          <label style={labelStyle}>GitHub
            <input style={inputStyle} value={dv(formData.identity?.github)} onChange={e => updateField("identity", "github", e.target.value)} />
          </label>
        </div>
        <label style={labelStyle}>Professional Summary
          <textarea style={textareaStyle} value={dv(formData.identity?.professional_summary)} onChange={e => updateField("identity", "professional_summary", e.target.value)} />
        </label>
      </div>

      {/* ========== LOCATION & WORK AUTH ========== */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Location</h2>
          <label style={labelStyle}>Country
            <input style={inputStyle} value={dv(formData.location?.country)} onChange={e => updateField("location", "country", e.target.value)} />
          </label>
          <label style={labelStyle}>City
            <input style={inputStyle} value={dv(formData.location?.city)} onChange={e => updateField("location", "city", e.target.value)} />
          </label>
        </div>

        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Work Authorization</h2>
          <label style={labelStyle}>Nationality
            <input style={inputStyle} value={dv(formData.work_authorization?.nationality)} onChange={e => updateField("work_authorization", "nationality", e.target.value)} />
          </label>
          <label style={labelStyle}>Status
            <input style={inputStyle} value={dv(formData.work_authorization?.work_authorization_status)} onChange={e => updateField("work_authorization", "work_authorization_status", e.target.value)} />
          </label>
        </div>
      </div>

      {/* ========== EXPERIENCE ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Experience</h2>
        {formData.experience?.map((exp: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Company
                <input style={inputStyle} value={dv(exp.company)} onChange={e => { const n = [...formData.experience]; n[idx] = { ...n[idx], company: e.target.value }; setFormData({...formData, experience: n}) }} />
              </label>
              <label style={labelStyle}>Title
                <input style={inputStyle} value={dv(exp.title)} onChange={e => { const n = [...formData.experience]; n[idx] = { ...n[idx], title: e.target.value }; setFormData({...formData, experience: n}) }} />
              </label>
              <label style={labelStyle}>Start Date
                <input style={inputStyle} value={dv(exp.start_date)} onChange={e => { const n = [...formData.experience]; n[idx] = { ...n[idx], start_date: e.target.value }; setFormData({...formData, experience: n}) }} />
              </label>
              <label style={labelStyle}>End Date
                <input style={inputStyle} value={dv(exp.end_date)} onChange={e => { const n = [...formData.experience]; n[idx] = { ...n[idx], end_date: e.target.value }; setFormData({...formData, experience: n}) }} />
              </label>
            </div>
            <label style={labelStyle}>Description
              <textarea style={textareaStyle} value={dv(exp.description)} onChange={e => { const n = [...formData.experience]; n[idx] = { ...n[idx], description: e.target.value }; setFormData({...formData, experience: n}) }} />
            </label>
          </div>
        ))}
        {(!formData.experience || formData.experience.length === 0) && <p style={{ color: "var(--text-3)" }}>No experience entries found.</p>}
      </div>

      {/* ========== EDUCATION ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Education</h2>
        {formData.education?.map((edu: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Degree
                <input style={inputStyle} value={dv(edu.degree)} onChange={e => { const n = [...formData.education]; n[idx] = { ...n[idx], degree: e.target.value }; setFormData({...formData, education: n}) }} />
              </label>
              <label style={labelStyle}>Institution
                <input style={inputStyle} value={dv(edu.institution)} onChange={e => { const n = [...formData.education]; n[idx] = { ...n[idx], institution: e.target.value }; setFormData({...formData, education: n}) }} />
              </label>
              <label style={labelStyle}>Field of Study
                <input style={inputStyle} value={dv(edu.field_of_study)} onChange={e => { const n = [...formData.education]; n[idx] = { ...n[idx], field_of_study: e.target.value }; setFormData({...formData, education: n}) }} />
              </label>
              <label style={labelStyle}>Graduation Year
                <input style={inputStyle} value={dv(edu.graduation_year)} onChange={e => { const n = [...formData.education]; n[idx] = { ...n[idx], graduation_year: e.target.value }; setFormData({...formData, education: n}) }} />
              </label>
            </div>
          </div>
        ))}
        {(!formData.education || formData.education.length === 0) && <p style={{ color: "var(--text-3)" }}>No education entries found.</p>}
      </div>

      {/* ========== SKILLS ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Skills</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {formData.skills?.map((skill: any, idx: number) => (
            <span key={idx} style={{
              background: "var(--accent)", color: "var(--accent-ink, #fff)", padding: "6px 14px",
              borderRadius: "20px", fontSize: "13px", fontWeight: 600,
            }}>
              {dv(skill)}
            </span>
          ))}
        </div>
        {(!formData.skills || formData.skills.length === 0) && <p style={{ color: "var(--text-3)" }}>No skills found.</p>}
      </div>

      {/* ========== CERTIFICATIONS ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Certifications</h2>
        {formData.certifications?.map((cert: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Name
                <input style={inputStyle} value={dv(cert.name)} onChange={e => { const n = [...formData.certifications]; n[idx] = { ...n[idx], name: e.target.value }; setFormData({...formData, certifications: n}) }} />
              </label>
              <label style={labelStyle}>Issuer
                <input style={inputStyle} value={dv(cert.issuer)} onChange={e => { const n = [...formData.certifications]; n[idx] = { ...n[idx], issuer: e.target.value }; setFormData({...formData, certifications: n}) }} />
              </label>
              <label style={labelStyle}>Date
                <input style={inputStyle} value={dv(cert.date)} onChange={e => { const n = [...formData.certifications]; n[idx] = { ...n[idx], date: e.target.value }; setFormData({...formData, certifications: n}) }} />
              </label>
            </div>
          </div>
        ))}
        {(!formData.certifications || formData.certifications.length === 0) && <p style={{ color: "var(--text-3)" }}>No certifications found.</p>}
      </div>

      {/* ========== LANGUAGES ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "24px", color: "var(--accent)" }}>Languages</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {formData.languages?.map((lang: any, idx: number) => (
            <span key={idx} style={{
              background: "var(--surface-2)", color: "var(--text)", padding: "6px 14px",
              borderRadius: "20px", fontSize: "13px", fontWeight: 600,
              border: "1px solid var(--border)",
            }}>
              {dv(lang)}
            </span>
          ))}
        </div>
        {(!formData.languages || formData.languages.length === 0) && <p style={{ color: "var(--text-3)" }}>No languages found.</p>}
      </div>

    </div>
  );
}
