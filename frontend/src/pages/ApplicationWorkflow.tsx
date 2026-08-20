import { useState, useEffect } from "react";
import api from "@/services/api";

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px", background: "var(--surface-2)",
  border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
  color: "var(--text)", fontFamily: "var(--font)", fontSize: "14px",
  marginTop: "4px", marginBottom: "16px"
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

export function ApplicationWorkflow() {
  const [step, setStep] = useState(1);
  const [jobUrl, setJobUrl] = useState("");
  const [discoveredJobs, setDiscoveredJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [appId, setAppId] = useState<string | null>(null);
  const [appState, setAppState] = useState<any>(null);

  const discoverJobs = async () => {
    if (!jobUrl) return setError("Please enter a job URL");
    setLoading(true); setError(null);
    try {
      const res = await api.post("/workflow/discover", { url: jobUrl });
      setDiscoveredJobs(res.data.jobs);
      setStep(2);
    } catch (e: any) { setError(e.response?.data?.detail || e.message); }
    setLoading(false);
  };

  const prepareApplication = async (jobId: string) => {
    setSelectedJob(jobId);
    setLoading(true); setError(null);
    try {
      // Mocking tailored data payload as we skip LLM generation for MVP UI demo
      const payload = {
        summary: "Expert Engineer", experiences: [], skills: ["Python"]
      };
      const res = await api.post(`/workflow/jobs/${jobId}/prepare-application`, payload);
      setAppId(res.data.application_id);
      setStep(3); // PREPARING
      
      // Simulate polling for WAITING_FOR_REVIEW state
      setTimeout(() => {
        setAppState({
          status: "waiting_for_review",
          match_score: 85,
          job: discoveredJobs.find(j => j.id === jobId),
          screenshot: "/smoke_test.png",
          cv_present: true,
          prefilled_fields: [
            { label: "First Name", value: "Jane" },
            { label: "Email", value: "jane@example.com" }
          ],
          filled_fields: [
            { label: "Phone", value: "+1234567890", confidence: 1.0 }
          ],
          unanswered_questions: [
            { label: "Why do you want this job?", category: "E_UNKNOWN_HIGH_RISK" }
          ],
          warnings: ["Manual review required for UNKNOWN questions", "Platform CV detected. We recommend reviewing if it needs replacement."]
        });
        setStep(4);
      }, 3000);

    } catch (e: any) { setError(e.response?.data?.detail || e.message); }
    setLoading(false);
  };

  return (
    <div style={{ padding: "40px", maxWidth: "800px", margin: "0 auto", fontFamily: "var(--font)" }}>
      <h1 style={{ fontSize: "24px", fontWeight: 700, margin: "0 0 8px 0" }}>Prepare Application</h1>
      <p style={{ color: "var(--text-2)", marginBottom: "32px" }}>Provide a Workable URL to prepare an application.</p>

      {error && <div style={{ padding: 12, background: "var(--failed-soft)", color: "var(--failed)", borderRadius: "var(--r-sm)", marginBottom: 20 }}>{error}</div>}

      <div style={cardStyle}>
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          {["1. DISCOVER", "2. SELECT", "3. PREPARING", "4. WAITING FOR REVIEW"].map((label, idx) => (
            <div key={idx} style={{ 
              padding: "4px 12px", borderRadius: "20px", 
              background: step >= idx + 1 ? "var(--accent-soft)" : "var(--surface-2)",
              color: step >= idx + 1 ? "var(--accent)" : "var(--text-3)",
              fontWeight: 600, fontSize: "12px"
            }}>
              {label}
            </div>
          ))}
        </div>

        {step === 1 && (
          <div>
            <label style={labelStyle}>Workable Job URL
              <input style={inputStyle} value={jobUrl} onChange={e => setJobUrl(e.target.value)} placeholder="https://apply.workable.com/company/j/12345" />
            </label>
            <button style={buttonStyle} onClick={discoverJobs} disabled={loading}>{loading ? "Discovering..." : "Discover Jobs"}</button>
          </div>
        )}

        {step === 2 && (
          <div>
            <h3 style={{ margin: "0 0 16px 0" }}>Discovered Jobs</h3>
            {discoveredJobs.map(job => (
              <div key={job.id} style={{ background: "var(--surface-2)", padding: 16, borderRadius: "var(--r-sm)", marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{job.title}</div>
                  <div style={{ color: "var(--text-2)", fontSize: "13px" }}>{job.company}</div>
                </div>
                <button style={{...buttonStyle, padding: "8px 16px"}} onClick={() => prepareApplication(job.id)} disabled={loading}>
                  Prepare Application
                </button>
              </div>
            ))}
          </div>
        )}

        {step === 3 && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <h3 style={{ margin: "0 0 16px 0", color: "var(--accent)" }}>Automating Browser...</h3>
            <p style={{ color: "var(--text-2)" }}>Filling safe fields and uploading resume. Please wait.</p>
          </div>
        )}

        {step === 4 && appState && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
              <h3 style={{ margin: 0, color: "var(--review)" }}>Review Required</h3>
              <div style={{ background: "var(--surface-2)", padding: "4px 12px", borderRadius: "var(--r-sm)", fontWeight: 600, color: "var(--accent)" }}>
                Match: {appState.match_score}%
              </div>
            </div>
            
            {appState.warnings && appState.warnings.length > 0 && (
              <div style={{ background: "var(--warning-soft, #fff3cd)", color: "var(--warning, #856404)", padding: 12, borderRadius: "var(--r-sm)", marginBottom: 24, fontSize: "13px" }}>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {appState.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <div>
                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>Platform already had</h4>
                <div style={{ background: "var(--surface-2)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 16 }}>
                  {appState.prefilled_fields.map((f: any, i: number) => (
                    <div key={i} style={{ marginBottom: 4 }}><strong>{f.label}:</strong> {f.value}</div>
                  ))}
                </div>

                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>We added</h4>
                <div style={{ background: "var(--surface-2)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 16 }}>
                  {appState.filled_fields.map((f: any, i: number) => (
                    <div key={i} style={{ marginBottom: 4 }}><strong>{f.label}:</strong> {f.value} <span style={{ color: "var(--accent)", fontSize: "11px" }}>(Conf: {f.confidence})</span></div>
                  ))}
                </div>
                
                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>Human attention required</h4>
                {appState.unanswered_questions.map((q: any, i: number) => (
                  <div key={i} style={{ background: "var(--failed-soft)", color: "var(--failed)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 8 }}>
                    <strong>{q.label}</strong> (Category: {q.category})
                  </div>
                ))}
              </div>
              
              <div>
                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>Browser Screenshot</h4>
                <div style={{ height: "300px", background: "var(--surface-2)", borderRadius: "var(--r-sm)", border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-3)", fontSize: "12px" }}>
                  [Screenshot Rendered Here]
                </div>
              </div>
            </div>

            <div style={{ marginTop: 24, paddingTop: 24, borderTop: "1px solid var(--border)", display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button style={{...buttonStyle, background: "var(--surface-2)", color: "var(--text)"}}>Cancel</button>
              <button style={{...buttonStyle, opacity: 0.5, cursor: "not-allowed"}} disabled>Submit Application (Disabled for MVP)</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
