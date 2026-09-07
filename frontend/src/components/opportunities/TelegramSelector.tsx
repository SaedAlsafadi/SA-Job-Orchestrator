import { useState, useEffect } from "react";
import api from "@/services/api";

const cardStyle: React.CSSProperties = {
  background: "var(--surface)", border: "1px solid var(--border)",
  borderRadius: "var(--r-md)", padding: "16px", marginBottom: "12px", cursor: "pointer",
  transition: "border-color 0.2s"
};

export function TelegramSelector({ onSelect }: { onSelect: (job: any) => void }) {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch recent jobs from telegram
    api.get("/jobs/?source_type=telegram&page_size=10")
      .then(res => {
        setJobs(res.data.items);
      })
      .catch(err => console.error("Failed to fetch telegram jobs", err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading recent Telegram messages...</div>;
  if (jobs.length === 0) return <div style={{ color: 'var(--text-3)' }}>No recent jobs found from Telegram.</div>;

  return (
    <div>
      <h3 style={{ margin: "0 0 16px 0", fontSize: "14px" }}>Recent Telegram Opportunities</h3>
      {jobs.map(job => (
        <div key={job.id} style={cardStyle} onClick={() => onSelect(job)} 
             onMouseOver={e => e.currentTarget.style.borderColor = "var(--accent)"}
             onMouseOut={e => e.currentTarget.style.borderColor = "var(--border)"}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <strong style={{ fontSize: "15px" }}>{job.title}</strong>
            <span style={{ fontSize: "12px", color: "var(--text-3)" }}>
              {new Date(job.received_at || job.created_at).toLocaleString()}
            </span>
          </div>
          <div style={{ fontSize: "13px", color: "var(--text-2)", marginBottom: "8px" }}>{job.company}</div>
          <div style={{ fontSize: "13px", color: "var(--text-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxHeight: "40px" }}>
            {job.description}
          </div>
        </div>
      ))}
    </div>
  );
}
