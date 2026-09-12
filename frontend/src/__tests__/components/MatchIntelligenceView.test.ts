import { describe, expect, it } from 'vitest';

import { getMatchScorePercent } from '@/components/matching/MatchIntelligenceView';

describe('getMatchScorePercent', () => {
  it('renders the persisted matcher total_score without multiplying it again', () => {
    expect(getMatchScorePercent({ total_score: 6 })).toBe(6);
  });

  it('supports normalized score values used by older callers', () => {
    expect(getMatchScorePercent({ score: 0.47 })).toBe(47);
  });

  it('prefers the canonical total_score when both fields are present', () => {
    expect(getMatchScorePercent({ total_score: 51, score: 0.51 })).toBe(51);
  });
});
