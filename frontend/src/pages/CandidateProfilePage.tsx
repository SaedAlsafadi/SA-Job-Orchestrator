import React, { useEffect, useState, useRef } from "react";
import { useProfileStore } from "@/store/useProfileStore";
import api from "@/services/api";


export function CandidateProfilePage() {
  const { profile, fetchProfile } = useProfileStore();
  const [formData, setFormData] = useState<any>(null);
  const [draftMode, setDraftMode] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (profile && !draftMode) {
      setFormData(profile);
    } else if (!profile && !draftMode) {
      setFormData({
        identity: { first_name: "", last_name: "", email: "", phone: "", linkedin: "", github: "", portfolio: "", professional_summary: "" },
        location: { country: "", city: "", preferred_locations: [], willing_to_relocate: false, remote_preference: "hybrid" },
        employment: { current_title: "", years_of_experience: 0, notice_period: "" },
        work_authorization: { nationality: "", residency_country: "", work_authorization_status: "", iqama_transferable: false },
        education: [], experience: [], skills: [], projects: [], certifications: [], languages: [],
        preferences: { target_roles: [], target_countries: [], target_cities: [], minimum_salary: 0, salary_currency: "USD", employment_types: [], excluded_companies: [] }
      });
    }
  }, [profile, draftMode]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post("/candidate-profile/import-resume", fd);
      
      const flatten = (obj: any): any => {
        if (obj === null || obj === undefined) return obj;
        if (Array.isArray(obj)) return obj.map(flatten);
        if (typeof obj === 'object') {
          if ('confidence' in obj && 'source' in obj && 'value' in obj) {
            if (typeof obj.value === 'object' && obj.value !== null) {
              const flatValue = flatten(obj.value);
              flatValue._confidence = obj.confidence;
              return flatValue;
            } else {
              return { value: obj.value || "", _confidence: obj.confidence };
            }
          }
          const flatObj: any = {};
          for (const key in obj) {
            flatObj[key] = flatten(obj[key]);
          }
          return flatObj;
        }
        return obj;
      };
      
      setFormData(flatten(res.data));
      setDraftMode(true);
    } catch (error) {
      console.error(error);
      alert("Failed to import resume.");
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const cleanForSubmit = (obj: any): any => {
    if (obj === null || obj === undefined) return obj;
    if (Array.isArray(obj)) return obj.map(cleanForSubmit);
    if (typeof obj === 'object') {
      if ('value' in obj && '_confidence' in obj) {
        return obj.value;
      }
      const cleanObj: any = {};
      for (const key in obj) {
        if (key === '_confidence') continue;
        cleanObj[key] = cleanForSubmit(obj[key]);
      }
      return cleanObj;
    }
    return obj;
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload = cleanForSubmit(formData);
      await api.post("/candidate-profile/verify", payload);
      setDraftMode(false);
      fetchProfile();
    } catch (e) {
      console.error(e);
      alert("Failed to save profile.");
    } finally {
      setIsSaving(false);
    }
  };

  if (!formData) return <div className="p-8 text-gray-500">Loading...</div>;

  const renderField = (label: string, category: string, field: string, type: string = "text") => {
    const data = formData[category]?.[field];
    const val = (data && typeof data === 'object' && 'value' in data) ? data.value : (data || "");
    const conf = (data && typeof data === 'object' && '_confidence' in data) ? data._confidence : null;
    
    return (
      <div className="flex flex-col gap-1 mb-4">
        <label className="text-sm font-semibold text-gray-400 flex items-center justify-between">
          {label}
          {draftMode && conf !== null && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${conf > 0.8 ? 'bg-green-900/50 text-green-400' : 'bg-yellow-900/50 text-yellow-400'}`}>
              {conf > 0.8 ? "✅" : "⚠️"}
              {Math.round(conf * 100)}% Conf
            </span>
          )}
        </label>
        {type === "textarea" ? (
          <textarea 
            className="p-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-200"
            rows={4}
            value={val} 
            onChange={(e) => {
              const newData = { ...formData };
              if (data && typeof data === 'object' && 'value' in data) {
                newData[category][field].value = e.target.value;
              } else {
                newData[category][field] = e.target.value;
              }
              setFormData(newData);
            }} 
          />
        ) : (
          <input 
            type={type}
            className="p-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-200"
            value={val} 
            onChange={(e) => {
              const newData = { ...formData };
              if (data && typeof data === 'object' && 'value' in data) {
                newData[category][field].value = e.target.value;
              } else {
                newData[category][field] = e.target.value;
              }
              setFormData(newData);
            }} 
          />
        )}
      </div>
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto font-sans">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-100">Candidate Profile</h1>
          <p className="text-gray-400 mt-2">Manage your master profile or import from your resume.</p>
        </div>
        <div className="flex gap-4">
          <input 
            type="file" 
            accept=".pdf,.docx" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isImporting}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-200 px-4 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
          >
            ⬆️
            {isImporting ? "Parsing AI..." : "Import Resume"}
          </button>
          
          <button 
            onClick={handleSave}
            disabled={isSaving}
            className={`flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-bold transition-colors disabled:opacity-50 ${draftMode ? "bg-blue-600 hover:bg-blue-500 text-white" : "bg-emerald-600 hover:bg-emerald-500 text-white"}`}
          >
            {draftMode ? "Verify & Save Profile" : "Save Changes"}
          </button>
        </div>
      </div>

      {draftMode && (
        <div className="mb-6 p-4 bg-blue-900/30 border border-blue-500/30 rounded-lg text-blue-200 text-sm flex items-start gap-3">
          ⚠️
          <div>
            <strong>Review Required (DRAFT MODE)</strong>
            <p className="mt-1 opacity-90">AI has extracted data from your resume. Review all fields carefully before saving. Values with low confidence are highlighted.</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
            👤 Identity
          </h2>
          <div className="grid grid-cols-2 gap-x-4">
            {renderField("First Name", "identity", "first_name")}
            {renderField("Last Name", "identity", "last_name")}
            {renderField("Email", "identity", "email", "email")}
            {renderField("Phone", "identity", "phone")}
            {renderField("LinkedIn", "identity", "linkedin")}
            {renderField("GitHub", "identity", "github")}
          </div>
          {renderField("Professional Summary", "identity", "professional_summary", "textarea")}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col gap-6">
          <div>
            <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
              📍 Location
            </h2>
            <div className="grid grid-cols-2 gap-x-4">
              {renderField("Country", "location", "country")}
              {renderField("City", "location", "city")}
            </div>
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
              💼 Work Authorization
            </h2>
            <div className="grid grid-cols-2 gap-x-4">
              {renderField("Nationality", "work_authorization", "nationality")}
              {renderField("Residency Country", "work_authorization", "residency_country")}
              {renderField("Status", "work_authorization", "work_authorization_status")}
            </div>
          </div>
        </div>
      </div>
      
      {/* Experience */}
      <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
          💼 Experience
        </h2>
        {formData.experience?.map((exp: any, idx: number) => {
          const comp = exp.company?.value || exp.company || "";
          const tit = exp.title?.value || exp.title || "";
          const sd = exp.start_date?.value || exp.start_date || "";
          const ed = exp.end_date?.value || exp.end_date || "";
          return (
            <div key={idx} className="p-4 bg-gray-800/50 rounded-lg mb-4 border border-gray-800">
              <div className="font-semibold text-gray-300">{tit} at {comp}</div>
              <div className="text-xs text-gray-500 mb-2">{sd} - {ed}</div>
              <div className="text-sm text-gray-400">{exp.description?.value || exp.description || ""}</div>
            </div>
          );
        })}
        {(!formData.experience || formData.experience.length === 0) && (
          <div className="text-sm text-gray-500 italic">No experience entries.</div>
        )}
      </div>

      {/* Education */}
      <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
          🎓 Education
        </h2>
        {formData.education?.map((edu: any, idx: number) => {
          const deg = edu.degree?.value || edu.degree || "";
          const inst = edu.institution?.value || edu.institution || "";
          const field = edu.field_of_study?.value || edu.field_of_study || "";
          const year = edu.graduation_year?.value || edu.graduation_year || "";
          return (
            <div key={idx} className="p-4 bg-gray-800/50 rounded-lg mb-4 border border-gray-800">
              <div className="font-semibold text-gray-300">{deg} in {field}</div>
              <div className="text-sm text-gray-400">{inst} ({year})</div>
            </div>
          );
        })}
        {(!formData.education || formData.education.length === 0) && (
          <div className="text-sm text-gray-500 italic">No education entries.</div>
        )}
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
            💻 Skills
          </h2>
          <div className="flex flex-wrap gap-2">
            {formData.skills?.map((s: any, i: number) => (
              <span key={i} className="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs border border-gray-700">
                {s.name?.value || s.name || s.value || s}
              </span>
            ))}
          </div>
        </div>
        
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
            🏆 Languages
          </h2>
          <div className="flex flex-wrap gap-2">
            {formData.languages?.map((s: any, i: number) => (
              <span key={i} className="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs border border-gray-700">
                {s.value || s}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}



