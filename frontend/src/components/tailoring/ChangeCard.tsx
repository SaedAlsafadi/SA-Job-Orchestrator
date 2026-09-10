import React, { useState } from 'react';
import { DiffViewer } from './DiffViewer';
import { CVTailoringChange } from '../../services/tailoringService';
import { useTranslation } from 'react-i18next';

interface Props {
    change: CVTailoringChange;
    onAccept: () => void;
    onReject: () => void;
    onRevise: (instruction: string) => void;
}

export const ChangeCard: React.FC<Props> = ({ change, onAccept, onReject, onRevise }) => {
    const [isRevising, setIsRevising] = useState(false);
    const [instruction, setInstruction] = useState('');
    const { t } = useTranslation();

    const handleReviseSubmit = () => {
        if (instruction.trim()) {
            onRevise(instruction);
            setIsRevising(false);
            setInstruction('');
        }
    };

    let borderColor = 'var(--border)';
    let bgColor = 'var(--surface)';
    if (change.user_decision === 'accepted') {
        borderColor = 'var(--applied)';
        bgColor = 'var(--applied-soft)';
    } else if (change.user_decision === 'rejected') {
        borderColor = 'var(--rejected)';
        bgColor = 'var(--rejected-soft)';
    }

    return (
        <div style={{
            border: `1px solid ${borderColor}`,
            background: bgColor,
            padding: 16,
            borderRadius: 'var(--r-md)',
            marginBottom: 16,
            transition: 'all .2s'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ font: '700 11px/1 var(--font)', textTransform: 'uppercase', color: 'var(--text-3)', letterSpacing: '.04em' }}>
                    {change.change_type}
                </span>
                
                <div style={{ display: 'flex', gap: 6 }}>
                    {change.review_severity === 'warning' && <span style={{ background: 'var(--warning-soft)', color: 'var(--warning)', padding: '4px 6px', borderRadius: 'var(--r-sm)', font: '700 10px/1 var(--font)', textTransform: 'uppercase' }}>{t('warning')}</span>}
                    {change.review_severity === 'blocked' && <span style={{ background: 'var(--failed-soft)', color: 'var(--failed)', padding: '4px 6px', borderRadius: 'var(--r-sm)', font: '700 10px/1 var(--font)', textTransform: 'uppercase' }}>{t('blocked')}</span>}
                    {change.user_decision !== 'pending' && (
                        <span style={{
                            padding: '4px 6px', borderRadius: 'var(--r-sm)', font: '800 10px/1 var(--font)', textTransform: 'uppercase',
                            background: change.user_decision === 'accepted' ? 'var(--applied)' : 'var(--rejected)',
                            color: '#fff'
                        }}>
                            {t(change.user_decision)}
                        </span>
                    )}
                </div>
            </div>
            
            <DiffViewer change={change} />
            
            <div style={{ marginTop: 12, font: '500 13px/1.4 var(--font)', color: 'var(--text)' }}>
                <strong style={{ color: 'var(--text-2)' }}>{t('reason')}:</strong> {change.reason}
            </div>
            
            {change.review_severity !== 'safe' && (
                <div style={{
                    marginTop: 12, padding: 10, borderRadius: 'var(--r-sm)', font: '500 12px/1.4 var(--font)',
                    background: change.review_severity === 'blocked' ? 'var(--failed-soft)' : 'var(--warning-soft)',
                    color: change.review_severity === 'blocked' ? 'var(--failed)' : 'var(--warning)'
                }}>
                    <strong>{t('ai_review')}:</strong> {change.review_reason}
                </div>
            )}
            
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                {change.user_decision === 'pending' && (
                    <>
                        <button 
                            disabled={change.review_severity === 'blocked'} 
                            onClick={onAccept}
                            title={change.review_severity === 'blocked' ? 'Cannot accept blocked changes' : ''}
                            style={{ padding: '6px 12px', background: 'var(--applied)', color: '#fff', border: 'none', borderRadius: 'var(--r-sm)', font: '700 12px/1 var(--font)', cursor: 'pointer', opacity: change.review_severity === 'blocked' ? 0.5 : 1 }}
                        >
                            Accept
                        </button>
                        <button 
                            onClick={onReject}
                            style={{ padding: '6px 12px', background: 'var(--surface-3)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', font: '700 12px/1 var(--font)', cursor: 'pointer' }}
                        >
                            Reject
                        </button>
                        <button 
                            onClick={() => setIsRevising(!isRevising)}
                            style={{ padding: '6px 12px', background: 'transparent', color: 'var(--text-2)', border: '1px solid transparent', borderRadius: 'var(--r-sm)', font: '600 12px/1 var(--font)', cursor: 'pointer' }}
                        >
                            Revise
                        </button>
                    </>
                )}
                {change.user_decision !== 'pending' && (
                    <button 
                        onClick={() => change.user_decision === 'accepted' ? onReject() : onAccept()}
                        disabled={change.user_decision === 'rejected' && change.review_severity === 'blocked'}
                        style={{ padding: '6px 12px', background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', font: '600 12px/1 var(--font)', cursor: 'pointer', opacity: (change.user_decision === 'rejected' && change.review_severity === 'blocked') ? 0.5 : 1 }}
                    >
                        Undo Decision
                    </button>
                )}
            </div>

            {isRevising && (
                <div style={{ marginTop: 16, padding: 12, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }}>
                    <label style={{ display: 'block', font: '700 11px/1 var(--font)', color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase' }}>What should be changed?</label>
                    <input
                        type="text"
                        value={instruction}
                        onChange={e => setInstruction(e.target.value)}
                        style={{ width: '100%', padding: '8px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', font: '400 13px/1.4 var(--font)', color: 'var(--text)', marginBottom: 12, outline: 'none' }}
                        placeholder="e.g., Make it sound more technical"
                    />
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={handleReviseSubmit} style={{ padding: '6px 12px', background: 'var(--accent)', color: 'var(--accent-ink)', border: 'none', borderRadius: 'var(--r-sm)', font: '700 12px/1 var(--font)', cursor: 'pointer' }}>Submit</button>
                        <button onClick={() => setIsRevising(false)} style={{ padding: '6px 12px', background: 'transparent', color: 'var(--text-2)', border: 'none', font: '600 12px/1 var(--font)', cursor: 'pointer' }}>Cancel</button>
                    </div>
                </div>
            )}
        </div>
    );
};
