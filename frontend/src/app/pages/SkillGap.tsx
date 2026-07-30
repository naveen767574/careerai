import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { internshipService } from '../lib/services';
import { GlassCard } from '../components/GlassCard';
import { SkillGapSection } from '../components/SkillGapSection';
import { motion } from 'motion/react';
import { ArrowLeft, Target, AlertCircle, RefreshCw, TrendingUp, Zap, Layers, Compass, Lightbulb } from 'lucide-react';

type Simulation = { skill: string; simulated_pct: number; delta_pct: number; new_label: string };

type MatchInsights = {
  role_type: string;
  role_label: string;
  stack_type: string;
  stack_label: string;
  match_percentage: number;
  matched_skills: string[];
  missing_skills: { core: string[]; secondary: string[]; optional: string[] };
  explanation: string;
  match_reasons: string[];
  recommendation: string;
  top_missing_skill: string;
  skill_impacts: { skill: string; impact: number }[];
};

/**
 * SkillGap page — full-page view of matched/missing skills for one internship.
 *
 * STRICT CONSISTENCY: the headline match_percentage comes straight from
 * GET /api/internships/{id}/skill-gap (the stored composite score — the SAME
 * number the Internships card shows). The role-aware enrichment (role/stack
 * badges, core/secondary/optional gaps, mentor guidance) comes from
 * GET /api/internships/{id}/match-insights, which passes that same score
 * through verbatim — it never forks a second number.
 */

function labelColor(pct: number): string {
  if (pct >= 80) return 'text-green-400';
  if (pct >= 70) return 'text-blue-400';
  if (pct >= 60) return 'text-cyan-400';
  return 'text-purple-400';
}

// Category presentation: core = red/critical, secondary = amber, optional = grey.
const GAP_CATEGORIES: { key: 'core' | 'secondary' | 'optional'; label: string; chip: string; dot: string }[] = [
  { key: 'core',      label: 'Core (must-have)',   chip: 'bg-red-500/15 text-red-300 border border-red-500/25',       dot: 'bg-red-400' },
  { key: 'secondary', label: 'Secondary',          chip: 'bg-amber-500/15 text-amber-300 border border-amber-500/25', dot: 'bg-amber-400' },
  { key: 'optional',  label: 'Nice-to-have',       chip: 'bg-white/10 text-white/60 border border-white/15',          dot: 'bg-white/40' },
];

export function SkillGap() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [gap, setGap] = useState<{
    matched_skills: string[];
    missing_skills: string[];
    match_percentage: number;
  } | null>(null);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [insights, setInsights] = useState<MatchInsights | null>(null);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      // Fetch skill gap + internship detail in parallel; enrichers after gap loads.
      const [gapData, detail] = await Promise.all([
        internshipService.getSkillGap(id),
        internshipService.getById(Number(id)).catch(() => null),
      ]);
      setGap(gapData);
      const intern = detail?.internship || detail || {};
      setTitle(intern.title || 'Internship');
      setCompany(intern.company || '');

      // Simulations + insights are best-effort — never block the main view on them.
      internshipService.getSkillSimulations(id)
        .then(data => setSimulations(data.simulations || []))
        .catch(() => setSimulations([]));
      internshipService.getMatchInsights(id)
        .then(data => setInsights(data))
        .catch(() => setInsights(null));
    } catch (e: any) {
      const status = e?.response?.status;
      setError(
        status === 404
          ? 'No skill-gap data yet. Open Internships and click Refresh to generate recommendations first.'
          : 'Could not load skill gap. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const matched = gap?.matched_skills ?? [];
  const missing = gap?.missing_skills ?? [];
  const pct = Math.floor(gap?.match_percentage ?? 0);

  const totalCategorized = insights
    ? insights.missing_skills.core.length +
      insights.missing_skills.secondary.length +
      insights.missing_skills.optional.length
    : 0;

  // Single source of truth for "everything matched". Per the fix (item #2):
  //   - ALL of core/secondary/optional must be empty (totalCategorized === 0),
  //   - there must be at least one matched skill,
  //   - AND the score must be genuinely high (>= 90) - a low score with no
  //     listed gaps is a thin-data case, NOT a perfect match.
  //   - Otherwise fall back to the flat skill-gap arrays with the same guards.
  const ALL_MATCHED_MIN = 90;
  const allMatched = insights
    ? totalCategorized === 0 && insights.matched_skills.length > 0 && pct >= ALL_MATCHED_MIN
    : missing.length === 0 && matched.length > 0 && pct >= ALL_MATCHED_MIN;

  // "You partially match" vs "meet all core requirements" (item #3): only claim
  // core requirements are met at a Strong-match score (>= 70).
  const STRONG_MIN = 70;
  const meetsCore = pct >= STRONG_MIN;

  // Do we have ANY missing skill to show? (drives the "focus on these" line)
  const hasMissing = insights ? totalCategorized > 0 : missing.length > 0;

  // Item #12: don't show the same word twice as both role and stack badge
  // (e.g. role "Data Science" + stack "Data Science").
  const showStackBadge =
    !!insights?.stack_label &&
    insights.stack_label.trim().toLowerCase() !== insights.role_label.trim().toLowerCase();

  return (
    <div className="space-y-8">
      {/* Back link */}
      <button
        onClick={() => navigate('/internships')}
        className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Internships
      </button>

      {loading && (
        <div className="text-center py-16 text-white/60">Loading skill gap...</div>
      )}

      {!loading && error && (
        <GlassCard className="flex items-center justify-between gap-4 border border-red-500/30">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
          <button
            onClick={load}
            className="text-sm px-3 py-1 rounded-lg bg-red-500/20 text-red-200 hover:bg-red-500/30 transition-colors flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </GlassCard>
      )}

      {!loading && !error && gap && (
        <>
          {/* Header: title + role/stack badges + match_percentage */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-6 h-6 text-blue-400" />
                <h1 className="text-3xl font-bold gradient-text">Skill Gap</h1>
              </div>
              <p className="text-lg font-semibold">{title}</p>
              {company && <p className="text-sm text-white/60">{company}</p>}

              {/* Role + stack badges (only when insights loaded) */}
              {insights && (
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                    <Compass className="w-3.5 h-3.5" />
                    {insights.role_label}
                  </span>
                  {showStackBadge && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/25">
                      <Layers className="w-3.5 h-3.5" />
                      {insights.stack_label}
                    </span>
                  )}
                </div>
              )}
            </div>
            <GlassCard className="text-center min-w-[120px]">
              <p className={`text-4xl font-bold ${labelColor(pct)}`}>{pct}%</p>
              <p className="text-xs text-white/60 mt-1">Match</p>
            </GlassCard>
          </div>

          {/* Mentor guidance: why-you-match + biggest gap + recommendation */}
          {insights && (insights.explanation || insights.recommendation) && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard className="p-6 space-y-4">
                {insights.explanation && (
                  <div className="flex items-start gap-3">
                    <Target className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
                    <p className="text-sm text-white/80 leading-relaxed">{insights.explanation}</p>
                  </div>
                )}

                {/* Per-skill "why you match" bullets — each maps to ONE real
                    matched skill and explains HOW it helps in this role. */}
                {insights.match_reasons && insights.match_reasons.length > 0 && (
                  <ul className="space-y-1.5 pl-8">
                    {insights.match_reasons.map((reason, i) => (
                      <li key={`reason-${i}`} className="flex items-start gap-2 text-sm text-white/75 leading-relaxed">
                        <span className="text-green-400 shrink-0 mt-0.5">•</span>
                        <span>{reason}</span>
                      </li>
                    ))}
                  </ul>
                )}

                {insights.top_missing_skill && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-white/50">Biggest gap:</span>
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-300 border border-red-500/25">
                      {insights.top_missing_skill}
                    </span>
                  </div>
                )}

                {insights.recommendation && (
                  <div className="flex items-start gap-3 pt-1 border-t border-white/10">
                    <Lightbulb className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-sm text-amber-100/90 leading-relaxed">{insights.recommendation}</p>
                  </div>
                )}
              </GlassCard>
            </motion.div>
          )}

          {/* Insight line (fallback / summary). Item #3: only claim core
              requirements are met at a genuine match; below that, say "partial". */}
          <p className="text-sm text-white/70">
            {allMatched
              ? 'You meet all core requirements 🎯'
              : hasMissing
                ? (meetsCore
                    ? 'Focus on these skills to sharpen an already-strong match'
                    : 'You partially match this role — focus on these skills to improve')
                : 'Refresh recommendations to see your skill gap'}
          </p>

          {/* Categorized missing skills (core / secondary / optional) when insights
              are available — otherwise fall back to the flat SkillGapSection. */}
          {insights && totalCategorized > 0 ? (
            <GlassCard className="p-6 space-y-5">
              {/* Matched skills — verbatim */}
              {insights.matched_skills.length > 0 && (
                <div>
                  <p className="text-green-400 font-semibold mb-2 flex items-center gap-1.5 text-sm">
                    <span>✅</span> Why you match
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {insights.matched_skills.map((skill, i) => (
                      <span key={`ins-m-${i}`} className="px-2 py-0.5 bg-green-500/20 text-green-300 rounded text-xs">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing skills grouped by importance */}
              <div className="space-y-3">
                <p className="text-orange-400 font-semibold flex items-center gap-1.5 text-sm">
                  <span>⚠️</span> Skills to build — by priority
                </p>
                {GAP_CATEGORIES.map(cat => {
                  const items = insights.missing_skills[cat.key];
                  if (!items || items.length === 0) return null;
                  return (
                    <div key={cat.key}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className={`w-2 h-2 rounded-full ${cat.dot}`} />
                        <span className="text-xs text-white/60">{cat.label}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {items.map((skill, i) => (
                          <span key={`${cat.key}-${i}`} className={`px-2 py-0.5 rounded text-xs ${cat.chip}`}>
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          ) : (
            /* Matched + Missing sections — reuse the existing SkillGapSection.
               Values passed VERBATIM from the API; the component does not
               recompute anything, only renders and counts. */
            <GlassCard>
              <SkillGapSection
                matchedSkills={matched}
                missingSkills={missing}
                matchPercentage={pct}
                onStartLearning={() => alert('Learning resources coming soon!')}
              />
            </GlassCard>
          )}

          {/* Weighted skill impact — compact fallback shown ONLY when the richer
              What-if simulations panel below isn't available (both use the same
              delta math, so we never render both and duplicate the numbers). */}
          {insights && simulations.length === 0 && insights.skill_impacts.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <GlassCard className="p-6">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="w-5 h-5 text-green-400" />
                  <h2 className="text-lg font-semibold text-white">Highest-impact skills to learn</h2>
                </div>
                <p className="text-xs text-white/50 mb-4">
                  Estimated match boost from each missing skill — biggest first.
                </p>
                <div className="space-y-2">
                  {insights.skill_impacts.map((imp) => (
                    <div key={imp.skill} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 px-3.5 py-2.5">
                      <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-white/10 text-white/90">
                        {imp.skill}
                      </span>
                      <span className="text-sm font-bold text-green-400">+{imp.impact.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* What-if simulation panel */}
          {simulations.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <GlassCard className="p-6">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-5 h-5 text-yellow-400" />
                  <h2 className="text-lg font-semibold text-white">What if you learned…</h2>
                </div>
                <p className="text-xs text-white/50 mb-5">
                  Projected match boost for each missing skill — sorted by highest impact first.
                </p>

                <div className="space-y-3">
                  {simulations.map((sim) => {
                    const simFloor = Math.floor(sim.simulated_pct);
                    const deltaStr = `+${sim.delta_pct.toFixed(1)}%`;
                    const barCurrent = Math.min(100, pct);
                    const barSimulated = Math.min(100, simFloor);
                    const crosses70 = pct < 70 && sim.simulated_pct >= 70;
                    const crosses80 = pct < 80 && sim.simulated_pct >= 80;
                    const milestone = crosses80 ? 'Excellent Match' : crosses70 ? 'Strong Match' : null;

                    return (
                      <div key={sim.skill} className="rounded-xl border border-white/10 p-3.5 space-y-2.5">
                        {/* Header row */}
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-white/10 text-white/90 shrink-0">
                              {sim.skill}
                            </span>
                            {milestone && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-yellow-500/20 text-yellow-300 shrink-0">
                                Unlocks {milestone}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <TrendingUp className="w-3.5 h-3.5 text-green-400" />
                            <span className="text-sm font-bold text-green-400">{deltaStr}</span>
                          </div>
                        </div>

                        {/* Progress bar */}
                        <div className="relative h-2 rounded-full bg-white/10 overflow-hidden">
                          {/* Current fill */}
                          <div
                            className="absolute left-0 top-0 h-full rounded-full bg-blue-500/60"
                            style={{ width: `${barCurrent}%` }}
                          />
                          {/* Simulated extension */}
                          <div
                            className="absolute top-0 h-full rounded-full bg-green-400/80"
                            style={{ left: `${barCurrent}%`, width: `${Math.max(0, barSimulated - barCurrent)}%` }}
                          />
                        </div>

                        {/* Labels */}
                        <div className="flex justify-between text-[10px] text-white/50">
                          <span>Now: {pct}%</span>
                          <span className="text-green-300 font-medium">
                            With {sim.skill}: {simFloor}% — {sim.new_label}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* Motivational footer — only on a genuine all-matched (missing==0 AND
              score >= 90). Item #15: strong-match, ready-to-apply copy. */}
          {allMatched && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center text-green-300"
            >
              Strong match — you're ready to apply 🎯
            </motion.div>
          )}
        </>
      )}
    </div>
  );
}
