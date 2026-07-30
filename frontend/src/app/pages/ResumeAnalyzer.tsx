import { useEffect, useRef, useState } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion, AnimatePresence } from 'motion/react';
import {
  Upload, FileText, CheckCircle2, AlertCircle,
  TrendingUp, Target, Zap, RefreshCw, Sparkles,
  BookOpen, Compass, ChevronDown, ChevronUp, Brain,
  Gauge, Rocket, Briefcase, Lightbulb,
} from 'lucide-react';
import { resumeService } from '../lib/services';
import api from '../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DetailedSkill = {
  skill: string;
  priority: 'High' | 'Medium' | 'Low';
  why_it_matters: string;
  how_to_learn: string[];
  project_idea: string;
};

type CareerAnalysis = {
  target_role: string;
  confidence: number;
  reasoning: string;
  match_score: number;
  level: string;
  role_analysis: string;
  readiness_score: number;
  readiness_summary: string;
  present_skills: string[];
  missing_skills: string[];
  missing_skills_detailed: DetailedSkill[];
  missing_experience: string[];
  recommended_projects: string[];
  action_plan: { day: string; focus: string }[];
  career_guidance: string;
  resume_improvements: string[];
  _error?: boolean;
};

type OptimizeResult = {
  improvements: string[];
  missing_keywords: string[];
  improved_bullets: { original: string; improved: string }[];
  skill_suggestions: { skill: string; suggestion: string }[];
};

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const color = score >= 70 ? '#22c55e' : score >= 45 ? '#eab308' : '#ef4444';
  const r = (size / 2) - 6;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={8} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={8}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 0.8s ease' }}
      />
      <text
        x="50%" y="50%" dominantBaseline="middle" textAnchor="middle"
        fill={color} fontSize={size * 0.22} fontWeight="bold"
      >
        {score}%
      </text>
    </svg>
  );
}

function scoreLabel(score: number): { label: string; color: string } {
  if (score >= 70) return { label: 'Strong', color: 'text-green-400' };
  if (score >= 45) return { label: 'Moderate', color: 'text-yellow-400' };
  return { label: 'Weak', color: 'text-red-400' };
}

function confidenceBar(pct: number) {
  const color = pct >= 70 ? 'bg-green-400' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%`, transition: 'width 0.6s ease' }} />
      </div>
      <span className="text-xs text-white/50">{pct}%</span>
    </div>
  );
}

const PRIORITY_STYLES: Record<DetailedSkill['priority'], { chip: string; dot: string }> = {
  High:   { chip: 'bg-red-500/20 text-red-300 border border-red-500/30',       dot: 'bg-red-400' },
  Medium: { chip: 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30', dot: 'bg-yellow-400' },
  Low:    { chip: 'bg-white/10 text-white/60 border border-white/15',           dot: 'bg-white/40' },
};

function PriorityBadge({ priority }: { priority: DetailedSkill['priority'] }) {
  const s = PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.Medium;
  return (
    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide ${s.chip}`}>
      {priority}
    </span>
  );
}

function readinessTone(pct: number): { bar: string; text: string } {
  if (pct >= 70) return { bar: 'from-green-500 to-emerald-400', text: 'text-green-300' };
  if (pct >= 45) return { bar: 'from-yellow-500 to-amber-400',  text: 'text-yellow-300' };
  return { bar: 'from-red-500 to-orange-400', text: 'text-red-300' };
}

function SkillCard({ item, idx }: { item: DetailedSkill; idx: number }) {
  const [open, setOpen] = useState(idx === 0); // first card open by default
  const accent = PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.Medium;
  return (
    <div className="rounded-xl border border-white/10 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-white/8 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${accent.dot}`} />
          <span className="font-semibold text-sm text-white text-left truncate">{item.skill}</span>
          <PriorityBadge priority={item.priority} />
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-white/40 shrink-0" /> : <ChevronDown className="w-4 h-4 text-white/40 shrink-0" />}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 space-y-4 border-t border-white/10">
              {item.why_it_matters && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Why it matters</p>
                  <p className="text-sm text-gray-300 leading-relaxed">{item.why_it_matters}</p>
                </div>
              )}

              {item.how_to_learn.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-white/40 mb-2">How to learn</p>
                  <ol className="space-y-1.5">
                    {item.how_to_learn.map((step, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-300">
                        <span className="text-blue-400 shrink-0 font-semibold">{i + 1}.</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {item.project_idea && (
                <div className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                  <p className="text-[10px] uppercase tracking-wide text-violet-400 mb-1">Project idea</p>
                  <p className="text-sm text-violet-200 leading-relaxed">{item.project_idea}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ResumeAnalyzer() {
  const [dragOver, setDragOver]       = useState(false);
  const [uploaded, setUploaded]       = useState(false);
  const [uploading, setUploading]     = useState(false);
  const [analyzing, setAnalyzing]     = useState(false);
  const [fileName, setFileName]       = useState('');
  const [error, setError]             = useState('');
  const [resumeData, setResumeData]   = useState<any>(null);

  // Career Intelligence (new)
  const [careerLoading, setCareerLoading]   = useState(false);
  const [careerResult, setCareerResult]     = useState<CareerAnalysis | null>(null);
  const [careerError, setCareerError]       = useState(false);

  // Legacy Resume Improver
  const [optimizing, setOptimizing]     = useState(false);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);
  const [optimizeError, setOptimizeError]   = useState(false);

  const careerRef  = useRef<HTMLDivElement>(null);
  const optimizeRef = useRef<HTMLDivElement>(null);

  // ---- Career Intelligence handler ----------------------------------------
  const handleCareerAnalysis = async () => {
    if (careerLoading) return;
    setCareerLoading(true);
    setCareerError(false);
    setCareerResult(null);
    try {
      const data = await resumeService.careerAnalysis();
      setCareerResult(data);
      setTimeout(() => careerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch {
      setCareerError(true);
    } finally {
      setCareerLoading(false);
    }
  };

  // ---- Legacy optimiser handler -------------------------------------------
  const handleOptimize = async () => {
    if (optimizing) return;
    setOptimizing(true);
    setOptimizeError(false);
    try {
      const data = await resumeService.optimize();
      setOptimizeResult(data);
      setTimeout(() => optimizeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch {
      setOptimizeError(true);
    } finally {
      setOptimizing(false);
    }
  };

  // ---- On-mount: load existing resume -------------------------------------
  useEffect(() => { loadExistingResume(); }, []);

  const loadExistingResume = async () => {
    try {
      const data = await resumeService.getMyResume();
      if (data) {
        setFileName(data.file_name || 'resume');
        setUploaded(true);
        try {
          const analysis = await resumeService.getAnalysis(data.id);
          setResumeData(analysis);
        } catch {
          setResumeData(data);
        }
      }
    } catch { /* no resume yet */ }
  };

  const handleFile = async (file: File) => {
    if (!file) return;
    setError('');
    setUploading(true);
    setFileName(file.name);
    // Reset results on new upload
    setCareerResult(null);
    setOptimizeResult(null);
    try {
      await resumeService.upload(file);
      setUploaded(true);
      setAnalyzing(true);
      setTimeout(async () => {
        try {
          const resume   = await resumeService.getMyResume();
          const analysis = await resumeService.getAnalysis(resume.id);
          setResumeData(analysis);
        } catch { /* fallback */ }
        setAnalyzing(false);
        try { await api.post('/recommendations/refresh'); } catch { }
        try { api.post('/agent/trigger', { trigger: 'resume_upload' }).catch(() => {}); } catch { }
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
      setUploading(false);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleClick  = () => (document.getElementById('resume-file-input') as HTMLInputElement)?.click();
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const score    = resumeData?.ats_score || resumeData?.score || 0;
  const skills   = resumeData?.extracted_skills || resumeData?.analysis?.skills || [];

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
          Resume Analyzer
        </h1>
        <p className="text-gray-400 mt-1">Upload your resume for AI-powered career insights</p>
      </motion.div>

      {error && (
        <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl p-4">{error}</div>
      )}

      <input id="resume-file-input" type="file" accept=".pdf,.docx" style={{ display: 'none' }} onChange={handleFileInput} />

      {/* Upload dropzone */}
      {!uploaded ? (
        <GlassCard
          className={`border-2 border-dashed transition-all duration-300 cursor-pointer p-12 text-center ${
            dragOver ? 'border-blue-400 bg-blue-500/10' : 'border-gray-600'
          }`}
          onDragOver={(e: React.DragEvent) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <Upload className="w-16 h-16 text-blue-400 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">
            {uploading ? 'Uploading...' : 'Drop your resume here'}
          </h3>
          <p className="text-gray-400">Supports PDF and DOCX files</p>
        </GlassCard>
      ) : (
        <div className="space-y-5">

          {/* File status bar */}
          <GlassCard className="p-6 flex items-center gap-4">
            <FileText className="w-10 h-10 text-blue-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-white font-semibold truncate">{fileName}</p>
              <p className="text-gray-400 text-sm">
                {analyzing ? 'Analyzing your resume...' : 'Analyzed successfully'}
              </p>
            </div>
            {analyzing
              ? <RefreshCw className="w-6 h-6 text-blue-400 animate-spin shrink-0" />
              : <CheckCircle2 className="w-6 h-6 text-green-400 shrink-0" />}
            <button onClick={handleClick} className="ml-2 text-xs text-blue-400 hover:text-blue-300 underline shrink-0">
              Replace
            </button>
          </GlassCard>

          {/* Quick stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: TrendingUp, label: 'Resume Score',  value: analyzing ? '…' : `${score}/100`,               color: 'text-blue-400' },
              { icon: Target,     label: 'Skills Found',  value: analyzing ? '…' : `${skills.length} skills`,    color: 'text-violet-400' },
              { icon: Zap,        label: 'ATS Ready',     value: analyzing ? '…' : score > 60 ? 'Yes' : 'Needs Work', color: 'text-cyan-400' },
            ].map(stat => (
              <GlassCard key={stat.label} className="p-6 text-center">
                <stat.icon className={`w-8 h-8 ${stat.color} mx-auto mb-2`} />
                <p className="text-2xl font-bold text-white">{stat.value}</p>
                <p className="text-gray-400 text-sm">{stat.label}</p>
              </GlassCard>
            ))}
          </div>

          {/* Detected Skills */}
          {skills.length > 0 && (
            <GlassCard className="p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-400" />
                Detected Skills
              </h3>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill: any, idx: number) => (
                  <span key={idx} className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-lg text-xs">
                    {typeof skill === 'string' ? skill : skill.name}
                  </span>
                ))}
              </div>
            </GlassCard>
          )}

          {/* ================================================================
              PRIMARY CTA — Career Intelligence
              ================================================================ */}
          <button
            onClick={handleCareerAnalysis}
            disabled={careerLoading || analyzing}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-blue-600 rounded-xl py-4 font-semibold text-base disabled:opacity-60 disabled:cursor-not-allowed hover:from-violet-500 hover:to-blue-500 transition-all"
          >
            {careerLoading ? (
              <><RefreshCw className="w-5 h-5 animate-spin" />Analyzing your career profile...</>
            ) : (
              <><Brain className="w-5 h-5" />Analyse My Career Profile</>
            )}
          </button>

          {careerError && !careerLoading && (
            <GlassCard className="p-4 border border-red-500/30 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                <p className="text-sm text-red-300">Career analysis failed. Please try again.</p>
              </div>
              <button onClick={handleCareerAnalysis} className="text-sm px-3 py-1 rounded-lg bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center gap-1">
                <RefreshCw className="w-3.5 h-3.5" />Retry
              </button>
            </GlassCard>
          )}

          {/* ================================================================
              CAREER INTELLIGENCE RESULTS
              ================================================================ */}
          {careerResult && !careerLoading && (
            <div ref={careerRef} className="space-y-5">

              {careerResult._error && (
                <div className="text-yellow-300 text-sm bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
                  Career analysis returned partial results. Some sections may be empty — try again later.
                </div>
              )}

              {/* 1. Target Role */}
              <GlassCard className="p-6">
                <div className="flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Target className="w-5 h-5 text-blue-400 shrink-0" />
                      <h2 className="text-lg font-semibold text-white">Target Role</h2>
                    </div>
                    <p className="text-2xl font-bold text-blue-300 mt-1">{careerResult.target_role}</p>
                    <div className="mt-2">
                      <span className="text-xs text-white/50">Confidence</span>
                      {confidenceBar(careerResult.confidence)}
                    </div>
                    {careerResult.reasoning && (
                      <p className="mt-3 text-sm text-white/70 leading-relaxed italic">"{careerResult.reasoning}"</p>
                    )}
                  </div>
                  <div className="shrink-0">
                    <div className="text-center">
                      <p className="text-xs text-white/40 mb-1 uppercase tracking-wide">Level</p>
                      <span className="px-3 py-1.5 rounded-full text-sm font-semibold bg-blue-500/20 text-blue-300">
                        {careerResult.level}
                      </span>
                    </div>
                  </div>
                </div>
              </GlassCard>

              {/* 2. Match Score */}
              {careerResult.match_score > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-5 h-5 text-green-400" />
                    <h2 className="text-lg font-semibold text-white">Role Match Score</h2>
                  </div>
                  <div className="flex items-center gap-6">
                    <ScoreRing score={careerResult.match_score} size={90} />
                    <div className="flex-1 min-w-0">
                      {(() => { const { label, color } = scoreLabel(careerResult.match_score); return (
                        <p className={`text-xl font-bold mb-1 ${color}`}>{label} Match</p>
                      ); })()}
                      {careerResult.role_analysis && (
                        <p className="text-sm text-white/70 leading-relaxed">{careerResult.role_analysis}</p>
                      )}
                    </div>
                  </div>
                </GlassCard>
              )}

              {/* 2b. Job Readiness Score */}
              {careerResult.readiness_score > 0 && (() => {
                const tone = readinessTone(careerResult.readiness_score);
                return (
                  <GlassCard className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <Gauge className="w-5 h-5 text-cyan-400" />
                      <h2 className="text-lg font-semibold text-white">Job Readiness</h2>
                    </div>
                    <p className="text-sm text-white/70 mb-2">
                      You are{' '}
                      <span className={`font-bold ${tone.text}`}>{careerResult.readiness_score}% ready</span>{' '}
                      for <span className="font-semibold text-white">{careerResult.target_role}</span> roles.
                    </p>
                    <div className="h-3 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${tone.bar}`}
                        style={{ width: `${careerResult.readiness_score}%`, transition: 'width 0.8s ease' }}
                      />
                    </div>
                    {careerResult.readiness_summary && (
                      <p className="mt-3 text-sm text-white/60 leading-relaxed">{careerResult.readiness_summary}</p>
                    )}
                  </GlassCard>
                );
              })()}

              {/* 3. Present Skills */}
              {careerResult.present_skills.length > 0 && (
                <GlassCard className="p-6">
                  <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    Skills You Have
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {careerResult.present_skills.map((s, i) => (
                      <span key={i} className="px-3 py-1 rounded-lg text-xs bg-green-500/20 text-green-300">
                        {s}
                      </span>
                    ))}
                  </div>
                </GlassCard>
              )}

              {/* 4. Missing Skills chips (quick overview) */}
              {careerResult.missing_skills.length > 0 && (
                <GlassCard className="p-6">
                  <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-orange-400" />
                    Skills You Need to Reach This Role
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {careerResult.missing_skills.map((s, i) => (
                      <span key={i} className="px-3 py-1 rounded-lg text-xs bg-orange-500/20 text-orange-300">
                        {s}
                      </span>
                    ))}
                  </div>
                </GlassCard>
              )}

              {/* 5. How to Build These Skills (detailed accordion) */}
              {careerResult.missing_skills_detailed.length > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-5">
                    <BookOpen className="w-5 h-5 text-cyan-400" />
                    <h2 className="text-lg font-semibold text-white">How to Build These Skills</h2>
                  </div>
                  <div className="space-y-3">
                    {careerResult.missing_skills_detailed.map((item, idx) => (
                      <SkillCard key={item.skill} item={item} idx={idx} />
                    ))}
                  </div>
                </GlassCard>
              )}

              {/* 5b. Missing Experience */}
              {careerResult.missing_experience.length > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Briefcase className="w-5 h-5 text-rose-400" />
                    <h2 className="text-lg font-semibold text-white">Experience Gaps</h2>
                  </div>
                  <ul className="space-y-2.5">
                    {careerResult.missing_experience.map((exp, i) => (
                      <li key={i} className="flex gap-2.5 text-sm text-gray-300 leading-relaxed">
                        <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        <span>{exp}</span>
                      </li>
                    ))}
                  </ul>
                </GlassCard>
              )}

              {/* 5c. Recommended Projects */}
              {careerResult.recommended_projects.length > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="w-5 h-5 text-amber-400" />
                    <h2 className="text-lg font-semibold text-white">Projects to Build</h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {careerResult.recommended_projects.map((proj, i) => (
                      <div key={i} className="flex gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                        <span className="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-300 text-xs font-bold flex items-center justify-center shrink-0">
                          {i + 1}
                        </span>
                        <p className="text-sm text-amber-100 leading-snug">{proj}</p>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              )}

              {/* 5d. 7-Day Action Plan */}
              {careerResult.action_plan.length > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-1">
                    <Rocket className="w-5 h-5 text-violet-400" />
                    <h2 className="text-lg font-semibold text-white">Your Next 7 Days</h2>
                  </div>
                  <p className="text-xs text-white/40 mb-5">A realistic kickstart plan to close your top gaps.</p>
                  <ol className="relative border-l border-white/10 ml-2 space-y-5">
                    {careerResult.action_plan.map((step, i) => (
                      <li key={i} className="ml-5">
                        <span className="absolute -left-[7px] w-3.5 h-3.5 rounded-full bg-violet-500 border-2 border-[#0b0b12]" />
                        <p className="text-xs font-semibold uppercase tracking-wide text-violet-300">{step.day}</p>
                        <p className="text-sm text-white/80 leading-relaxed mt-0.5">{step.focus}</p>
                      </li>
                    ))}
                  </ol>
                </GlassCard>
              )}

              {/* 6. Career Guidance */}
              {careerResult.career_guidance && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Compass className="w-5 h-5 text-yellow-400" />
                    <h2 className="text-lg font-semibold text-white">Career Guidance</h2>
                  </div>
                  <p className="text-sm text-white/80 leading-relaxed whitespace-pre-line">
                    {careerResult.career_guidance}
                  </p>
                </GlassCard>
              )}

              {/* 7. Resume Improvements */}
              {careerResult.resume_improvements.length > 0 && (
                <GlassCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Sparkles className="w-5 h-5 text-violet-400" />
                    <h2 className="text-lg font-semibold text-white">Resume Improvements</h2>
                  </div>
                  <ul className="space-y-2.5">
                    {careerResult.resume_improvements.map((s, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-300 leading-relaxed">
                        <span className="text-violet-400 shrink-0 mt-0.5">•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </GlassCard>
              )}

            </div>
          )}

          {/* ================================================================
              DIVIDER
              ================================================================ */}
          <div className="flex items-center gap-4 py-2">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-white/30 uppercase tracking-widest">Bullet Rewriter</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* ================================================================
              LEGACY: Improve Resume with AI
              ================================================================ */}
          <button
            onClick={handleOptimize}
            disabled={optimizing || analyzing}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-500 to-violet-500 rounded-xl py-3 font-medium disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {optimizing ? (
              <><RefreshCw className="w-4 h-4 animate-spin" />Analyzing your resume...</>
            ) : (
              <><Sparkles className="w-4 h-4" />Improve Resume with AI</>
            )}
          </button>

          {optimizeError && !optimizing && (
            <GlassCard className="p-4 border border-red-500/30 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                <p className="text-sm text-red-300">Couldn't improve your resume. Please try again.</p>
              </div>
              <button onClick={handleOptimize} className="text-sm px-3 py-1 rounded-lg bg-red-500/20 text-red-200 hover:bg-red-500/30 flex items-center gap-1">
                <RefreshCw className="w-3.5 h-3.5" />Retry
              </button>
            </GlassCard>
          )}

          {optimizeResult && !optimizing && (
            <div ref={optimizeRef} className="space-y-4">

              {/* A) Suggested Improvements */}
              <GlassCard className="p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-400" />
                  Suggested Improvements
                </h3>
                {(optimizeResult.improvements?.length ?? 0) > 0 ? (
                  <ul className="space-y-2 text-gray-300">
                    {optimizeResult.improvements.map((s, idx) => (
                      <li key={idx} className="flex gap-2 text-sm leading-relaxed">
                        <span className="text-blue-400 shrink-0">•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-400 text-sm">No improvement suggestions returned.</p>
                )}
              </GlassCard>

              {/* D) Improved Bullet Examples */}
              <GlassCard className="p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-violet-400" />
                  Improved Bullet Examples
                </h3>
                {(optimizeResult.improved_bullets?.length ?? 0) > 0 ? (
                  <div className="space-y-4">
                    {optimizeResult.improved_bullets.map((b, idx) => (
                      <div key={idx} className="rounded-xl border border-white/10 overflow-hidden">
                        <div className="p-3 bg-white/5">
                          <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">Before</p>
                          <p className="text-sm text-gray-400">{b.original}</p>
                        </div>
                        <div className="p-3 bg-green-500/10 border-t border-green-500/20">
                          <p className="text-[10px] uppercase tracking-wide text-green-400 mb-1">After</p>
                          <p className="text-sm text-green-200 flex gap-2">
                            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                            <span>{b.improved}</span>
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm">
                    No bullet rewrites available. Add experience or project descriptions to your resume for AI rewrites.
                  </p>
                )}
              </GlassCard>

            </div>
          )}
        </div>
      )}
    </div>
  );
}
