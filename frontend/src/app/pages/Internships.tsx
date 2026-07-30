import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import api from '../lib/api';
import { internshipService, applicationService, recommendationService, internshipStatsService } from '../lib/services';
import { GlassCard } from '../components/GlassCard';
import { SkillGapSection } from '../components/SkillGapSection';
import { CompanyAvatar } from '../components/CompanyAvatar';
import { motion, AnimatePresence } from 'motion/react';
import {
  Search, MapPin, Briefcase, Clock, DollarSign,
  Bookmark, ExternalLink, Filter, RefreshCw, X,
  CheckCircle2, AlertCircle, Loader2,
} from 'lucide-react';

const categoryFilters = ['All', 'Software Engineering', 'Product', 'Design', 'Data Science'];

const refreshMessages = [
  'Scanning opportunities matching your skills...',
  'Finding internships tailored to your resume...',
  'Analyzing skill matches across job boards...',
  'Discovering roles aligned with your profile...',
];

const sourceLogoMap: Record<string, string> = {
  linkedin: '/linkedin.png',
  internshala: '/internshala.png',
  naukri: '/naukri.png',
  indeed: '/indeed.png',
  unstop: '/unstop.png',
  wellfound: '/wellfound.png',
  shine: '/shine.png',
};

const getSourceLogo = (source?: string): string | null => {
  if (!source) return null;
  return sourceLogoMap[source.trim().toLowerCase()] || null;
};

// ─── Client-side role detection ────────────────────────────────────────────────
// Lightweight mirror of backend role_stack.detect_role, used ONLY to show a role
// badge on each card WITHOUT firing a per-card /match-insights request. The
// authoritative role (+ stack, categorized gaps, impacts) lives on the Skill Gap
// page, which does call the API. Keep keyword order most-specific → general.
const ROLE_KEYWORDS: [string, string[]][] = [
  ['Machine Learning', ['machine learning', 'ml engineer', 'deep learning', 'ai engineer', 'artificial intelligence', 'nlp', 'computer vision', 'data scientist', 'mlops', 'llm']],
  ['Data Science', ['data analyst', 'data analytics', 'data engineer', 'business intelligence', 'bi analyst', 'etl', 'tableau', 'power bi', 'big data', 'analytics', 'data science']],
  ['Frontend', ['frontend', 'front-end', 'front end', 'ui developer', 'ui/ux', 'react developer', 'angular developer', 'vue developer', 'web designer']],
  ['Mobile', ['mobile', 'android', 'ios', 'flutter', 'react native', 'app developer']],
  ['DevOps / Cloud', ['devops', 'site reliability', 'sre', 'cloud engineer', 'platform engineer', 'infrastructure', 'kubernetes']],
  ['Security', ['security', 'cybersecurity', 'penetration', 'soc analyst', 'infosec']],
  ['Full-Stack', ['full stack', 'full-stack', 'fullstack', 'mern', 'mean']],
  ['Backend', ['backend', 'back-end', 'back end', 'server-side', 'api developer', 'microservices']],
];

const detectRoleLabel = (title?: string): string => {
  const t = (title || '').toLowerCase();
  for (const [label, kws] of ROLE_KEYWORDS) {
    if (kws.some(k => t.includes(k))) return label;
  }
  return 'Software Engineer';
};

// ─── Stats ────────────────────────────────────────────────────────────────────
// Four stat values fetched from GET /internships/stats (server-computed).
// Uses raw SQL on the backend so new_this_week matches the DB exactly.

interface Stats {
  total_positions: number;
  new_this_week: number;
  high_match: number;
  saved: number;
}

const EMPTY_STATS: Stats = { total_positions: 0, new_this_week: 0, high_match: 0, saved: 0 };

// ─── Main component ───────────────────────────────────────────────────────────

const Internships = () => {
  const navigate = useNavigate();

  // Recommendation data (drives card list and stats)
  const [recs, setRecs] = useState<any[]>(() => {
    try {
      const c = localStorage.getItem('cached_recs');
      return c ? JSON.parse(c) : [];
    } catch { return []; }
  });

  // Supplemental internship list for search / load-more modes
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [searchScores, setSearchScores] = useState<Record<string, number>>({});

  // Saved internship IDs — source of truth is Applications table
  // Map: internshipId → applicationId (needed for DELETE)
  const [savedMap, setSavedMap] = useState<Map<number, number>>(new Map());
  const [savingId, setSavingId] = useState<number | null>(null);
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);

  const [loading, setLoading] = useState(() => !localStorage.getItem('cached_recs'));
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');
  const [refreshSuccess, setRefreshSuccess] = useState(false);
  const [refreshError, setRefreshError] = useState(false);

  const [search, setSearch] = useState('');
  const [searchSuggestions, setSearchSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [showFilters, setShowFilters] = useState(false);
  const [locationFilter, setLocationFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('all');
  const [scraping, setScraping] = useState(false);

  const [explanations, setExplanations] = useState<Record<number, any>>({});
  const [loadingExplain, setLoadingExplain] = useState<Record<number, boolean>>({});
  const [expandedExplain, setExpandedExplain] = useState<Record<number, boolean>>({});

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load recommendations, saved applications, and stats on mount
  useEffect(() => {
    Promise.all([loadRecs(), loadSaved(), loadStats()]);
  }, []);

  // ── Data loaders ───────────────────────────────────────────────────────────

  const loadRecs = async () => {
    try {
      const data = await recommendationService.get();
      const items = data.recommendations || [];
      setRecs(items);
      localStorage.setItem('cached_recs', JSON.stringify(items));
    } catch {
      // keep cached recs if API fails
    } finally {
      setLoading(false);
    }
  };

  // Fetch all saved applications and build internshipId → applicationId map
  const loadSaved = async () => {
    try {
      const data = await applicationService.getAll('saved');
      const apps: any[] = data.applications || [];
      const m = new Map<number, number>();
      for (const app of apps) {
        const iid = app.internship?.id ?? app.internship_id;
        if (iid) m.set(iid, app.id);
      }
      setSavedMap(m);
    } catch {
      // non-fatal — worst case: bookmark icons wrong until refresh
    }
  };

  const loadStats = async () => {
    try {
      const data = await internshipStatsService.get();
      setStats(data);
    } catch {
      // non-fatal — stats stay at last known value
    }
  };

  // ── Search (query the internships API, not the rec list) ──────────────────

  const loadSearch = async (query: string, targetPage = 1, append = false) => {
    if (!query.trim()) {
      setIsSearchMode(false);
      setSearchResults([]);
      setSearchScores({});
      return;
    }
    if (!append) setLoading(true);
    try {
      const data = await internshipService.getAll({ page: targetPage, limit: 20, search: query });
      const items = (data.internships || data.items || []) as any[];
      const mapped = items.map((item: any) => ({
        id: item.id,
        company: item.company || 'Company',
        position: item.title || 'Position',
        location: item.location || 'Remote',
        salary: item.salary_range || 'Competitive',
        posted: item.created_at
          ? new Date(item.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
          : 'Recently',
        rawDate: item.created_at || null,
        match: 0,
        logo: getSourceLogo(item.source),
        source: item.source || '',
        tags: [],   // populated from matched_skills in displayList when a rec exists
        url: item.application_url || '#',
        matchedSkills: [],
        missingSkills: [],
      }));
      setSearchResults(prev => append ? [...prev, ...mapped] : mapped);
      setIsSearchMode(true);
      if (data.search_scores) setSearchScores(data.search_scores);
      setTotalPages(data.pages || 1);
    } catch { }
    setLoading(false);
  };

  // ── Save / Unsave ──────────────────────────────────────────────────────────

  const handleSave = async (internshipId: number) => {
    if (savingId !== null) return;
    setSavingId(internshipId);

    const isSaved = savedMap.has(internshipId);

    if (isSaved) {
      // Optimistic remove
      const appId = savedMap.get(internshipId)!;
      setSavedMap(prev => { const m = new Map(prev); m.delete(internshipId); return m; });
      try {
        await applicationService.delete(appId);
      } catch {
        // Rollback
        setSavedMap(prev => new Map(prev).set(internshipId, appId));
      }
    } else {
      // Optimistic add with placeholder id=-1 until backend confirms
      setSavedMap(prev => new Map(prev).set(internshipId, -1));
      try {
        const created = await applicationService.create(internshipId, 'saved');
        const appId = created.id;
        setSavedMap(prev => new Map(prev).set(internshipId, appId));
      } catch (err: any) {
        // Rollback
        setSavedMap(prev => { const m = new Map(prev); m.delete(internshipId); return m; });
        // 400 "Already tracking" means it's actually saved — reload to sync
        if (err?.response?.status === 400) await loadSaved();
      }
    }

    setSavingId(null);
    // Refresh stats so Saved count stays in sync with the backend
    loadStats();
  };

  // ── Refresh ────────────────────────────────────────────────────────────────

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshError(false);
    setRefreshSuccess(false);
    setRefreshMsg(refreshMessages[Math.floor(Math.random() * refreshMessages.length)]);
    try {
      await recommendationService.refresh();
      api.post('/agent/trigger', { trigger: 'user_refresh' }).catch(() => {});
      await loadRecs();
      setRefreshSuccess(true);
      window.setTimeout(() => setRefreshSuccess(false), 2500);
      // Refresh stats after rec update — high_match count may change
      loadStats();
    } catch {
      setRefreshError(true);
    } finally {
      setRefreshing(false);
      setRefreshMsg('');
    }
  };

  // ── Explain ────────────────────────────────────────────────────────────────

  const handleExplain = async (internshipId: number) => {
    if (expandedExplain[internshipId]) {
      setExpandedExplain(prev => ({ ...prev, [internshipId]: false }));
      return;
    }
    if (explanations[internshipId]) {
      setExpandedExplain(prev => ({ ...prev, [internshipId]: true }));
      return;
    }
    setLoadingExplain(prev => ({ ...prev, [internshipId]: true }));
    try {
      const data = await internshipService.explainMatch(internshipId);
      setExplanations(prev => ({ ...prev, [internshipId]: data }));
      setExpandedExplain(prev => ({ ...prev, [internshipId]: true }));
    } catch {
      alert('Could not generate explanation. Try again.');
    }
    setLoadingExplain(prev => ({ ...prev, [internshipId]: false }));
  };

  // ── Filters + display list ─────────────────────────────────────────────────

  const displayList = (() => {
    // Search mode: use search results, merge in rec match scores
    if (isSearchMode) {
      return searchResults.map(item => {
        const rec = recs.find(r => r.internship_id === item.id);
        return rec
          ? {
              ...item,
              match:         Math.floor(rec.match_percentage ?? 0),
              matchedSkills: rec.matched_skills  || [],
              missingSkills: rec.missing_skills  || [],
              tags:          (rec.matched_skills || []).slice(0, 3),
            }
          : item;
      });
    }
    // Normal mode: use recs list, map to card shape
    let list = recs.map((rec: any) => ({
      id: rec.internship_id,
      company: rec.company || 'Company',
      position: rec.title || 'Position',
      location: rec.location || 'Remote',
      salary: 'Competitive',
      posted: rec.internship_created_at
        ? new Date(rec.internship_created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
        : 'Recently',
      rawDate: rec.internship_created_at || null,
      match: Math.floor(rec.match_percentage ?? 0),
      logo: getSourceLogo(rec.source),
      source: rec.source || '',
      tags: (rec.matched_skills || []).slice(0, 3),
      url: rec.application_url || '#',
      matchedSkills: rec.matched_skills || [],
      missingSkills: rec.missing_skills || [],
    }));

    // Category filter
    if (selectedCategory !== 'All') {
      const categoryMap: Record<string, string[]> = {
        'Software Engineering': ['software', 'developer', 'engineer', 'backend', 'frontend', 'fullstack', 'web', 'python', 'java', 'node', 'react', 'devops'],
        'Product': ['product', 'manager', 'pm', 'strategy', 'business', 'operations'],
        'Design': ['design', 'ui', 'ux', 'graphic', 'creative', 'figma', 'visual'],
        'Data Science': ['data', 'analytics', 'ml', 'machine learning', 'ai', 'analyst', 'science', 'artificial'],
      };
      const kw = categoryMap[selectedCategory] || [];
      list = list.filter(i =>
        kw.some(k =>
          i.position.toLowerCase().includes(k) ||
          i.tags.some((t: string) => t.toLowerCase().includes(k))
        )
      );
    }

    // Location filter
    if (locationFilter.trim()) {
      list = list.filter(i => i.location.toLowerCase().includes(locationFilter.toLowerCase()));
    }

    // Date filter
    if (dateFilter !== 'all') {
      const now = Date.now();
      list = list.filter(i => {
        if (!i.rawDate) return true;
        const diffDays = (now - new Date(i.rawDate).getTime()) / 86_400_000;
        if (dateFilter === 'today') return diffDays <= 1;
        if (dateFilter === 'week')  return diffDays <= 7;
        if (dateFilter === 'month') return diffDays <= 30;
        return true;
      });
    }

    return list;
  })();

  // Search suggestions from rec list
  useEffect(() => {
    if (search.length > 1) {
      const q = search.toLowerCase();
      setSearchSuggestions(
        recs.filter(r =>
          (r.title || '').toLowerCase().includes(q) ||
          (r.company || '').toLowerCase().includes(q)
        ).slice(0, 5).map(r => ({ id: r.internship_id, position: r.title, company: r.company, location: r.location }))
      );
    } else {
      setSearchSuggestions([]);
      setShowSuggestions(false);
    }
  }, [search, recs]);

  // ── Load more (search mode only — normal mode uses rec list which is all) ──

  const handleLoadMore = async () => {
    if (isSearchMode) {
      if (page < totalPages) {
        const nextPage = page + 1;
        setPage(nextPage);
        await loadSearch(search, nextPage, true);
      } else {
        setScraping(true);
        try {
          await api.post('/agent/trigger', { trigger: 'user_refresh' });
          await new Promise(r => setTimeout(r, 5000));
          setPage(1);
          await loadSearch(search, 1);
        } catch {
          await loadSearch(search, 1);
        }
        setScraping(false);
      }
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold mb-2 gradient-text">Internship Opportunities</h1>
          <p className="text-white/60">AI-matched positions based on your profile</p>
        </div>
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={refreshing ? {} : { scale: 1.05 }}
            whileTap={refreshing ? {} : { scale: 0.95 }}
            onClick={handleRefresh}
            disabled={refreshing}
            className="glass-card px-4 py-2 rounded-xl flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="text-sm">{refreshing ? 'Updating recommendations...' : 'Refresh'}</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setShowFilters(!showFilters)}
            className={`glass-card px-4 py-2 rounded-xl flex items-center gap-2 ${showFilters ? 'bg-blue-500/20 border border-blue-500/30' : ''}`}
          >
            <Filter className="w-4 h-4" />
            <span className="text-sm">Filters</span>
          </motion.button>
        </div>
      </div>

      {/* Status banners */}
      <AnimatePresence>
        {refreshing && refreshMsg && (
          <motion.div key="refresh-progress" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="glass-card p-4 rounded-xl border border-blue-500/30 flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-blue-400 animate-spin flex-shrink-0" />
            <p className="text-sm text-blue-300">{refreshMsg}</p>
          </motion.div>
        )}
        {!refreshing && refreshSuccess && (
          <motion.div key="refresh-success" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="glass-card p-4 rounded-xl border border-green-500/30 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
            <p className="text-sm text-green-300">Recommendations updated</p>
          </motion.div>
        )}
        {!refreshing && refreshError && (
          <motion.div key="refresh-error" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="glass-card p-4 rounded-xl border border-red-500/30 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
              <p className="text-sm text-red-300">Couldn't update recommendations. Please try again.</p>
            </div>
            <button onClick={handleRefresh}
              className="text-sm px-3 py-1 rounded-lg bg-red-500/20 text-red-200 hover:bg-red-500/30 transition-colors flex items-center gap-1">
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters panel */}
      <AnimatePresence>
        {showFilters && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <GlassCard>
              <h3 className="font-semibold mb-4">Advanced Filters</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-2 block">Location</label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input type="text" placeholder="e.g. Chennai, Bengaluru..." value={locationFilter}
                      onChange={e => setLocationFilter(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500/50" />
                  </div>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-2 block">Posted Within</label>
                  <select value={dateFilter} onChange={e => setDateFilter(e.target.value)}
                    className="w-full border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                    style={{ background: '#1a1a2e', color: 'white' }}>
                    <option value="all">Any time</option>
                    <option value="today">Today</option>
                    <option value="week">This week</option>
                    <option value="month">This month</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button onClick={() => { setLocationFilter(''); setDateFilter('all'); setSelectedCategory('All'); setSearch(''); setIsSearchMode(false); setSearchResults([]); setSearchScores({}); }}
                    className="w-full glass-card py-2 rounded-xl text-sm hover:bg-white/10 transition-colors flex items-center justify-center gap-2">
                    <X className="w-4 h-4" /> Clear All Filters
                  </button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search + category strip */}
      <div className="glass-card rounded-2xl p-6 relative" style={{ overflow: 'visible', zIndex: 100 }}>
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1" style={{ position: 'relative', zIndex: 999 }}>
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search positions, companies, skills..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); setShowSuggestions(false); loadSearch(search.trim()); }
                if (e.key === 'Escape') setShowSuggestions(false);
              }}
              onFocus={() => { if (search.length > 1) setShowSuggestions(true); }}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
            />
            <AnimatePresence>
              {showSuggestions && searchSuggestions.length > 0 && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="absolute top-full left-0 right-0 mt-2 rounded-xl overflow-hidden shadow-2xl"
                  style={{ zIndex: 99999, background: '#13131f', border: '1px solid rgba(255,255,255,0.1)' }}>
                  {searchSuggestions.map(s => (
                    <button key={s.id} onMouseDown={() => { setSearch(s.position); setShowSuggestions(false); setTimeout(() => loadSearch(s.position), 100); }}
                      className="w-full px-4 py-3 text-left hover:bg-white/10 transition-colors flex items-center gap-3">
                      <Briefcase className="w-4 h-4 text-white/40" />
                      <div>
                        <p className="text-sm font-medium">{s.position}</p>
                        <p className="text-xs text-white/60">{s.company} · {s.location}</p>
                      </div>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <div className="flex gap-2 overflow-x-auto">
            {categoryFilters.map(filter => (
              <button key={filter} onClick={() => setSelectedCategory(filter)}
                className={`px-4 py-2 rounded-xl text-sm whitespace-nowrap transition-all ${selectedCategory === filter ? 'bg-gradient-to-r from-blue-500 to-purple-500' : 'glass-card hover:bg-white/5'}`}>
                {filter}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats — server-computed from GET /internships/stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4" style={{ position: 'relative', zIndex: 1 }}>
        {[
          { label: 'Total Positions', value: stats.total_positions },
          { label: 'New This Week',   value: stats.new_this_week },
          { label: 'High Match',      value: stats.high_match },
          { label: 'Saved',           value: stats.saved },
        ].map((stat, idx) => (
          <GlassCard key={idx}>
            <p className="text-white/60 text-sm mb-1">{stat.label}</p>
            <p className="text-2xl font-bold">{stat.value}</p>
          </GlassCard>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-3 py-12 text-white/60">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Loading internships...</span>
        </div>
      )}

      {!loading && displayList.length === 0 && (
        <GlassCard className="text-center py-12">
          <Briefcase className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2">No matches found</h3>
          <p className="text-white/60 mb-4">
            {recs.length === 0
              ? 'No recommendations yet — click Refresh to generate AI-matched internships'
              : 'Try adjusting your filters or search terms'}
          </p>
          {recs.length === 0 && (
            <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
              onClick={handleRefresh} disabled={refreshing}
              className="bg-gradient-to-r from-blue-500 to-purple-500 px-5 py-2.5 rounded-xl inline-flex items-center gap-2 text-sm font-medium disabled:opacity-60">
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Refreshing...' : 'Generate Recommendations'}
            </motion.button>
          )}
        </GlassCard>
      )}

      {/* Skeleton while refreshing */}
      {refreshing && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <GlassCard key={`sk-${i}`}>
              <div className="animate-pulse space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-white/10" />
                    <div className="space-y-2"><div className="h-4 w-40 bg-white/10 rounded" /><div className="h-3 w-24 bg-white/10 rounded" /></div>
                  </div>
                  <div className="h-6 w-16 bg-white/10 rounded-full" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[1,2,3,4].map(j => <div key={j} className="h-3 bg-white/10 rounded" />)}
                </div>
                <div className="flex gap-2"><div className="h-8 flex-1 bg-white/10 rounded-xl" /><div className="h-8 w-12 bg-white/10 rounded-xl" /></div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {/* Card grid */}
      <div className={`grid grid-cols-1 lg:grid-cols-2 gap-6 transition-opacity duration-300 ${refreshing ? 'opacity-0 pointer-events-none h-0 overflow-hidden' : 'opacity-100'}`}>
        {displayList.map(internship => {
          const isSaved = savedMap.has(internship.id);
          const isSaving = savingId === internship.id;
          const pct = isSearchMode
            ? (searchScores[String(internship.id)] ?? internship.match ?? 0)
            : (internship.match ?? 0);
          const roleLabel = detectRoleLabel(internship.position);

          return (
            <GlassCard key={internship.id} hover>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-4">
                  <CompanyAvatar logo={internship.logo} name={internship.company} alt={internship.source} className="w-12 h-12" />
                  <div>
                    <h3 className="font-semibold mb-1">{internship.position}</h3>
                    <p className="text-sm text-white/60">{internship.company}</p>
                    <span className="inline-block mt-1.5 px-2 py-0.5 rounded-md text-[10px] font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                      {roleLabel}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Badge color follows the SAME buckets as the "High Match"
                      counter (item #4): High >= 75, Medium 50-74, Low < 50 —
                      so a card's color never contradicts the stat. */}
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                    pct >= 75 ? 'bg-green-500/20 text-green-400'
                    : pct >= 50 ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-purple-500/20 text-purple-400'
                  }`}>
                    {pct}% {isSearchMode ? 'Relevant' : 'Match'}
                  </div>
                  {/* Save / Unsave button — calls backend */}
                  <button
                    onClick={() => handleSave(internship.id)}
                    disabled={isSaving}
                    title={isSaved ? 'Remove from saved' : 'Save internship'}
                    className={`p-2 rounded-lg transition-colors disabled:opacity-50 ${isSaved ? 'bg-yellow-500/20 text-yellow-400' : 'hover:bg-white/5 text-white/40 hover:text-white/80'}`}
                  >
                    {isSaving
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <Bookmark className={`w-4 h-4 ${isSaved ? 'fill-yellow-400' : ''}`} />
                    }
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="flex items-center gap-2 text-sm text-white/60"><MapPin className="w-4 h-4" />{internship.location}</div>
                <div className="flex items-center gap-2 text-sm text-white/60"><Briefcase className="w-4 h-4" />Internship</div>
                <div className="flex items-center gap-2 text-sm text-white/60"><DollarSign className="w-4 h-4" />{internship.salary}</div>
                <div className="flex items-center gap-2 text-sm text-white/60"><Clock className="w-4 h-4" />{internship.posted}</div>
              </div>

              {/* ── Skill match panels — always visible, FULL skill list ── */}
              {(internship.matchedSkills.length > 0 || internship.missingSkills.length > 0) && (
                <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
                  {/* Why you match */}
                  <div className="p-2.5 bg-green-500/10 rounded-xl border border-green-500/20">
                    <p className="text-green-400 font-semibold mb-1.5 flex items-center gap-1">
                      <span>✅</span> Why you match
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {internship.matchedSkills.map((skill: string, i: number) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 bg-green-500/20 text-green-300 rounded-md text-[10px] capitalize"
                        >
                          {skill}
                        </span>
                      ))}
                      {internship.matchedSkills.length === 0 && (
                        <span className="text-white/30 text-[10px]">No matches yet</span>
                      )}
                    </div>
                  </div>

                  {/* Skills to build */}
                  <div className="p-2.5 bg-orange-500/10 rounded-xl border border-orange-500/20">
                    <p className="text-orange-400 font-semibold mb-1.5 flex items-center gap-1">
                      <span>⚠️</span> Skills to build
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {internship.missingSkills.map((skill: string, i: number) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 bg-orange-500/20 text-orange-300 rounded-md text-[10px] capitalize"
                        >
                          {skill}
                        </span>
                      ))}
                      {/* "All matched" only when there ARE matched skills, none
                          missing, AND the score is genuinely high (item #2, >=90).
                          A low score with no listed gaps is thin data, not a
                          perfect match — show "partial" instead. */}
                      {internship.missingSkills.length === 0 && internship.matchedSkills.length > 0 && pct >= 90 && (
                        <span className="text-green-300 text-[10px]">All matched 🎯</span>
                      )}
                      {internship.missingSkills.length === 0 && internship.matchedSkills.length > 0 && pct < 90 && (
                        <span className="text-white/50 text-[10px]">Partial match</span>
                      )}
                      {internship.missingSkills.length === 0 && internship.matchedSkills.length === 0 && (
                        <span className="text-white/30 text-[10px]">No data yet</span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={() => handleSave(internship.id)} disabled={isSaving}
                  className={`flex-1 rounded-xl py-2 text-sm font-medium transition-all ${isSaved ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : 'bg-gradient-to-r from-blue-500 to-purple-500'}`}>
                  {isSaving ? 'Saving...' : isSaved ? 'Saved ✓' : 'Save'}
                </motion.button>
                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={() => window.open(internship.url, '_blank')}
                  className="glass-card px-4 py-2 rounded-xl">
                  <ExternalLink className="w-4 h-4" />
                </motion.button>
              </div>

              <button onClick={() => handleExplain(internship.id)}
                className="w-full mt-2 text-xs text-blue-400 hover:text-blue-300 flex items-center justify-center gap-1 py-1">
                {loadingExplain[internship.id] ? '⚡ Analyzing...' : expandedExplain[internship.id] ? '↑ Hide explanation' : '⚡ Why this matches you?'}
              </button>

              <button onClick={() => navigate(`/skill-gap/${internship.id}`)}
                className="w-full text-xs text-white/60 hover:text-white transition-colors flex items-center justify-center gap-1 py-1">
                View Skill Gap →
              </button>

              {expandedExplain[internship.id] && explanations[internship.id] && (
                <div className="mt-2 space-y-2">
                  {(explanations[internship.id].match_reasons?.length > 0 || explanations[internship.id].tip) && (
                    <div className="p-3 bg-white/5 rounded-xl text-xs space-y-2">
                      {explanations[internship.id].match_reasons?.length > 0 && (
                        <div>
                          <p className="text-green-400 font-medium mb-1">Why it matches:</p>
                          <ul className="space-y-1">
                            {explanations[internship.id].match_reasons.map((r: string, i: number) => (
                              <li key={i} className="text-white/70">• {r}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {explanations[internship.id].tip && (
                        <p className="text-purple-300 italic">💡 {explanations[internship.id].tip}</p>
                      )}
                    </div>
                  )}
                  <SkillGapSection
                    matchedSkills={internship.matchedSkills ?? []}
                    missingSkills={internship.missingSkills ?? []}
                    matchPercentage={internship.match ?? 0}
                    onStartLearning={() => alert('Learning resources coming soon!')}
                  />
                </div>
              )}
            </GlassCard>
          );
        })}
      </div>

      {/* Load More (only in search mode — rec list is already complete) */}
      {isSearchMode && (
        <div className="text-center">
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={handleLoadMore} disabled={scraping}
            className="glass-card px-8 py-3 rounded-xl font-medium disabled:opacity-70">
            {scraping ? (
              <span className="flex items-center gap-2"><RefreshCw className="w-4 h-4 animate-spin" />Finding fresh opportunities...</span>
            ) : page < totalPages ? 'Load More Results' : 'Find More Opportunities'}
          </motion.button>
        </div>
      )}
    </div>
  );
};

export { Internships };
