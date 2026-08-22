import re

with open("frontend/src/pages/ApplicationWorkflow.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Change stateData extraction
content = content.replace("const stateData = pollRes.data.state_data || {};", "const stateData = pollRes.data.run?.state_data || {};")

# Fix 2: Better handling of match score in UI
content = content.replace("match_score: discoveredJobs.find((j: any) => j.id === jobId)?.match_score || pollRes.data.ats_score || 85", "match_score: pollRes.data.match_score || discoveredJobs.find((j: any) => j.id === jobId)?.match_score || 85")

# Fix 3: In prepareApplication, actually call /match first!
prepare_func = """  const prepareApplication = async (jobId: string) => {
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
  };"""

# We need to replace the old prepareApplication with this new one
content = re.sub(r'const prepareApplication = async \(jobId: string\) => \{.*?(?=\n  const handleAnswerChange)', prepare_func, content, flags=re.DOTALL)

# Fix 4: Make unanswered questions textareas so text input is handled better
textarea_input = """<textarea 
                          placeholder="Your answer..." 
                          value={q.answer || ''}
                          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                          style={{ padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", width: "100%", boxSizing: "border-box", minHeight: "80px", resize: "vertical", fontFamily: "var(--font)", fontSize: "14px" }} 
                        />"""
content = re.sub(r'<input[^>]*type="text"[^>]*placeholder="Your answer..."[^>]*onChange=\{\(e\) => handleAnswerChange\(q\.id, e\.target\.value\)\}[^>]*/>', textarea_input, content, flags=re.DOTALL)

with open("frontend/src/pages/ApplicationWorkflow.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("ApplicationWorkflow patched successfully.")
