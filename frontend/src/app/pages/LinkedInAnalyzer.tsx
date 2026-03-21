import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  Linkedin, TrendingUp, Users, FileText,
  CheckCircle2, AlertCircle, Zap, Target, RefreshCw,
} from 'lucide-react';
import { linkedinService } from '../lib/services';

export function LinkedInAnalyzer() {
  const [analyzed, setAnalyzed] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [profileText, setProfileText] = useState('');
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profileScore, setProfileScore] = useState({
    overall: 0, headline: 0, summary: 0,
    experience: 0, skills: 0, engagement: 0,
  });
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [improvements, setImprovements] = useState<any[]>([]);
  const [optimizedSummary, setOptimizedSummary] = useState('');
  const [activeAction, setActiveAction] = useState<number | null>(null);

  useEffect(() => {
    setError('');
    // Don't auto-load previous report - let user analyze fresh
  }, []);

  const loadLatestReport = async () => {
    setError('');
    try {
      const data = await linkedinService.getLatest();
      if (data && data.profile_score) {
        applyReportData(data);
        setAnalyzed(true);
      }
    } catch {
      // No previous report - that's fine
    }
  };

  const handleAnalyze = async () => {
    setError('');
    if (!profileText || profileText.trim().length < 10) {
      setError('Please paste your LinkedIn profile text first');
      return;
    }
    setAnalyzing(true);
    try {
      const lines = profileText.split('\n').filter((l: string) => l.trim().length > 0);
      const headline = lines[0]?.trim().substring(0, 100) || 'Professional';
      const payload = {
        headline: headline,
        about: profileText.substring(0, 3000),
        experience: ['See profile for details'],
        skills: ['See profile for details'],
        projects: [],
        education: 'See profile for details',
        has_photo: true,
      };
      console.log('Sending payload:', JSON.stringify(payload).substring(0, 200));
      const data = await linkedinService.analyze(payload);
      applyReportData(data);
      setAnalyzed(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Analysis failed. Please try again.');
    }
    setAnalyzing(false);
  };

  const applyReportData = (data: any) => {
    setSessionId(data.session_id);
    
    // Fix: backend returns profile_score not overall_score
    const breakdown = data.score_breakdown || {};
    setProfileScore({
      overall: data.profile_score || data.overall_score || 0,
      headline: breakdown.headline || data.headline_score || 0,
      summary: breakdown.about || data.summary_score || 0,
      experience: breakdown.experience || data.experience_score || 0,
      skills: breakdown.skills || data.skills_score || 0,
      engagement: breakdown.photo || data.engagement_score || 0,
    });

    // Fix: map improvement_priority to suggestions
    const priorities = data.improvement_priority || [];
    setSuggestions(
      priorities.slice(0, 5).map((s: string, idx: number) => ({
        type: idx < 2 ? 'warning' : 'success',
        category: idx === 0 ? 'Skills' : idx === 1 ? 'Headline' : 'Profile',
        text: s,
      }))
    );

    // Fix: map skills_optimization and gap_analysis to improvements
    const skillsToAdd = (data.skills_optimization?.add || []).slice(0, 3);
    const missingSkills = (data.gap_analysis?.missing_skills || []).slice(0, 3);
    setImprovements([
      {
        title: 'Add Missing Skills',
        description: `Add these skills to your profile: ${skillsToAdd.join(', ')}`,
        impact: 'High',
      },
      {
        title: 'Optimize Headline',
        description: data.headline_variants?.keyword_rich || 'Update your headline with keywords',
        impact: 'High',
      },
      {
        title: 'Improve About Section',
        description: 'Your about section has been optimized. Click to see the new version.',
        impact: 'Medium',
      },
      {
        title: 'Highlight Top Skills',
        description: `Reorder skills to show: ${(data.skills_optimization?.reorder || []).join(', ')}`,
        impact: 'Medium',
      },
    ]);

    // Fix: set optimized summary
    setOptimizedSummary(data.about_section || data.optimized_summary || '');
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold mb-2 gradient-text">
          LinkedIn Profile Analyzer
        </h1>
        <p className="text-white/60">
          Optimize your LinkedIn presence with AI insights
        </p>
      </div>

      {/* Connection Section */}
      <GlassCard gradient="blue">
        <div className="flex items-start gap-4 mb-6">
          <div className="p-3 bg-blue-500/20 rounded-xl">
            <Linkedin className="w-6 h-6 text-blue-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-semibold mb-1">Analyze Your LinkedIn Profile</h2>
            <p className="text-white/60 text-sm">
              Copy your LinkedIn profile content and paste it below for AI-powered analysis
            </p>
          </div>
        </div>

        {/* Step instructions */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { step: '1', text: 'Open your LinkedIn profile in browser' },
            { step: '2', text: 'Select all text (Ctrl+A) and copy (Ctrl+C)' },
            { step: '3', text: 'Paste below and click Analyze' },
          ].map((item) => (
            <div key={item.step} className="glass-card p-3 rounded-xl flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-blue-500/30 text-blue-400 text-xs flex items-center justify-center font-bold flex-shrink-0">
                {item.step}
              </div>
              <p className="text-xs text-white/60">{item.text}</p>
            </div>
          ))}
        </div>

        {/* Paste area */}
        <textarea
          value={profileText}
          onChange={(e) => {
            setProfileText(e.target.value);
            setError('');
          }}
          placeholder="Paste your LinkedIn profile text here..."
          className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm focus:outline-none focus:border-blue-500/50 resize-none mb-4"
          rows={8}
        />

        {error && (
          <p className="text-red-400 text-sm mb-4 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {error}
          </p>
        )}

        <div className="flex items-center gap-4">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleAnalyze}
            disabled={analyzing || !profileText.trim()}
            className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-3 rounded-xl text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {analyzing ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> Analyzing...</>
            ) : (
              <><Zap className="w-4 h-4" /> Analyze Profile</>
            )}
          </motion.button>
          {analyzed && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              onClick={() => {
                setAnalyzed(false);
                setProfileText('');
                setProfileScore({ overall: 0, headline: 0, summary: 0, experience: 0, skills: 0, engagement: 0 });
                setSuggestions([]);
                setImprovements([]);
                setOptimizedSummary('');
              }}
              className="glass-card px-4 py-3 rounded-xl text-sm text-white/60 hover:text-white flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" /> Clear & Re-analyze
            </motion.button>
          )}
        </div>
      </GlassCard>

      {analyzed && (
        <>
          {/* Profile Score */}
          <GlassCard>
            <h3 className="text-xl font-semibold mb-6">Profile Score</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-6">
              {Object.entries(profileScore).map(([key, value]) => (
                <div key={key} className="text-center">
                  <div
                    className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center mb-3 ${
                      value >= 80
                        ? 'bg-green-500/20 border-2 border-green-500/30'
                        : value >= 70
                        ? 'bg-blue-500/20 border-2 border-blue-500/30'
                        : 'bg-yellow-500/20 border-2 border-yellow-500/30'
                    }`}
                  >
                    <span className="text-2xl font-bold">{value}</span>
                  </div>
                  <p className="text-sm text-white/60 capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </p>
                </div>
              ))}
            </div>
          </GlassCard>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Profile Insights */}
            <GlassCard className="lg:col-span-2">
              <h3 className="text-xl font-semibold mb-6">Profile Insights</h3>
              <div className="space-y-3">
                {suggestions.map((suggestion, idx) => (
                  <div
                    key={idx}
                    className={`flex items-start gap-3 p-4 rounded-xl ${
                      suggestion.type === 'success'
                        ? 'bg-green-500/10 border border-green-500/20'
                        : 'bg-yellow-500/10 border border-yellow-500/20'
                    }`}
                  >
                    {suggestion.type === 'success' ? (
                      <CheckCircle2 className="w-5 h-5 text-green-400 mt-0.5 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm font-medium mb-1">
                        {suggestion.category}
                      </p>
                      <p className="text-sm text-white/80">{suggestion.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Quick Stats */}
            <div className="space-y-6">
              <GlassCard>
                <h3 className="text-xl font-semibold mb-4">Network Stats</h3>
                <div className="space-y-3">
                  <div className="glass-card p-3 rounded-xl flex items-center justify-between">
                    <span className="text-sm text-white/60">Connections</span>
                    <span className="text-sm font-medium">Enter manually</span>
                  </div>
                  <div className="glass-card p-3 rounded-xl flex items-center justify-between">
                    <span className="text-sm text-white/60">Profile Views</span>
                    <span className="text-sm font-medium">Check LinkedIn</span>
                  </div>
                  <p className="text-xs text-white/30 text-center mt-2">
                    ?? Live stats require LinkedIn API access
                  </p>
                  <span className="block text-center text-xs px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full">
                    ?? Auto-sync Coming Soon
                  </span>
                </div>
              </GlassCard>

              <GlassCard gradient="purple">
                <div className="flex items-start gap-3 mb-4">
                  <TrendingUp className="w-5 h-5 text-purple-400 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-sm mb-1">Profile Growth</h4>
                    <p className="text-xs text-white/60">
                      Your profile views increased by 32% this month
                    </p>
                  </div>
                </div>
                <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: '32%' }}
                    transition={{ duration: 1 }}
                    className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 rounded-full"
                  />
                </div>
              </GlassCard>
            </div>
          </div>

          {optimizedSummary && (
            <GlassCard>
              <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-cyan-400" />
                AI Optimized Summary
              </h3>
              <p className="text-white/80 text-sm leading-relaxed">{optimizedSummary}</p>
              <button
                onClick={() => navigator.clipboard.writeText(optimizedSummary)}
                className="mt-4 text-xs text-blue-400 hover:text-blue-300 underline"
              >
                Copy to clipboard
              </button>
            </GlassCard>
          )}

          {/* Action Items */}
          <GlassCard>
            <h3 className="text-xl font-semibold mb-6">Recommended Actions</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {improvements.map((item, idx) => (
                <div
                  key={idx}
                  className="glass-card p-4 rounded-xl hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h4 className="font-medium">{item.title}</h4>
                    <span
                      className={`text-xs px-2 py-1 rounded ${
                        item.impact === 'High'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}
                    >
                      {item.impact} Impact
                    </span>
                  </div>
                  <p className="text-sm text-white/60 mb-3">
                    {item.description}
                  </p>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setActiveAction(activeAction === idx ? null : idx)}
                    className="w-full glass-card py-2 rounded-lg text-sm hover:bg-white/10 transition-colors"
                  >
                    {activeAction === idx ? 'Hide ?' : 'Start Now ?'}
                  </motion.button>
                  {activeAction === idx && (
                    <div className="mt-3 p-3 bg-blue-500/10 rounded-xl text-xs text-white/70 space-y-1">
                      {idx === 0 && (
                        <>
                          <p className="text-blue-400 font-medium mb-2">How to add skills on LinkedIn:</p>
                          <p>1. Go to your LinkedIn profile</p>
                          <p>2. Click "Add profile section"</p>
                          <p>3. Select "Skills" ? Add each skill</p>
                          <p className="text-green-400 mt-2">Add: {item.description.replace('Add these skills to your profile: ', '')}</p>
                        </>
                      )}
                      {idx === 1 && (
                        <>
                          <p className="text-blue-400 font-medium mb-2">Suggested headline:</p>
                          <p className="text-white/90 font-medium">{item.description}</p>
                          <p className="mt-2">1. Go to your profile ? Click pencil icon</p>
                          <p>2. Update your headline with the above</p>
                        </>
                      )}
                      {idx === 2 && (
                        <>
                          <p className="text-blue-400 font-medium mb-2">Your AI-optimized About section is ready!</p>
                          <p>Scroll up to "AI Optimized Summary" and click "Copy to clipboard"</p>
                          <p className="mt-1">Then paste it in your LinkedIn About section.</p>
                        </>
                      )}
                      {idx === 3 && (
                        <>
                          <p className="text-blue-400 font-medium mb-2">Reorder your skills:</p>
                          <p>{item.description}</p>
                          <p className="mt-1">Go to Skills section ? drag most relevant skills to top</p>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Content Suggestions */}
          <GlassCard gradient="cyan">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-cyan-500/20 rounded-xl">
                <Zap className="w-6 h-6 text-cyan-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-semibold mb-2">
                  AI Content Suggestions
                </h3>
                <p className="text-white/60 mb-4">
                  Get personalized post ideas based on your industry and interests to boost engagement
                </p>
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => window.open('https://www.linkedin.com/post/new/', '_blank')}
                    className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-2 rounded-xl text-sm font-medium"
                  >
                    Create LinkedIn Post
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => window.open('https://www.linkedin.com/in/', '_blank')}
                    className="glass-card px-6 py-2 rounded-xl text-sm font-medium"
                  >
                    View My Profile ?
                  </motion.button>
                </div>
              </div>
            </div>
          </GlassCard>
        </>
      )}
    </div>
  );
}






