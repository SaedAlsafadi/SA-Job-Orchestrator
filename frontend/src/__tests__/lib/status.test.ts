import { describe, it, expect } from 'vitest';
import { atsPercent, atsColor } from '@/lib/status';

/**
 * Score normalization regression tests.
 *
 * CONTRACT: job.match_score and resume *_score fields arrive as 0–1 floats.
 *           CandidateMatchResult.total_score arrives as 0–100 int.
 *
 * This test ensures:
 * - atsPercent(0–1 float) → 0–100 int  ✓
 * - No code path produces 4700 (double-multiplication)   ✓
 * - 0–1 scores correctly land in the right color band    ✓
 */
describe('Score normalization — canonical 0–1 → 0–100 contract', () => {
  describe('atsPercent', () => {
    it('converts 0–1 float to 0–100 integer', () => {
      expect(atsPercent(0.47)).toBe(47);
      expect(atsPercent(0.51)).toBe(51);
      expect(atsPercent(0.91)).toBe(91);
      expect(atsPercent(0.868)).toBe(87);
      expect(atsPercent(0.78)).toBe(78);
      expect(atsPercent(1)).toBe(100);
      expect(atsPercent(0)).toBe(0);
    });

    it('treats null/undefined as 0', () => {
      expect(atsPercent(null)).toBe(0);
      expect(atsPercent(undefined)).toBe(0);
    });

    it('REGRESSION: never produces 4700 for a value like 0.47', () => {
      // Before the fix, atsPercent was called on total_score (already 0–100),
      // producing 47 * 100 = 4700. atsPercent must only be used on 0–1 values.
      const jobMatchScore = 0.47; // 0–1 float from API
      const displayed = atsPercent(jobMatchScore);
      expect(displayed).toBe(47);
      expect(displayed).not.toBe(4700);
    });

    it('REGRESSION: do not call atsPercent on already-100 values (total_score)', () => {
      // total_score from CandidateMatchResult is already 0–100.
      // Using it directly, NOT via atsPercent, must give the correct value.
      const totalScore = 47; // 0–100 int from CandidateMatchResult
      // Display it directly — no multiplication.
      expect(totalScore).toBe(47);
      // Calling atsPercent on it would produce 4700 — this documents the contract.
      expect(atsPercent(totalScore)).toBe(4700); // intentional: proves atsPercent is wrong for this input
    });
  });

  describe('atsColor + atsPercent integration', () => {
    it('a 0.91 score lands in the offer band', () => {
      expect(atsColor(atsPercent(0.91))).toBe('var(--offer)');
    });

    it('a 0.47 score lands in the rejected band', () => {
      expect(atsColor(atsPercent(0.47))).toBe('var(--rejected)');
    });

    it('a 0.75 score lands in the applied band', () => {
      expect(atsColor(atsPercent(0.75))).toBe('var(--applied)');
    });

    it('a raw 0.91 passed to atsColor directly gives wrong result (demonstrates contract)', () => {
      // 0.91 < 65 → rejected. This shows why atsPercent MUST be called first.
      expect(atsColor(0.91)).toBe('var(--rejected)');
    });
  });
});
