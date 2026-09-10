import React from 'react';
import { CVTailoringChange } from '../../services/tailoringService';
import { useTranslation } from 'react-i18next';

interface Props {
    change: CVTailoringChange;
}

export const DiffViewer: React.FC<Props> = ({ change }) => {
    const { t } = useTranslation();
    return (
        <div style={{ borderRadius: 'var(--r-sm)', border: '1px solid var(--border)', background: 'var(--surface-2)', overflow: 'hidden' }}>
            <div style={{ background: 'var(--surface-3)', padding: '6px 10px', font: '600 11px/1.2 var(--mono)', color: 'var(--text-3)', borderBottom: '1px solid var(--border)' }}>
                {t('target')}: {change.target_reference}
            </div>
            <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(change.change_type === 'remove' || change.change_type === 'modify') && (
                    <div style={{ color: 'var(--rejected)', background: 'var(--rejected-soft)', padding: '6px 10px', borderRadius: 'var(--r-sm)', font: '400 13px/1.4 var(--font)', textDecoration: 'line-through' }} dir="auto">
                        - {change.original_text || 'None'}
                    </div>
                )}
                {(change.change_type === 'add' || change.change_type === 'modify') && (
                    <div style={{ color: 'var(--applied)', background: 'var(--applied-soft)', padding: '6px 10px', borderRadius: 'var(--r-sm)', font: '400 13px/1.4 var(--font)' }} dir="auto">
                        + {change.proposed_text}
                    </div>
                )}
            </div>
        </div>
    );
};
