import React from 'react';
import { CVTailoringChange } from '../../services/tailoringService';

interface Props {
    baseResumeText: string;
    changes: CVTailoringChange[];
}

export const ResumePreview: React.FC<Props> = ({ baseResumeText, changes }) => {
    
    let resumeData: any = {};
    try {
        resumeData = JSON.parse(baseResumeText);
    } catch {
        return <pre style={{ whiteSpace: 'pre-wrap', font: '400 13px/1.5 var(--mono)' }}>{baseResumeText}</pre>;
    }

    const getFieldStyle = (path: string): React.CSSProperties => {
        const related = changes.filter(c => c.target_reference.startsWith(path));
        if (related.length === 0) return { padding: 8 };
        
        if (related.some(c => c.user_decision === 'pending')) return { background: 'var(--warning-soft)', borderLeft: '4px solid var(--warning)', padding: '8px 12px' };
        if (related.some(c => c.user_decision === 'accepted')) return { background: 'var(--applied-soft)', borderLeft: '4px solid var(--applied)', padding: '8px 12px' };
        if (related.some(c => c.user_decision === 'rejected')) return { background: 'var(--rejected-soft)', borderLeft: '4px solid var(--rejected)', padding: '8px 12px', opacity: 0.5 };
        return { padding: 8 };
    };

    return (
        <div style={{ font: '400 14px/1.6 var(--font)', color: 'var(--text)' }}>
            <div style={{ textAlign: 'center', marginBottom: 24, ...getFieldStyle('name') }}>
                <h1 style={{ margin: '0 0 8px 0', font: '800 28px/1.2 var(--font)' }}>{resumeData.name}</h1>
                <div style={{ font: '500 13px/1.4 var(--font)', color: 'var(--text-3)', display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
                    <span>{resumeData.email}</span>
                    <span>{resumeData.phone}</span>
                    <span>{resumeData.location}</span>
                </div>
            </div>

            {resumeData.summary && (
                <div style={{ marginBottom: 24, ...getFieldStyle('summary') }}>
                    <h2 style={{ margin: '0 0 8px 0', font: '800 14px/1 var(--font)', textTransform: 'uppercase', letterSpacing: '.04em', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>Summary</h2>
                    <p style={{ margin: 0 }}>{resumeData.summary}</p>
                </div>
            )}

            {resumeData.skills && resumeData.skills.length > 0 && (
                <div style={{ marginBottom: 24, ...getFieldStyle('skills') }}>
                    <h2 style={{ margin: '0 0 8px 0', font: '800 14px/1 var(--font)', textTransform: 'uppercase', letterSpacing: '.04em', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>Skills</h2>
                    <p style={{ margin: 0 }}>{resumeData.skills.join(', ')}</p>
                </div>
            )}

            {resumeData.experience && resumeData.experience.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                    <h2 style={{ margin: '0 0 16px 0', font: '800 14px/1 var(--font)', textTransform: 'uppercase', letterSpacing: '.04em', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>Experience</h2>
                    {resumeData.experience.map((exp: any, idx: number) => (
                        <div key={idx} style={{ marginBottom: 16, ...getFieldStyle(`experience[${idx}]`) }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                                <h3 style={{ margin: 0, font: '700 15px/1.2 var(--font)' }}>{exp.title}</h3>
                                <span style={{ font: '600 12px/1 var(--font)', color: 'var(--text-3)' }}>{exp.duration}</span>
                            </div>
                            <div style={{ font: '600 14px/1.4 var(--font)', color: 'var(--text-2)', marginBottom: 8 }}>{exp.company}</div>
                            {exp.description && (
                                <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                                    {exp.description.split('\n').filter(Boolean).map((bullet: string, i: number) => (
                                        <li key={i} style={{ marginBottom: 4 }}>{bullet.replace(/^- /, '')}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
