/**
 * SkillGapSection
 *
 * Full-detail matched / missing skills breakdown.
 * Used in:
 *   • The expand-explain toggle on internship cards (alongside LLM context)
 *   • The dedicated /skill-gap/:id page
 *
 * STRICT CONSISTENCY CONTRACT:
 *  - `matchedSkills` and `missingSkills` are rendered VERBATIM from the API
 *    (the stored semantic values on the recommendations row). No filtering,
 *    no re-casing, no dedup, no transformation of skill names.
 *  - The insight line uses ONLY the LENGTH of the backend arrays.
 *  - The match percentage is NOT re-derived here.
 *
 * The internship card's always-visible preview (top 4 each) lives in
 * Internships.tsx. This component renders ALL skills — no truncation.
 */

interface SkillGapSectionProps {
  matchedSkills: string[];
  missingSkills: string[];
  /** Match percentage (0-100). Used to gate the "all matched" claim: we only
   *  say "all requirements matched" at a genuinely high score (>= 90), so the
   *  message can never contradict a low score. Defaults to a passing value when
   *  omitted (callers that already know there are no missing skills). */
  matchPercentage?: number;
  /** Optional: called when the user clicks the learning CTA. */
  onStartLearning?: (skills: string[]) => void;
}

// "All requirements matched" is only honest at a high score (item #2).
const ALL_MATCHED_MIN = 90;

function buildInsight(matchedCount: number, missingCount: number, pct: number): string {
  if (missingCount === 0) {
    if (matchedCount === 0) return 'No skill data yet — refresh recommendations';
    return pct >= ALL_MATCHED_MIN
      ? 'Strong match — you\'re ready to apply 🎯'
      : 'You partially match this role';
  }
  if (missingCount === 1) return 'Strong match — just 1 skill to build';
  return `${matchedCount} skills matched · ${missingCount} still to build`;
}

export function SkillGapSection({
  matchedSkills,
  missingSkills,
  matchPercentage,
  onStartLearning,
}: SkillGapSectionProps) {
  const matchedCount = matchedSkills.length;
  const missingCount = missingSkills.length;
  const isQuickWin   = missingCount >= 1 && missingCount <= 3;
  // When no percentage is provided, assume the caller already vetted this view;
  // don't block the positive message purely on a missing prop.
  const pct = matchPercentage ?? ALL_MATCHED_MIN;
  const strongMatch = matchedCount > 0 && pct >= ALL_MATCHED_MIN;

  return (
    <div className="mt-2 p-3 bg-white/5 rounded-xl text-xs space-y-3">
      {/* Summary line */}
      <p className="text-white/80 font-medium">{buildInsight(matchedCount, missingCount, pct)}</p>

      {/* Why you match — ALL matched skills, verbatim */}
      {matchedCount > 0 && (
        <div>
          <p className="text-green-400 font-semibold mb-1.5 flex items-center gap-1">
            <span>✅</span> Why you match
          </p>
          <div className="flex flex-wrap gap-1">
            {matchedSkills.map((skill, i) => (
              <span
                key={`m-${i}`}
                className="px-2 py-0.5 bg-green-500/20 text-green-300 rounded capitalize"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Why you don't — ALL missing skills, verbatim */}
      {missingCount === 0 ? (
        matchedCount === 0 ? (
          <p className="text-white/40">No skill data yet — refresh recommendations.</p>
        ) : strongMatch ? (
          <p className="text-green-300">All required skills matched 🎯</p>
        ) : (
          <p className="text-white/60">You partially match this role.</p>
        )
      ) : (
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <p className="text-orange-400 font-semibold flex items-center gap-1">
              <span>⚠️</span> Why you don't fully match
            </p>
            {isQuickWin && (
              <span className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-[10px] uppercase tracking-wide">
                Quick wins
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {missingSkills.map((skill, i) => (
              <span
                key={`x-${i}`}
                className="px-2 py-0.5 bg-orange-500/20 text-orange-300 rounded capitalize"
              >
                {skill}
              </span>
            ))}
          </div>

          <button
            onClick={() => onStartLearning?.(missingSkills)}
            className="mt-2 text-blue-400 hover:text-blue-300 underline underline-offset-2"
          >
            Start learning →
          </button>
        </div>
      )}
    </div>
  );
}
