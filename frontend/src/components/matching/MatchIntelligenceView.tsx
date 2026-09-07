import { useState } from "react";
import Icon from "@/components/ui/Icon";

function getMatchVerdict(recommendation: string): { label: string; color: string } {
  switch ((recommendation || '').toLowerCase()) {
    case 'strong_apply':
    case 'apply':     return { label: 'Strong Match', color: 'var(--approved)' };
    case 'consider':  return { label: 'Possible Match', color: 'var(--interview)' };
    case 'skip':      return { label: 'Poor Match', color: 'var(--rejected)' };
    default:          return { label: 'Analyzed', color: 'var(--text-2)' };
  }
}

export function MatchIntelligenceView({ result }: { result: any }) {
  const [showDetailed, setShowDetailed] = useState(false);
  const analysis = result;

  if (!analysis) return null;

  const scoreDisplay = typeof analysis.score === 'number' 
    ? (analysis.score * 100).toFixed(0) + '%'
    : (analysis.score || 'N/A');
    
  const verdictInfo = getMatchVerdict(analysis.recommendation || (analysis.score > 0.8 ? 'apply' : 'skip'));

  return (
    <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {analysis.blockers && analysis.blockers.length > 0 && (
        <div style={{ background: 'var(--rejected-soft)', border: '1px solid var(--rejected)', borderRadius: 'var(--r-lg)', padding: 16 }}>
          <h4 style={{ margin: '0 0 8px 0', color: 'var(--rejected)', display: 'flex', gap: 8, alignItems: 'center' }}><Icon name="alert" size={16} /> Potential blockers</h4>
          <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px' }}>
            {analysis.blockers.map((r: string, i: number) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 18, color: verdictInfo.color }}>{verdictInfo.label}</h3>
            <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>{scoreDisplay}</div>
          </div>
          {analysis.data_quality && analysis.data_quality !== 'HIGH' && (
            <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-3)', maxWidth: 150 }}>
              <span style={{ fontWeight: 600 }}>Source quality: {analysis.data_quality}</span>
              <div style={{ marginTop: 2 }}>{analysis.data_quality_explanation}</div>
            </div>
          )}
        </div>
        
        {analysis.explanation && (
          <div>
            <h4 style={{ margin: '0 0 4px 0', fontSize: 13, color: 'var(--text-2)' }}>Why this is a {verdictInfo.label.toLowerCase()}</h4>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)' }}>{analysis.explanation}</p>
          </div>
        )}
      </div>

      {analysis.strong_matches && analysis.strong_matches.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 8px 0', fontSize: 14, color: 'var(--text-1)' }}>Strong matches</h4>
          <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {analysis.strong_matches.map((s: string, i: number) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}

      {(analysis.gaps?.length > 0 || analysis.critical_gaps?.length > 0) && (
        <div>
          <h4 style={{ margin: '0 0 8px 0', fontSize: 14, color: 'var(--text-1)' }}>Gaps</h4>
          <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {analysis.critical_gaps?.map((g: string, i: number) => <li key={`c-${i}`} style={{color: 'var(--rejected)'}}><strong>Critical:</strong> {g}</li>)}
            {analysis.gaps?.map((g: string, i: number) => <li key={`g-${i}`}>- {g}</li>)}
          </ul>
        </div>
      )}

      {analysis.requirement_analysis && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h4 style={{ margin: 0, fontSize: 14, color: 'var(--text-1)' }}>Requirements</h4>
            <button 
              onClick={() => setShowDetailed(!showDetailed)}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, padding: 0 }}
            >
              {showDetailed ? 'Hide detailed analysis' : 'View detailed analysis'}
            </button>
          </div>
          
          <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
            {analysis.requirement_analysis.filter((r:any) => r.status === 'MATCH').length} of {analysis.requirement_analysis.length} supported
          </div>

          {showDetailed && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
              {analysis.requirement_analysis.map((req:any, idx:number) => (
                <div key={req.requirement_id || idx} style={{ padding: 12, borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <strong style={{ fontSize: 13, color: req.status === 'MATCH' ? 'var(--approved)' : req.status === 'PARTIAL' ? 'var(--interview)' : req.status === 'GAP' ? 'var(--rejected)' : 'var(--text-3)' }}>
                      {req.status === 'MATCH' ? '✓ ' : req.status === 'PARTIAL' ? '— ' : req.status === 'GAP' ? '✗ ' : '? '}
                      {req.normalized_requirement}
                    </strong>
                    <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{req.importance}</span>
                  </div>
                  <p style={{ margin: '4px 0', fontSize: 12, color: 'var(--text-2)' }}>{req.explanation}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
