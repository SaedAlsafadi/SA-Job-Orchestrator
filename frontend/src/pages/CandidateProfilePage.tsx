import React, { useState, useEffect, useRef } from "react";
import api from "@/services/api";

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 12px", background: "var(--surface-2)",
  border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
  color: "var(--text)", fontFamily: "var(--font)", fontSize: "14px",
  marginTop: "4px", marginBottom: "16px", boxSizing: "border-box"
};

const textareaStyle: React.CSSProperties = {
  ...inputStyle,
  minHeight: "90px",
  resize: "vertical"
};

const labelStyle: React.CSSProperties = {
  fontSize: "13px", color: "var(--text-2)", fontWeight: 600, display: "block"
};

const cardStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)", padding: "24px", marginBottom: "24px", boxShadow: "var(--shadow-1)"
};

const buttonStyle: React.CSSProperties = {
  background: "var(--accent)", color: "var(--accent-ink, #fff)", padding: "10px 20px",
  border: "none", borderRadius: "var(--r-md)", fontWeight: 700, cursor: "pointer", fontSize: "14px"
};

const smallBtnStyle: React.CSSProperties = {
  background: "var(--surface-2)", color: "var(--text)", padding: "6px 14px",
  border: "1px solid var(--border)", borderRadius: "var(--r-sm)", fontWeight: 600,
  cursor: "pointer", fontSize: "13px", display: "inline-flex", alignItems: "center", gap: "6px"
};

const deleteBtnStyle: React.CSSProperties = {
  background: "transparent", color: "var(--failed, #ef4444)", border: "1px solid var(--failed, #ef4444)",
  padding: "4px 10px", borderRadius: "var(--r-sm)", fontSize: "12px", fontWeight: 600, cursor: "pointer"
};

/* ---------- helpers ---------- */

/** Safely extract a display string from a field that could be a plain string, a DraftValue object, or null. */
function dv(field: any): string {
  if (field === null || field === undefined) return "";
  if (typeof field === "string") return field;
  if (typeof field === "number") return String(field);
  if (typeof field === "object" && "value" in field) return field.value ?? "";
  if (typeof field === "object" && "name" in field) return field.name ?? "";
  return String(field);
}

/** Recursively flatten DraftValue objects into clean format for backend CandidateProfileSchema. */
function preparePayloadForSave(data: any): any {
  if (!data) return {};

  const cleanVal = (v: any) => {
    if (v === null || v === undefined) return "";
    if (typeof v === "object" && "value" in v) return v.value ?? "";
    return v;
  };

  return {
    identity: {
      first_name: cleanVal(data.identity?.first_name),
      last_name: cleanVal(data.identity?.last_name),
      email: cleanVal(data.identity?.email),
      phone: cleanVal(data.identity?.phone),
      linkedin: cleanVal(data.identity?.linkedin),
      github: cleanVal(data.identity?.github),
      portfolio: cleanVal(data.identity?.portfolio),
      professional_summary: cleanVal(data.identity?.professional_summary),
    },
    location: {
      country: cleanVal(data.location?.country),
      city: cleanVal(data.location?.city),
      preferred_locations: Array.isArray(data.location?.preferred_locations) ? data.location.preferred_locations : [],
      willing_to_relocate: Boolean(data.location?.willing_to_relocate),
      remote_preference: cleanVal(data.location?.remote_preference) || "hybrid",
    },
    employment: {
      current_title: cleanVal(data.employment?.current_title),
      years_of_experience: Number(cleanVal(data.employment?.years_of_experience)) || 0,
      notice_period: cleanVal(data.employment?.notice_period),
    },
    work_authorization: {
      nationality: cleanVal(data.work_authorization?.nationality),
      residency_country: cleanVal(data.work_authorization?.residency_country),
      work_authorization_status: cleanVal(data.work_authorization?.work_authorization_status),
      iqama_transferable: Boolean(data.work_authorization?.iqama_transferable),
    },
    education: (data.education || []).map((e: any) => ({
      evidence_id: e.evidence_id || `edu-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      degree: cleanVal(e.degree),
      institution: cleanVal(e.institution),
      field_of_study: cleanVal(e.field_of_study),
      graduation_year: cleanVal(e.graduation_year),
    })),
    experience: (data.experience || []).map((e: any) => ({
      evidence_id: e.evidence_id || `exp-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      company: cleanVal(e.company),
      title: cleanVal(e.title),
      start_date: cleanVal(e.start_date),
      end_date: cleanVal(e.end_date),
      description: cleanVal(e.description),
      achievements: Array.isArray(e.achievements) ? e.achievements : [],
      technologies: Array.isArray(e.technologies) ? e.technologies : [],
    })),
    skills: (data.skills || []).map((s: any) => {
      const name = typeof s === "string" ? s : (s?.name || s?.value || "");
      return {
        evidence_id: s?.evidence_id || `skill-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
        name: name,
        proficiency: s?.proficiency || "intermediate",
        years: Number(s?.years) || 0,
        evidence: s?.evidence || "",
      };
    }).filter((s: any) => s.name.trim() !== ""),
    projects: (data.projects || []).map((p: any) => ({
      evidence_id: p.evidence_id || `proj-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      name: cleanVal(p.name),
      description: cleanVal(p.description),
      technologies: Array.isArray(p.technologies) ? p.technologies : [],
      achievements: Array.isArray(p.achievements) ? p.achievements : [],
      url: cleanVal(p.url),
    })),
    certifications: (data.certifications || []).map((c: any) => ({
      evidence_id: c.evidence_id || `cert-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      name: cleanVal(c.name),
      issuer: cleanVal(c.issuer),
      date: cleanVal(c.date),
    })),
    languages: (data.languages || []).map((l: any) => {
      return typeof l === "string" ? l : (l?.value || "");
    }).filter((l: string) => l.trim() !== ""),
    preferences: {
      target_roles: Array.isArray(data.preferences?.target_roles) ? data.preferences.target_roles : [],
      target_countries: Array.isArray(data.preferences?.target_countries) ? data.preferences.target_countries : [],
      target_cities: Array.isArray(data.preferences?.target_cities) ? data.preferences.target_cities : [],
      minimum_salary: Number(data.preferences?.minimum_salary) || 0,
      salary_currency: data.preferences?.salary_currency || "USD",
      employment_types: Array.isArray(data.preferences?.employment_types) ? data.preferences.employment_types : [],
      excluded_companies: Array.isArray(data.preferences?.excluded_companies) ? data.preferences.excluded_companies : [],
    },
  };
}

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

  // Quick addition inputs
  const [newSkill, setNewSkill] = useState("");
  const [newLanguage, setNewLanguage] = useState("");

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
        timeout: 120000,
      });
      setFormData(res.data);
      setDraftMode(true);
    } catch (err: any) {
      alert("Failed to upload CV: " + (err.response?.data?.detail || err.message));
    }
    if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    setIsImporting(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSave = async () => {
    setIsSaving(true);
    const payload = preparePayloadForSave(formData);
    try {
      if (draftMode) {
        await api.post('/candidate-profile/verify', payload);
      } else {
        await api.put('/candidate-profile', payload);
      }
      alert("Profile verified & saved successfully!");
      setDraftMode(false);
      await fetchProfile();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : (Array.isArray(detail) ? detail.map((d: any) => `${d.loc.join('.')}: ${d.msg}`).join('\n') : err.message);
      alert("Failed to save profile:\n" + msg);
    }
    setIsSaving(false);
  };

  const updateField = (category: string, field: string, value: any) => {
    setFormData((prev: any) => {
      const newData = { ...prev };
      if (!newData[category]) newData[category] = {};
      newData[category] = { ...newData[category], [field]: value };
      return newData;
    });
  };

  /* ----- Skills Management ----- */
  const addSkill = () => {
    if (!newSkill.trim()) return;
    setFormData((prev: any) => ({
      ...prev,
      skills: [...(prev.skills || []), newSkill.trim()]
    }));
    setNewSkill("");
  };

  const removeSkill = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      skills: (prev.skills || []).filter((_: any, i: number) => i !== index)
    }));
  };

  /* ----- Languages Management ----- */
  const addLanguage = () => {
    if (!newLanguage.trim()) return;
    setFormData((prev: any) => ({
      ...prev,
      languages: [...(prev.languages || []), newLanguage.trim()]
    }));
    setNewLanguage("");
  };

  const removeLanguage = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      languages: (prev.languages || []).filter((_: any, i: number) => i !== index)
    }));
  };

  /* ----- Experience Management ----- */
  const addExperience = () => {
    setFormData((prev: any) => ({
      ...prev,
      experience: [
        ...(prev.experience || []),
        { company: "", title: "", start_date: "", end_date: "", description: "" }
      ]
    }));
  };

  const updateExperience = (index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const list = [...(prev.experience || [])];
      list[index] = { ...list[index], [field]: value };
      return { ...prev, experience: list };
    });
  };

  const removeExperience = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      experience: (prev.experience || []).filter((_: any, i: number) => i !== index)
    }));
  };

  /* ----- Education Management ----- */
  const addEducation = () => {
    setFormData((prev: any) => ({
      ...prev,
      education: [
        ...(prev.education || []),
        { degree: "", institution: "", field_of_study: "", graduation_year: "" }
      ]
    }));
  };

  const updateEducation = (index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const list = [...(prev.education || [])];
      list[index] = { ...list[index], [field]: value };
      return { ...prev, education: list };
    });
  };

  const removeEducation = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      education: (prev.education || []).filter((_: any, i: number) => i !== index)
    }));
  };

  /* ----- Project Management ----- */
  const addProject = () => {
    setFormData((prev: any) => ({
      ...prev,
      projects: [
        ...(prev.projects || []),
        { name: "", description: "", url: "" }
      ]
    }));
  };

  const updateProject = (index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const list = [...(prev.projects || [])];
      list[index] = { ...list[index], [field]: value };
      return { ...prev, projects: list };
    });
  };

  const removeProject = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      projects: (prev.projects || []).filter((_: any, i: number) => i !== index)
    }));
  };

  /* ----- Certification Management ----- */
  const addCertification = () => {
    setFormData((prev: any) => ({
      ...prev,
      certifications: [
        ...(prev.certifications || []),
        { name: "", issuer: "", date: "" }
      ]
    }));
  };

  const updateCertification = (index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const list = [...(prev.certifications || [])];
      list[index] = { ...list[index], [field]: value };
      return { ...prev, certifications: list };
    });
  };

  const removeCertification = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      certifications: (prev.certifications || []).filter((_: any, i: number) => i !== index)
    }));
  };

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>Loading Profile...</div>;
  if (error) return <div style={{ padding: 40, textAlign: "center", color: "var(--failed)" }}>Error: {error}</div>;
  if (!formData) return null;

  return (
    <div style={{ padding: "32px", maxWidth: "950px", margin: "0 auto" }}>

      {/* ========== IMPORT OVERLAY ========== */}
      {isImporting && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 9999,
          background: "rgba(0,0,0,0.7)",
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          color: "#fff",
        }}>
          <div style={{
            width: 56, height: 56, border: "4px solid rgba(255,255,255,0.2)",
            borderTopColor: "var(--accent, #6366f1)", borderRadius: "50%",
            animation: "spin 1s linear infinite", marginBottom: 24,
          }} />
          <p style={{ fontSize: 20, fontWeight: 700, margin: "0 0 8px 0" }}>
            {IMPORT_STEPS[importStep]}
          </p>
          <p style={{ fontSize: 14, opacity: 0.7, margin: 0 }}>
            Extracting candidate data with LLM…
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
            {IMPORT_STEPS.map((_, i) => (
              <div key={i} style={{
                width: 10, height: 10, borderRadius: "50%",
                background: i <= importStep ? "var(--accent, #6366f1)" : "rgba(255,255,255,0.25)",
                transition: "background 0.3s",
              }} />
            ))}
          </div>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 style={{ margin: 0, fontSize: "28px" }}>Candidate Profile</h1>
            <span style={{
              fontSize: "12px", fontWeight: 700, padding: "4px 10px", borderRadius: "12px",
              background: draftMode ? "rgba(234, 179, 8, 0.15)" : "rgba(34, 197, 94, 0.15)",
              color: draftMode ? "var(--review, #eab308)" : "var(--success, #22c55e)",
              border: `1px solid ${draftMode ? "rgba(234, 179, 8, 0.3)" : "rgba(34, 197, 94, 0.3)"}`
            }}>
              {draftMode ? "Draft Mode" : "Verified Profile"}
            </span>
          </div>
          <p style={{ color: "var(--text-2)", marginTop: "6px", marginBottom: 0 }}>
            Edit, add, or remove information across all sections before verifying.
          </p>
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
            style={{ ...buttonStyle, background: draftMode ? "var(--review, #eab308)" : "var(--accent)" }}
          >
            {isSaving ? "Saving..." : (draftMode ? "Verify & Save Profile" : "Save Changes")}
          </button>
        </div>
      </div>

      {draftMode && (
        <div style={{ background: "rgba(234, 179, 8, 0.1)", border: "1px solid rgba(234, 179, 8, 0.3)", padding: "14px 18px", borderRadius: "var(--r-md)", marginBottom: "24px", color: "var(--review, #eab308)" }}>
          <strong>Draft Mode:</strong> AI extracted data from your resume. Review and edit any field below, then click <strong>Verify & Save Profile</strong>.
        </div>
      )}

      {/* ========== IDENTITY & SUMMARY ========== */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, marginBottom: "20px", color: "var(--accent)", fontSize: "18px" }}>Identity & Contact</h2>
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
          <label style={labelStyle}>LinkedIn URL
            <input style={inputStyle} value={dv(formData.identity?.linkedin)} onChange={e => updateField("identity", "linkedin", e.target.value)} />
          </label>
          <label style={labelStyle}>GitHub URL
            <input style={inputStyle} value={dv(formData.identity?.github)} onChange={e => updateField("identity", "github", e.target.value)} />
          </label>
          <label style={labelStyle}>Portfolio / Website
            <input style={inputStyle} value={dv(formData.identity?.portfolio)} onChange={e => updateField("identity", "portfolio", e.target.value)} />
          </label>
        </div>
        <label style={labelStyle}>Professional Summary
          <textarea style={textareaStyle} value={dv(formData.identity?.professional_summary)} onChange={e => updateField("identity", "professional_summary", e.target.value)} />
        </label>
      </div>

      {/* ========== LOCATION & WORK AUTH ========== */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "20px", color: "var(--accent)", fontSize: "18px" }}>Location</h2>
          <label style={labelStyle}>Country
            <input style={inputStyle} value={dv(formData.location?.country)} onChange={e => updateField("location", "country", e.target.value)} />
          </label>
          <label style={labelStyle}>City
            <input style={inputStyle} value={dv(formData.location?.city)} onChange={e => updateField("location", "city", e.target.value)} />
          </label>
          <label style={labelStyle}>Remote Preference
            <select 
              style={inputStyle} 
              value={dv(formData.location?.remote_preference) || "hybrid"} 
              onChange={e => updateField("location", "remote_preference", e.target.value)}
            >
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </label>
        </div>

        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, marginBottom: "20px", color: "var(--accent)", fontSize: "18px" }}>Work Authorization & Employment</h2>
          <label style={labelStyle}>Nationality
            <input style={inputStyle} value={dv(formData.work_authorization?.nationality)} onChange={e => updateField("work_authorization", "nationality", e.target.value)} />
          </label>
          <label style={labelStyle}>Work Authorization Status
            <input style={inputStyle} value={dv(formData.work_authorization?.work_authorization_status)} onChange={e => updateField("work_authorization", "work_authorization_status", e.target.value)} />
          </label>
          <label style={labelStyle}>Current Job Title
            <input style={inputStyle} value={dv(formData.employment?.current_title)} onChange={e => updateField("employment", "current_title", e.target.value)} />
          </label>
        </div>
      </div>

      {/* ========== SKILLS ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Skills ({formData.skills?.length || 0})</h2>
        </div>
        
        {/* Add Skill Row */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          <input 
            style={{ ...inputStyle, marginBottom: 0, flex: 1 }} 
            placeholder="Type a skill and click Add (e.g. Python, Docker, React)..." 
            value={newSkill} 
            onChange={e => setNewSkill(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addSkill(); } }}
          />
          <button type="button" onClick={addSkill} style={buttonStyle}>+ Add Skill</button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {formData.skills?.map((skill: any, idx: number) => {
            const skillName = dv(skill);
            return (
              <span key={idx} style={{
                background: "var(--surface-2)", color: "var(--text)", padding: "6px 12px",
                borderRadius: "20px", fontSize: "13px", fontWeight: 600, border: "1px solid var(--border)",
                display: "inline-flex", alignItems: "center", gap: "8px"
              }}>
                {skillName}
                <button 
                  type="button" 
                  onClick={() => removeSkill(idx)} 
                  style={{ background: "transparent", border: "none", color: "var(--text-3)", cursor: "pointer", fontSize: "14px", lineHeight: 1, padding: 0 }}
                  title="Remove skill"
                >
                  ✕
                </button>
              </span>
            );
          })}
        </div>
        {(!formData.skills || formData.skills.length === 0) && <p style={{ color: "var(--text-3)", marginTop: "8px" }}>No skills added yet.</p>}
      </div>

      {/* ========== WORK EXPERIENCE ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Work Experience ({formData.experience?.length || 0})</h2>
          <button type="button" onClick={addExperience} style={smallBtnStyle}>+ Add Experience</button>
        </div>
        {formData.experience?.map((exp: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <span style={{ fontWeight: 700, fontSize: "14px" }}>Position #{idx + 1}</span>
              <button type="button" onClick={() => removeExperience(idx)} style={deleteBtnStyle}>Delete</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Company
                <input style={inputStyle} value={dv(exp.company)} onChange={e => updateExperience(idx, "company", e.target.value)} />
              </label>
              <label style={labelStyle}>Job Title
                <input style={inputStyle} value={dv(exp.title)} onChange={e => updateExperience(idx, "title", e.target.value)} />
              </label>
              <label style={labelStyle}>Start Date
                <input style={inputStyle} placeholder="e.g. 2021 or Jan 2021" value={dv(exp.start_date)} onChange={e => updateExperience(idx, "start_date", e.target.value)} />
              </label>
              <label style={labelStyle}>End Date
                <input style={inputStyle} placeholder="e.g. Present or Dec 2023" value={dv(exp.end_date)} onChange={e => updateExperience(idx, "end_date", e.target.value)} />
              </label>
            </div>
            <label style={labelStyle}>Responsibilities & Achievements
              <textarea style={textareaStyle} value={dv(exp.description)} onChange={e => updateExperience(idx, "description", e.target.value)} />
            </label>
          </div>
        ))}
        {(!formData.experience || formData.experience.length === 0) && <p style={{ color: "var(--text-3)" }}>No experience entries added.</p>}
      </div>

      {/* ========== EDUCATION ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Education ({formData.education?.length || 0})</h2>
          <button type="button" onClick={addEducation} style={smallBtnStyle}>+ Add Education</button>
        </div>
        {formData.education?.map((edu: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <span style={{ fontWeight: 700, fontSize: "14px" }}>Education #{idx + 1}</span>
              <button type="button" onClick={() => removeEducation(idx)} style={deleteBtnStyle}>Delete</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Degree
                <input style={inputStyle} placeholder="e.g. Bachelor of Science" value={dv(edu.degree)} onChange={e => updateEducation(idx, "degree", e.target.value)} />
              </label>
              <label style={labelStyle}>Institution
                <input style={inputStyle} placeholder="e.g. King Saud University" value={dv(edu.institution)} onChange={e => updateEducation(idx, "institution", e.target.value)} />
              </label>
              <label style={labelStyle}>Field of Study
                <input style={inputStyle} placeholder="e.g. Computer Science" value={dv(edu.field_of_study)} onChange={e => updateEducation(idx, "field_of_study", e.target.value)} />
              </label>
              <label style={labelStyle}>Graduation Year
                <input style={inputStyle} placeholder="e.g. 2022" value={dv(edu.graduation_year)} onChange={e => updateEducation(idx, "graduation_year", e.target.value)} />
              </label>
            </div>
          </div>
        ))}
        {(!formData.education || formData.education.length === 0) && <p style={{ color: "var(--text-3)" }}>No education entries added.</p>}
      </div>

      {/* ========== PROJECTS ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Projects ({formData.projects?.length || 0})</h2>
          <button type="button" onClick={addProject} style={smallBtnStyle}>+ Add Project</button>
        </div>
        {formData.projects?.map((proj: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <span style={{ fontWeight: 700, fontSize: "14px" }}>Project #{idx + 1}</span>
              <button type="button" onClick={() => removeProject(idx)} style={deleteBtnStyle}>Delete</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Project Name
                <input style={inputStyle} value={dv(proj.name)} onChange={e => updateProject(idx, "name", e.target.value)} />
              </label>
              <label style={labelStyle}>Project URL
                <input style={inputStyle} value={dv(proj.url)} onChange={e => updateProject(idx, "url", e.target.value)} />
              </label>
            </div>
            <label style={labelStyle}>Description
              <textarea style={textareaStyle} value={dv(proj.description)} onChange={e => updateProject(idx, "description", e.target.value)} />
            </label>
          </div>
        ))}
        {(!formData.projects || formData.projects.length === 0) && <p style={{ color: "var(--text-3)" }}>No projects added.</p>}
      </div>

      {/* ========== CERTIFICATIONS ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Certifications ({formData.certifications?.length || 0})</h2>
          <button type="button" onClick={addCertification} style={smallBtnStyle}>+ Add Certification</button>
        </div>
        {formData.certifications?.map((cert: any, idx: number) => (
          <div key={idx} style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "var(--r-md)", marginBottom: "16px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <span style={{ fontWeight: 700, fontSize: "14px" }}>Certification #{idx + 1}</span>
              <button type="button" onClick={() => removeCertification(idx)} style={deleteBtnStyle}>Delete</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
              <label style={labelStyle}>Certification Name
                <input style={inputStyle} value={dv(cert.name)} onChange={e => updateCertification(idx, "name", e.target.value)} />
              </label>
              <label style={labelStyle}>Issuer / Organization
                <input style={inputStyle} value={dv(cert.issuer)} onChange={e => updateCertification(idx, "issuer", e.target.value)} />
              </label>
              <label style={labelStyle}>Date
                <input style={inputStyle} value={dv(cert.date)} onChange={e => updateCertification(idx, "date", e.target.value)} />
              </label>
            </div>
          </div>
        ))}
        {(!formData.certifications || formData.certifications.length === 0) && <p style={{ color: "var(--text-3)" }}>No certifications added.</p>}
      </div>

      {/* ========== LANGUAGES ========== */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, color: "var(--accent)", fontSize: "18px" }}>Languages ({formData.languages?.length || 0})</h2>
        </div>
        
        {/* Add Language Row */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          <input 
            style={{ ...inputStyle, marginBottom: 0, flex: 1 }} 
            placeholder="Type a language and click Add (e.g. Arabic, English)..." 
            value={newLanguage} 
            onChange={e => setNewLanguage(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addLanguage(); } }}
          />
          <button type="button" onClick={addLanguage} style={buttonStyle}>+ Add Language</button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {formData.languages?.map((lang: any, idx: number) => {
            const langName = dv(lang);
            return (
              <span key={idx} style={{
                background: "var(--surface-2)", color: "var(--text)", padding: "6px 14px",
                borderRadius: "20px", fontSize: "13px", fontWeight: 600, border: "1px solid var(--border)",
                display: "inline-flex", alignItems: "center", gap: "8px"
              }}>
                {langName}
                <button 
                  type="button" 
                  onClick={() => removeLanguage(idx)} 
                  style={{ background: "transparent", border: "none", color: "var(--text-3)", cursor: "pointer", fontSize: "14px", lineHeight: 1, padding: 0 }}
                  title="Remove language"
                >
                  ✕
                </button>
              </span>
            );
          })}
        </div>
        {(!formData.languages || formData.languages.length === 0) && <p style={{ color: "var(--text-3)", marginTop: "8px" }}>No languages added yet.</p>}
      </div>

    </div>
  );
}
