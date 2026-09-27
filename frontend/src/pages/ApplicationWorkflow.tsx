import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/services/api";
import { TelegramSelector } from "@/components/opportunities/TelegramSelector";
import { MatchIntelligenceView } from "@/components/matching/MatchIntelligenceView";
import { PackageReview } from "@/components/applications/PackageReview";
import { listResumes } from "@/services/resumeService";
import { tailoringService } from "@/services/tailoringService";

const tabStyle = (active: boolean): React.CSSProperties => ({
  flex: 1, padding: "12px 16px", cursor: "pointer", fontWeight: 700, fontSize: "13px",
  borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
  color: active ? "var(--text)" : "var(--text-3)",
  background: active ? "var(--surface-2)" : "transparent",
  borderTop: "none", borderLeft: "none", borderRight: "none",
  transition: "all .2s var(--ease)"
});

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "14px", background: "var(--surface-3)",
  border: "1px solid var(--border)", borderRadius: "var(--r-md)",
  color: "var(--text)", fontFamily: "var(--font)", fontSize: "14px",
  marginTop: "6px", marginBottom: "20px", outline: "none",
  boxShadow: "inset 0 1px 2px rgba(0,0,0,0.1)", transition: "border-color .2s"
};
const buttonStyle: React.CSSProperties = {
  background: "var(--accent)", color: "var(--accent-ink)", padding: "12px 24px",
  border: "1px solid var(--accent)", borderRadius: "var(--r-md)", fontWeight: 700, cursor: "pointer", fontSize: "13px",
  boxShadow: "0 0 0 1px var(--accent-line),0 6px 16px -8px var(--accent-glow)", transition: "all .2s"
};
const cardStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)", padding: "28px", marginBottom: "24px", boxShadow: "var(--shadow-1)"
};
const labelStyle: React.CSSProperties = { fontSize: "13px", color: "var(--text-2)", fontWeight: 700, display: "block", marginBottom: 6, letterSpacing: "0.01em" };

type SourceType = "url" | "paste" | "telegram";

export function ApplicationWorkflow() {
  const navigate = useNavigate();
  const [source, setSource] = useState<SourceType>("url");
  const [inputText, setInputText] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobData, setJobData] = useState<any>(null);
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [startingTailoring, setStartingTailoring] = useState(false);
  
  // Polling logic when job is processing
  useEffect(() => {
    if (!jobId || (jobData && jobData.status !== "processing" && jobData.status !== "received")) return;
    
    const interval = setInterval(() => {
      api.get(`/jobs/${jobId}`).then(res => {
        setJobData(res.data);
      }).catch(err => console.error("Poll error", err));
    }, 2000);
    
    return () => clearInterval(interval);
  }, [jobId, jobData]);

  const handleSubmit = async () => {
    if (!inputText.trim()) {
      setError("Please enter the opportunity details.");
      return;
    }
    setLoading(true); setError(null);
    try {
      const res = await api.post("/opportunities/ingest", {
        text: inputText,
        source_type: source
      });
      setJobId(res.data.job_id);
      // Fetch initial state immediately
      const jobRes = await api.get(`/jobs/${res.data.job_id}`);
      setJobData(jobRes.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleTelegramSelect = (job: any) => {
    setJobId(job.id);
    setJobData(job);
  };
  
  const overrideRoute = async (routeType: string) => {
    if (!jobId) return;
    try {
      await api.post(`/opportunities/${jobId}/route`, { preferred_route_type: routeType });
      // refetch job
      const jobRes = await api.get(`/jobs/${jobId}`);
      setJobData(jobRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const startTailoring = async () => {
    if (!jobId) return;
    setError(null);
    setStartingTailoring(true);
    try {
      const { items } = await listResumes();
      const baseResume = items.find((resume) => resume.type === "base") ?? items[0];
      if (!baseResume) {
        setError("Upload a base resume before tailoring your CV.");
        return;
      }
      const session = await tailoringService.startSession(jobId, baseResume.id);
      navigate(`/cv-tailoring/${session.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to start CV tailoring");
    } finally {
      setStartingTailoring(false);
    }
  };

  // Phase 19.5: auto-detect an existing application for this job so the
  // package review is reachable after tailoring (or on return visits) without
  // the user knowing any internal IDs.
  useEffect(() => {
    if (!jobId || applicationId) return;
    api
      .get("/applications/", { params: { page_size: 50 } })
      .then((res) => {
        const match = (res.data.items || []).find((a: any) => a.job_id === jobId);
        if (match) setApplicationId(match.id);
      })
      .catch(() => undefined);
  }, [jobId, jobData, applicationId]);

  // Phase 19: create the application record (REVIEW mode) and open the package review.
  const prepareApplication = async () => {
    if (!jobId) return;
    setError(null);
    try {
      const resumes = await listResumes().catch(() => ({ items: [], total: 0 }));
      const tailored = resumes.items
        .filter((resume) => resume.job_id === jobId && resume.type === "tailored")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
      const res = await api.post("/applications/", {
        job_id: jobId,
        resume_id: tailored?.id,
        apply_mode: "review",
      });
      setApplicationId(res.data.id);
    } catch (err: any) {
      // An active application for this job may already exist (unique-active
      // constraint) - detect and open its package review instead of failing.
      try {
        const list = await api.get("/applications/", { params: { page_size: 50 } });
        const match = (list.data.items || []).find((a: any) => a.job_id === jobId);
        if (match) {
          setApplicationId(match.id);
          return;
        }
      } catch {
        /* fall through to the original error */
      }
      setError(err.response?.data?.detail || err.message);
    }
  };

  if (jobData) {
    const isProcessing = jobData.status === "processing" || jobData.status === "received" || jobData.status === "new";
    
    return (
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "24px" }}>
        <button onClick={() => {setJobId(null); setJobData(null);}} style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", marginBottom: 16 }}>&larr; Back to Inbox</button>
        
        {isProcessing ? (
          <div style={{ textAlign: "center", padding: 40, ...cardStyle }}>
            <h2>Analyzing this job...</h2>
            <p style={{ color: "var(--text-2)" }}>Please wait while we extract details, normalize requirements, and evaluate your match.</p>
          </div>
        ) : (
          <div>
            <div style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h1 style={{ margin: "0 0 8px 0" }}>{jobData.title}</h1>
                  <h3 style={{ margin: 0, color: "var(--text-2)" }}>{jobData.company} • {jobData.location}</h3>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "12px", color: "var(--text-3)", textTransform: "uppercase" }}>Source</div>
                  <div style={{ fontWeight: 600 }}>{jobData.source_type}</div>
                </div>
              </div>
              
              <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "20px 0" }} />
              
              <div style={{ display: "flex", gap: "24px" }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "12px", color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4 }}>Language</div>
                  <div>{jobData.detected_language || "Unknown"}</div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "12px", color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4 }}>Source Quality</div>
                  <div>{jobData.data_quality_flags?.quality || "HIGH"}</div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "12px", color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4 }}>Application Route</div>
                  <select 
                    value={jobData.routes?.find((r:any) => r.is_preferred)?.route_type || ""} 
                    onChange={e => overrideRoute(e.target.value)}
                    style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--surface-2)", color: "var(--text)" }}
                  >
                    <option value="WORKABLE">Workable</option>
                    <option value="GREENHOUSE">Greenhouse</option>
                    <option value="LEVER">Lever</option>
                    <option value="COMPANY_WEBSITE">Company Website</option>
                    <option value="EMAIL">Email</option>
                    <option value="LINKEDIN">LinkedIn</option>
                    <option value="MANUAL">Manual</option>
                  </select>
                </div>
              </div>
              
              {jobData.status === "failed" && (
                <div style={{ background: "var(--danger-soft)", color: "var(--danger)", padding: 12, borderRadius: 8, marginTop: 16 }}>
                  <strong>Could not process this opportunity.</strong> {jobData.raw_data?.error}
                </div>
              )}
            </div>
            
            {/* Match Intelligence */}
            {jobData.match_score !== undefined && jobData.match_score !== null && (
               <MatchIntelligenceView result={jobData.raw_data?.match_result || { score: jobData.match_score }} />
            )}
            
            <div style={{ textAlign: "right", marginTop: 24, display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button disabled={startingTailoring} onClick={startTailoring} style={buttonStyle}>
                {startingTailoring ? "Starting…" : "Create Tailored CV"}
              </button>
              {!applicationId && (
                <button onClick={prepareApplication} style={buttonStyle}>Prepare Application Package</button>
              )}
            </div>

            {/* Phase 19: package review — once an application exists for this job */}
            {applicationId && (
              <div style={{ marginTop: 32 }}>
                <PackageReview
                  applicationId={applicationId}
                  jobId={jobId ?? undefined}
                  job={{ title: jobData.title, company: jobData.company, location: jobData.location }}
                  language={jobData.detected_language === "ar" ? "ar" : "en"}
                  matchSummary={jobData.raw_data?.match_result}
                  onStatus={(msg, kind) => {
                    if (kind !== "success") setError(msg);
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", animation: 'aaUp .4s var(--ease) both' }}>
      <h1 style={{ margin: "0 0 10px 0", font: '800 24px/1.1 var(--font)', letterSpacing: '-.03em' }}>Import Opportunity</h1>
      <p style={{ color: "var(--text-3)", margin: "0 0 24px 0", font: '500 13px/1.4 var(--font)' }}>Provide a link or paste a description to let the agent analyze the role and evaluate your match.</p>
      
      <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
        <div style={{ display: "flex", borderBottom: "1px solid var(--border)", background: "var(--surface-3)" }}>
          <button style={tabStyle(source === "url")} onClick={() => {setSource("url"); setInputText(""); setError(null);}}>
            URL
          </button>
          <button style={tabStyle(source === "paste")} onClick={() => {setSource("paste"); setInputText(""); setError(null);}}>
            Paste Text
          </button>
          <button style={tabStyle(source === "telegram")} onClick={() => {setSource("telegram"); setInputText(""); setError(null);}}>
            Telegram
          </button>
        </div>
        
        <div style={{ padding: "28px" }}>
          {source === "telegram" ? (
            <TelegramSelector onSelect={handleTelegramSelect} />
          ) : (
            <div>
              {source === "url" ? (
                <>
                  <label style={labelStyle}>Job URL</label>
                  <input 
                    style={inputStyle} 
                    placeholder="https://..." 
                    value={inputText} onChange={e => setInputText(e.target.value)} 
                  />
                </>
              ) : (
                <>
                  <label style={labelStyle}>Job Description / Text</label>
                  <textarea 
                    style={{ ...inputStyle, minHeight: "150px", resize: "vertical" }}
                    placeholder="Paste job posting, message, or email text here..."
                    value={inputText} onChange={e => setInputText(e.target.value)}
                  />
                </>
              )}
              
              {error && <div style={{ color: "var(--failed)", fontSize: "12.5px", marginBottom: "16px", background: "var(--failed-soft)", padding: "10px 14px", borderRadius: "var(--r-sm)", border: "1px solid var(--failed)" }}>{error}</div>}
              
              <div style={{ textAlign: "right", marginTop: 8 }}>
                <button onClick={handleSubmit} disabled={loading} style={{ ...buttonStyle, opacity: loading ? 0.7 : 1 }}>
                  {loading ? "Ingesting..." : "Process Opportunity"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
