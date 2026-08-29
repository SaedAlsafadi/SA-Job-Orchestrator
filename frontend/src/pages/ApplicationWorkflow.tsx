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
  const [capabilities, setCapabilities] = useState<any>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [appState, setAppState] = useState<any>(null);

  useEffect(() => {
    api.get("/workflow/capabilities").then(res => {
      setCapabilities(res.data);
    }).catch(err => console.error("Failed to load capabilities", err));
  }, []);

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
    setLoading(true); setError(null);
    try {
      // 1. Perform AI Match
      setStep(3); // PREPARING UI
      const matchRes = await api.post(`/workflow/jobs/${jobId}/match`);
      const matchResult = matchRes.data;
      
      // Update the local jobs list so the match score is reflected
      setDiscoveredJobs(jobs => jobs.map(j => j.id === jobId ? { ...j, match_score: matchResult.score } : j));

      // 2. Mock Tailoring & Prepare Application
      // In a real flow, you'd call /tailor-resume here, but for now we pass the mock tailoring and use the match result
      const payload = {
        summary: "Expert Engineer", experiences: [], skills: ["Python"]
      };
      const res = await api.post(`/workflow/jobs/${jobId}/prepare-application`, payload);
      const newAppId = res.data.application_id;
      
      // Real polling for WAITING_FOR_REVIEW state
      const pollInterval = setInterval(async () => {
        try {
          const pollRes = await api.get(`/workflow/applications/${newAppId}`);
          if (pollRes.data.status !== "preparing" && pollRes.data.status !== "running") {
            clearInterval(pollInterval);
            
            // Reconstruct state from backend real state_data
            const stateData = pollRes.data.run?.state_data || {};
            
            // Map real state_data questions to prefilled, filled, unanswered arrays
            const prefilled_fields = (stateData.questions || []).filter((q: any) => q.prefilled);
            const filled_fields = (stateData.questions || []).filter((q: any) => !q.prefilled && !q.requires_human && q.answer);
            const unanswered = (stateData.questions || []).filter((q: any) => q.requires_human || (!q.prefilled && !q.answer));
            
            const warnings = [];
            if (stateData.cv_present) {
               warnings.push("Platform CV detected. We recommend reviewing if it needs replacement.");
            }
            
            if (pollRes.data.status === "failed") {
                setError("Application preparation failed: " + (pollRes.data.run?.error || "Unknown error"));
                setStep(1);
                return;
            }

            setAppState({
              id: newAppId,
              status: pollRes.data.status,
              match_score: matchResult.score || 85,
              job: discoveredJobs.find((j: any) => j.id === jobId) || { id: jobId, platform: "workable" },
              screenshot: stateData.screenshot ? `http://localhost:8000/${stateData.screenshot}` : "/smoke_test.png",
              cv_present: stateData.cv_present || false,
              prefilled_fields: prefilled_fields.map((q: any) => ({ label: q.label, value: q.answer || q.current_value })),
              filled_fields: filled_fields.map((q: any) => ({ label: q.label, value: q.answer, confidence: q.confidence || 0.9 })),
              unanswered_questions: unanswered.map((q: any) => ({ id: q.question_id, label: q.label, category: q.category || 'unknown', answer: '' })),
              warnings: warnings
            });
            setStep(4);
          }
        } catch (e) {
          console.error(e);
        }
      }, 3000);
      
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
      setStep(1);
    }
    setLoading(false);
  };
  const handleAnswerChange = (id: string, value: string) => {
    setAppState((prev: any) => {
      const updated = prev.unanswered_questions.map((q: any) => q.id === id ? { ...q, answer: value } : q);
      return { ...prev, unanswered_questions: updated };
    });
  };

  const saveAnswers = async () => {
    if (!appState || !appState.id) return;
    setLoading(true); setError(null);
    try {
      const answers: Record<string, string> = {};
      appState.unanswered_questions.forEach((q: any) => {
        if (q.answer.trim() !== '') {
          answers[q.id] = q.answer;
        }
      });
      await api.patch(`/workflow/applications/${appState.id}/questions`, { answers });
      alert("Answers saved successfully! You can now submit.");
      // Move answered ones to filled_fields
      const newFilled = [...appState.filled_fields];
      const newUnanswered = [];
      for (const q of appState.unanswered_questions) {
        if (answers[q.id]) {
          newFilled.push({ label: q.label, value: answers[q.id], confidence: 1.0 });
        } else {
          newUnanswered.push(q);
        }
      }
      setAppState({ ...appState, filled_fields: newFilled, unanswered_questions: newUnanswered });
    } catch (e: any) { setError(e.response?.data?.detail || e.message); }
    setLoading(false);
  };

  useEffect(() => {
    let submitPoll: any;
    if (appState && appState.status === "submitting") {
      submitPoll = setInterval(async () => {
        try {
          const res = await api.get(`/workflow/applications/${appState.id}`);
          if (res.data.status !== "submitting") {
            clearInterval(submitPoll);
            setAppState((prev: any) => ({ ...prev, status: res.data.status }));
            if (res.data.status === "applied") {
              alert("Application successfully submitted!");
            } else if (res.data.status === "submission_unknown") {
              setError("Submission status unknown. The bot clicked submit, but could not verify the success message. Check the post-submission screenshot.");
            } else if (res.data.status === "failed" || res.data.status === "submission_blocked") {
              setError("Submission failed: " + (res.data.run?.error || "Unknown error"));
            }
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 3000);
    }
    return () => clearInterval(submitPoll);
  }, [appState?.status, appState?.id]);

  const submitApplication = async () => {
    if (!appState || !appState.id) return;
    
    if (appState.unanswered_questions.length > 0) {
      if (!window.confirm("You have unanswered questions. The submission might fail. Proceed anyway?")) {
        return;
      }
    }
    
    setLoading(true); setError(null);
    try {
      await api.post(`/workflow/applications/${appState.id}/approve`);
      await api.post(`/workflow/applications/${appState.id}/submit`);
      setAppState({ ...appState, status: "submitting" });
      alert("Submission started! Transitioning to Submitting state.");
    } catch (e: any) { setError(e.response?.data?.detail || e.message); }
    setLoading(false);
  };

  return (
    <div style={{ padding: "40px", maxWidth: "800px", margin: "0 auto", fontFamily: "var(--font)" }}>
      <h1 style={{ fontSize: "24px", fontWeight: 700, margin: "0 0 8px 0" }}>Prepare Application</h1>
      <p style={{ color: "var(--text-2)", marginBottom: "32px" }}>Provide a Job Board URL (Workable, Greenhouse) to prepare an application.</p>

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
            <label style={labelStyle}>Job Board URL
              <input style={inputStyle} value={jobUrl} onChange={e => setJobUrl(e.target.value)} placeholder="https://apply.workable.com/... or https://boards.greenhouse.io/..." />
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
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                {appState.status === "submitting" && <span style={{ color: "var(--accent)" }}>Submitting...</span>}
                {appState.status === "applied" && <span style={{ color: "var(--success)" }}>âœ“ Successfully Applied!</span>}
                {appState.status === "submission_unknown" && <span style={{ color: "var(--warning)" }}>âš  Status Unknown</span>}
                {(appState.status === "failed" || appState.status === "submission_blocked") && <span style={{ color: "var(--failed)" }}>âœ˜ Submission Failed</span>}
                <div style={{ background: "var(--surface-2)", padding: "4px 12px", borderRadius: "var(--r-sm)", fontWeight: 600, color: "var(--accent)" }}>
                  Match: {appState.match_score}%
                </div>
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
                    <div key={i} style={{ marginBottom: 4, wordBreak: "break-word" }}><strong>{f.label}:</strong> {f.value}</div>
                  ))}
                </div>

                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>We added</h4>
                <div style={{ background: "var(--surface-2)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 16 }}>
                  {appState.filled_fields.map((f: any, i: number) => (
                    <div key={i} style={{ marginBottom: 4, wordBreak: "break-word" }}><strong>{f.label}:</strong> {f.value} <span style={{ color: "var(--accent)", fontSize: "11px" }}>(Conf: {f.confidence})</span></div>
                  ))}
                </div>
                
                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>Human attention required</h4>
                {appState.unanswered_questions.length > 0 ? (
                  <div>
                    {appState.unanswered_questions.map((q: any) => (
                      <div key={q.id} style={{ background: "var(--failed-soft)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 8, display: "flex", flexDirection: "column", gap: "8px" }}>
                        <div style={{ color: "var(--failed)", wordBreak: "break-word" }}>
                          <strong>{q.label}</strong> (ID: {q.id})
                        </div>
                        <textarea 
                          placeholder="Your answer..." 
                          value={q.answer || ''}
                          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                          style={{ padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", width: "100%", boxSizing: "border-box", minHeight: "80px", resize: "vertical", fontFamily: "var(--font)", fontSize: "14px" }} 
                        />
                      </div>
                    ))}
                    <button style={{ ...buttonStyle, marginTop: "8px", width: "100%", background: "var(--review)", color: "#fff" }} onClick={saveAnswers} disabled={loading}>
                      {loading ? "Saving..." : "Save Manual Answers"}
                    </button>
                  </div>
                ) : (
                  <div style={{ background: "var(--surface-2)", padding: 12, borderRadius: "var(--r-sm)", fontSize: "13px", marginBottom: 16 }}>
                    No manual attention required.
                  </div>
                )}
              </div>
              
              <div>
                <h4 style={{ margin: "0 0 12px 0", color: "var(--text-2)", fontSize: "12px", textTransform: "uppercase" }}>Browser Screenshot</h4>
                <div style={{ height: "300px", background: "var(--surface-2)", borderRadius: "var(--r-sm)", border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-3)", fontSize: "12px" }}>
                  <img src={appState.screenshot} alt="Form state" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
                </div>
              </div>
            </div>

            <div style={{ marginTop: 24, paddingTop: 24, borderTop: "1px solid var(--border)", display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button onClick={() => { setStep(1); setAppState(null); }} style={{...buttonStyle, background: "var(--surface-2)", color: "var(--text)"}}>Cancel</button>
              {capabilities && appState.job.platform && capabilities[appState.job.platform]?.submission ? (
                 <button style={buttonStyle} onClick={submitApplication} disabled={loading}>
                   {loading ? "Submitting..." : "Submit Application"}
                 </button>
              ) : (
                 <button style={{...buttonStyle, opacity: 0.5, cursor: "not-allowed"}} disabled title="This integration does not support automated submission yet.">Submit Application (Unsupported)</button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
