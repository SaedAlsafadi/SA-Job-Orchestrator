import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/services/api";
import { TelegramSelector } from "@/components/opportunities/TelegramSelector";
import { MatchIntelligenceView } from "@/components/matching/MatchIntelligenceView";

const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: "10px 16px", cursor: "pointer", fontWeight: 600, fontSize: "14px",
  borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
  color: active ? "var(--accent)" : "var(--text-3)",
  background: "none", borderTop: "none", borderLeft: "none", borderRight: "none"
});

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "12px", background: "var(--surface-2)",
  border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
  color: "var(--text)", fontFamily: "var(--font)", fontSize: "14px",
  marginTop: "4px", marginBottom: "16px"
};
const buttonStyle: React.CSSProperties = {
  background: "var(--accent)", color: "var(--accent-ink)", padding: "12px 24px",
  border: "none", borderRadius: "var(--r-md)", fontWeight: 700, cursor: "pointer", fontSize: "14px"
};
const cardStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)", padding: "24px", marginBottom: "24px", boxShadow: "var(--shadow-1)"
};
const labelStyle: React.CSSProperties = { fontSize: "13px", color: "var(--text-2)", fontWeight: 600, display: "block", marginBottom: 4 };

type SourceType = "url" | "paste" | "telegram";

export function ApplicationWorkflow() {
  const navigate = useNavigate();
  const [source, setSource] = useState<SourceType>("url");
  const [inputText, setInputText] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobData, setJobData] = useState<any>(null);
  
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

  const startTailoring = () => {
    navigate(`/cv-tailoring/new?jobId=${jobId}`);
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
            
            <div style={{ textAlign: "right", marginTop: 24 }}>
              <button onClick={startTailoring} style={buttonStyle}>Create Tailored CV</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 600, margin: "40px auto" }}>
      <h1 style={{ marginBottom: "8px" }}>Prepare Application</h1>
      <p style={{ color: "var(--text-2)", marginBottom: "32px" }}>Where did you receive this opportunity?</p>
      
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "24px" }}>
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
      
      {source === "telegram" ? (
        <TelegramSelector onSelect={handleTelegramSelect} />
      ) : (
        <div style={cardStyle}>
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
          
          {error && <div style={{ color: "var(--danger)", fontSize: "13px", marginBottom: "16px" }}>{error}</div>}
          
          <div style={{ textAlign: "right" }}>
            <button onClick={handleSubmit} disabled={loading} style={{ ...buttonStyle, opacity: loading ? 0.7 : 1 }}>
              {loading ? "Ingesting..." : "Process Opportunity"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
