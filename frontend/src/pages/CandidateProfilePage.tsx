import { useEffect, useState } from "react";
import { useProfileStore } from "@/store/useProfileStore";

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px",
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-sm)",
  color: "var(--text)",
  fontFamily: "var(--font)",
  fontSize: "14px",
  marginTop: "4px"
};

const labelStyle: React.CSSProperties = {
  fontSize: "13px",
  color: "var(--text-2)",
  fontWeight: 600,
  display: "block",
  marginBottom: "12px"
};

const cardStyle: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  padding: "24px",
  marginBottom: "24px",
  boxShadow: "var(--shadow-1)"
};

const titleStyle: React.CSSProperties = {
  fontSize: "24px",
  fontWeight: 700,
  color: "var(--text)",
  margin: "0 0 8px 0"
};

const subtitleStyle: React.CSSProperties = {
  fontSize: "15px",
  color: "var(--text-2)",
  margin: "0 0 32px 0"
};

export function CandidateProfilePage() {
  const { profile, fetchProfile, updateProfile, isLoading } = useProfileStore();
  const [formData, setFormData] = useState<any>({
    identity: { first_name: "", last_name: "", email: "", phone: "" },
    location: { country: "", city: "", preferred_locations: [], willing_to_relocate: false, remote_preference: "hybrid" },
    employment: { current_title: "", years_of_experience: 0, notice_period: "" },
    work_authorization: { nationality: "", residency_country: "", work_authorization_status: "", iqama_transferable: false },
    education: [],
    experience: [],
    skills: [],
    projects: [],
    certifications: [],
    preferences: { target_roles: [], target_countries: [], target_cities: [], minimum_salary: 0, salary_currency: "USD", employment_types: [], excluded_companies: [] }
  });

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (profile) setFormData(profile);
  }, [profile]);

  const handleSave = () => {
    updateProfile(formData);
  };

  const updateIdentity = (field: string, val: string) => {
    setFormData((prev: any) => ({ ...prev, identity: { ...prev.identity, [field]: val } }));
  };

  if (isLoading && !profile) {
    return <div style={{ padding: 40, color: "var(--text-2)", fontFamily: "var(--font)" }}>Loading profile...</div>;
  }

  return (
    <div style={{ padding: "40px", maxWidth: "800px", margin: "0 auto", fontFamily: "var(--font)" }}>
      <h1 style={titleStyle}>Candidate Profile</h1>
      <p style={subtitleStyle}>Manage your central professional profile to eliminate AI hallucinations.</p>
      
      {/* Identity */}
      <div style={cardStyle}>
        <h2 style={{ margin: "0 0 20px 0", fontSize: "18px", color: "var(--text)" }}>Identity</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <label style={labelStyle}>
            First Name
            <input style={inputStyle} type="text" value={formData.identity.first_name} onChange={(e) => updateIdentity("first_name", e.target.value)} />
          </label>
          <label style={labelStyle}>
            Last Name
            <input style={inputStyle} type="text" value={formData.identity.last_name} onChange={(e) => updateIdentity("last_name", e.target.value)} />
          </label>
          <label style={labelStyle}>
            Email
            <input style={inputStyle} type="email" value={formData.identity.email} onChange={(e) => updateIdentity("email", e.target.value)} />
          </label>
          <label style={labelStyle}>
            Phone
            <input style={inputStyle} type="text" value={formData.identity.phone} onChange={(e) => updateIdentity("phone", e.target.value)} />
          </label>
        </div>
      </div>

      <button 
        onClick={handleSave} 
        style={{
          background: "var(--accent)", 
          color: "var(--accent-ink)", 
          padding: "12px 24px", 
          border: "none", 
          borderRadius: "var(--r-md)",
          fontWeight: 700,
          cursor: "pointer",
          fontSize: "14px"
        }}
      >
        {isLoading ? "Saving..." : "Save Profile"}
      </button>
    </div>
  );
}
