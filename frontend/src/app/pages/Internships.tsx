import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { internshipService, applicationService, recommendationService } from '../lib/services';
import { GlassCard } from '../components/GlassCard';
import { motion, AnimatePresence } from 'motion/react';
import {
  Search, MapPin, Briefcase, Clock, DollarSign,
  Bookmark, ExternalLink, Filter, RefreshCw, X,
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

const Internships = () => {
  const [internships, setInternships] = useState<any[]>(() => {
    try {
      const cached = localStorage.getItem('cached_internships');
      return cached ? JSON.parse(cached) : [];
    } catch { return []; }
  });
  const [filteredInternships, setFilteredInternships] = useState<any[]>([]);
  const [loading, setLoading] = useState(() => {
  const cached = localStorage.getItem('cached_internships');
  return !cached; // Only show loading if no cache
});
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');
  const [search, setSearch] = useState('');
  const [searchSuggestions, setSearchSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [totalCount, setTotalCount] = useState<number>(() => {
    try {
      const cached = localStorage.getItem('cached_total');
      return cached ? parseInt(cached) : 0;
    } catch { return 0; }
  });
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [bookmarked, setBookmarked] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem('bookmarked_internships');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [showFilters, setShowFilters] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [locationFilter, setLocationFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('all');
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [searchScores, setSearchScores] = useState<Record<string, number>>({});
  const [explanations, setExplanations] = useState<Record<number, any>>({});
  const [loadingExplain, setLoadingExplain] = useState<Record<number, boolean>>({});
  const [expandedExplain, setExpandedExplain] = useState<Record<number, boolean>>({});
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (search.length > 1 && !false) {
      const suggestions = internships.filter(i =>
        i.position.toLowerCase().includes(search.toLowerCase()) ||
        i.company.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 5);
      setSearchSuggestions(suggestions);
    } else {
      setShowSuggestions(false);
    }
  }, [search, internships]);

  const applyFilters = () => {
    let filtered = [...internships];

    if (selectedCategory !== 'All') {
      const categoryMap: Record<string, string[]> = {
        'Software Engineering': ['software', 'developer', 'engineer', 'backend', 'frontend', 'fullstack', 'web', 'python', 'java', 'node', 'react', 'devops'],
        'Product': ['product', 'manager', 'pm', 'strategy', 'business', 'operations'],
        'Design': ['design', 'ui', 'ux', 'graphic', 'creative', 'figma', 'visual'],
        'Data Science': ['data', 'analytics', 'ml', 'machine learning', 'ai', 'analyst', 'science', 'artificial'],
      };
      const keywords = categoryMap[selectedCategory] || [];
      filtered = filtered.filter(i =>
        keywords.some(k =>
          i.position.toLowerCase().includes(k) ||
          i.tags.some((t: string) => t.toLowerCase().includes(k))
        )
      );
    }

    if (locationFilter.trim()) {
      filtered = filtered.filter(i =>
        i.location.toLowerCase().includes(locationFilter.toLowerCase())
      );
    }

    if (dateFilter !== 'all') {
      const now = new Date();
      filtered = filtered.filter(i => {
        if (!i.rawDate) return true;
        const posted = new Date(i.rawDate);
        const daysDiff = (now.getTime() - posted.getTime()) / (1000 * 60 * 60 * 24);
        if (dateFilter === 'today') return daysDiff <= 1;
        if (dateFilter === 'week') return daysDiff <= 7;
        if (dateFilter === 'month') return daysDiff <= 30;
        return true;
      });
    }

    setFilteredInternships(filtered);
  };

  const loadInternships = async (append = false, searchQuery = '') => {
    if (internships.length === 0) setLoading(true);
    try {
      const data = await internshipService.getAll({ page, limit: 20, search: searchQuery });
      const items = data.internships || data.items || data || [];
    
    // Track if we're in search mode
    setIsSearchMode(data.is_search || false);
    if (data.search_scores) {
      setSearchScores(data.search_scores);
    }
      const mapped = items.map((item: any) => ({
        id: item.id,
        company: item.company || 'Company',
        position: item.title || 'Position',
        location: item.location || 'Remote',
        type: 'Internship',
        salary: item.salary_range || 'Competitive',
        posted: item.created_at
          ? new Date(item.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
          : 'Recently',
        rawDate: item.created_at,
        match: 50,
        logo: sourceLogoMap[item.source] || null,
        sourceName: item.source || 'web',
        tags: item.description
          ? item.description.split(' ').filter((w: string) => w.length > 5).slice(0, 3)
          : [],
        url: item.application_url || '#',
      }));      if (!append) {
        localStorage.setItem('cached_internships', JSON.stringify(mapped));
        localStorage.setItem('cached_total', String(data.total || items.length));
      }
      setInternships(prev => append ? [...prev, ...mapped] : mapped);
      setTotalCount(data.total || items.length);
      setTotalPages(data.pages || 1);


      try {
        const recData = await recommendationService.get();
        const recs = recData.recommendations || [];
        if (recs.length > 0) {
          setInternships(prev => prev.map((internship: any) => {
            const rec = recs.find((r: any) => r.internship_id === internship.id);
            return rec ? { ...internship, match: Math.round(rec.match_percentage || rec.similarity_score * 100) } : internship;
          }));
        }
      } catch { }

      // Sort by match score descending after merging recommendations
      setInternships(prev => [...prev].sort((a, b) => (b.match || 0) - (a.match || 0)));

    } catch {
      if (!append) setInternships([]);
    }
    setLoading(false);
  };

  const handleExplain = async (internshipId: number) => {
    // Toggle off if already showing
    if (expandedExplain[internshipId]) {
      setExpandedExplain(prev => ({ ...prev, [internshipId]: false }));
      return;
    }
    // If already loaded, just show it
    if (explanations[internshipId]) {
      setExpandedExplain(prev => ({ ...prev, [internshipId]: true }));
      return;
    }
    // Fetch from API
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

  const handleSearch = () => {
    setShowSuggestions(false);
    setPage(1);
    loadInternships(false, search.trim());
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    const msg = refreshMessages[Math.floor(Math.random() * refreshMessages.length)];
    setRefreshMsg(msg);
    try { await recommendationService.refresh(); } catch { }
    try { await api.post('/agent/trigger', { trigger: 'user_refresh' }); } catch { }
    setTimeout(async () => {
      await loadInternships();
      setRefreshing(false);
      setRefreshMsg('');
    }, 4000);
  };

  const handleLoadMore = async () => {
    if (page < totalPages) {
      setPage(prev => prev + 1);
      await loadInternships(true, search.trim());
    } else {
      setScraping(true);
      try {
        await api.post('/agent/trigger', { trigger: 'user_refresh' });
        await new Promise(resolve => setTimeout(resolve, 5000));
        setPage(1);
        await loadInternships(false, search.trim());
      } catch {
        await loadInternships(false, search.trim());
      }
      setScraping(false);
    }
  };

  const handleTrack = async (internshipId: number) => {
    try {
      await applicationService.create(internshipId, 'saved');
      alert('Added to your applications tracker!');
    } catch (err: any) {
      if (err.response?.data?.detail?.includes('Already')) {
        alert('Already in your tracker!');
      }
    }
  };

  const toggleBookmark = (id: number) => {
    setBookmarked(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const isFiltering = selectedCategory !== 'All' || locationFilter.trim() !== '' || dateFilter !== 'all';
  const displayList = isFiltering ? filteredInternships : internships;

  const newThisWeek = internships.filter(i => {
    if (!i.rawDate) return false;
    const d = new Date(i.rawDate);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return d >= weekAgo;
  }).length;

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
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleRefresh}
            disabled={refreshing}
            className="glass-card px-4 py-2 rounded-xl flex items-center gap-2 disabled:opacity-70"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="text-sm">{refreshing ? 'Scanning...' : 'Refresh'}</span>
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

      {/* Refresh message */}
      <AnimatePresence>
        {refreshing && refreshMsg && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="glass-card p-4 rounded-xl border border-blue-500/30 flex items-center gap-3"
          >
            <RefreshCw className="w-5 h-5 text-blue-400 animate-spin flex-shrink-0" />
            <p className="text-sm text-blue-300">{refreshMsg}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Advanced Filters Panel */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <GlassCard>
              <h3 className="font-semibold mb-4">Advanced Filters</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-2 block">Location</label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="text"
                      placeholder="e.g. Chennai, Bengaluru..."
                      value={locationFilter}
                      onChange={(e) => setLocationFilter(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-2 block">Posted Within</label>
                  <select
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value)}
                    className="w-full border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                    style={{ background: '#1a1a2e', color: 'white' }}
                  >
                    <option value="all">Any time</option>
                    <option value="today">Today</option>
                    <option value="week">This week</option>
                    <option value="month">This month</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={() => { setLocationFilter(''); setDateFilter('all'); setSelectedCategory('All'); setSearch(''); loadInternships(); }}
                    className="w-full glass-card py-2 rounded-xl text-sm hover:bg-white/10 transition-colors flex items-center justify-center gap-2"
                  >
                    <X className="w-4 h-4" />
                    Clear All Filters
                  </button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search and Category Filters */}
      <div className="glass-card rounded-2xl p-6 relative" style={{ overflow: 'visible', zIndex: 100 }}>
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search Input */}
          <div className="flex-1" style={{ position: 'relative', zIndex: 999 }}>
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search positions, companies, skills..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setShowSuggestions(false);
                  handleSearch();
                }
                if (e.key === 'Escape') {
                  setShowSuggestions(false);
                }
              }}
              onFocus={() => { if (search.length > 1) setShowSuggestions(true); }}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
            />
            {/* Search Suggestions Dropdown */}
            <AnimatePresence>
              {showSuggestions && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="absolute top-full left-0 right-0 mt-2 rounded-xl overflow-hidden shadow-2xl"
                  style={{ zIndex: 99999, background: '#13131f', border: '1px solid rgba(255,255,255,0.1)' }}
                >
                  {searchSuggestions.map((s) => (
                    <button
                      key={s.id}
                      onMouseDown={() => {
                        setSearch(s.position);
                        setShowSuggestions(false);
                        setTimeout(() => loadInternships(false, s.position), 100);
                      }}
                      className="w-full px-4 py-3 text-left hover:bg-white/10 transition-colors flex items-center gap-3"
                    >
                      <Briefcase className="w-4 h-4 text-white/40" />
                      <div>
                        <p className="text-sm font-medium">{s.position}</p>
                        <p className="text-xs text-white/60">{s.company} • {s.location}</p>
                      </div>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Category Filters */}
          <div className="flex gap-2 overflow-x-auto">
            {categoryFilters.map((filter) => (
              <button
                key={filter}
                onClick={() => setSelectedCategory(filter)}
                className={`px-4 py-2 rounded-xl text-sm whitespace-nowrap transition-all ${
                  selectedCategory === filter
                    ? 'bg-gradient-to-r from-blue-500 to-purple-500'
                    : 'glass-card hover:bg-white/5'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4" style={{ position: 'relative', zIndex: 1 }}>
        {[
          { label: 'Total Positions', value: totalCount.toString() },
          { label: 'New This Week', value: newThisWeek.toString() },
          { label: 'High Match', value: internships.filter(i => i.match >= 70).length.toString() },
          { label: 'Saved', value: bookmarked.length.toString() },
        ].map((stat, idx) => (
          <GlassCard key={idx}>
            <p className="text-white/60 text-sm mb-1">{stat.label}</p>
            <p className="text-2xl font-bold">{stat.value}</p>
          </GlassCard>
        ))}
      </div>

      {loading && (
        <div className="text-center py-12 text-white/60">Loading internships...</div>
      )}

      {!loading && displayList.length === 0 && (
        <GlassCard className="text-center py-12">
          <Briefcase className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2">No matches found</h3>
          <p className="text-white/60">Try adjusting your filters or search terms</p>
        </GlassCard>
      )}

      {/* Internship Listings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {displayList.map((internship) => (
          <GlassCard key={internship.id} hover>
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl glass-card flex flex-col items-center justify-center overflow-hidden p-1">
                  {internship.logo ? (
                    <img
                      src={internship.logo}
                      alt={internship.sourceName}
                      className="w-full h-full object-contain"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    <span className="text-lg">??</span>
                  )}
                </div>
                <div>
                  <h3 className="font-semibold mb-1">{internship.position}</h3>
                  <p className="text-sm text-white/60">{internship.company}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Match badge */}
                <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                  isSearchMode
                    ? (searchScores[String(internship.id)] || 0) >= 80
                      ? 'bg-green-500/20 text-green-400'
                      : (searchScores[String(internship.id)] || 0) >= 60
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'bg-purple-500/20 text-purple-400'
                    : internship.match >= 80
                    ? 'bg-green-500/20 text-green-400'
                    : internship.match >= 70
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-purple-500/20 text-purple-400'
                }`}>
                  {isSearchMode
                    ? `${searchScores[String(internship.id)] || '--'}% Relevant`
                    : `${internship.match}% Match`
                  }
                </div>
                <button
                  onClick={() => toggleBookmark(internship.id)}
                  className={`p-2 rounded-lg transition-colors ${bookmarked.includes(internship.id) ? 'bg-yellow-500/20 text-yellow-400' : 'hover:bg-white/5'}`}
                >
                  <Bookmark className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="flex items-center gap-2 text-sm text-white/60">
                <MapPin className="w-4 h-4" />
                {internship.location}
              </div>
              <div className="flex items-center gap-2 text-sm text-white/60">
                <Briefcase className="w-4 h-4" />
                {internship.type}
              </div>
              <div className="flex items-center gap-2 text-sm text-white/60">
                <DollarSign className="w-4 h-4" />
                {internship.salary}
              </div>
              <div className="flex items-center gap-2 text-sm text-white/60">
                <Clock className="w-4 h-4" />
                {internship.posted}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              {internship.tags.map((tag: any, idx: number) => (
                <span key={idx} className="px-3 py-1 bg-white/5 rounded-lg text-xs">{tag}</span>
              ))}
            </div>

            <div className="flex gap-2">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => handleTrack(internship.id)}
                className="flex-1 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-2 text-sm font-medium"
              >
                Quick Apply
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => window.open(internship.url, '_blank')}
                className="glass-card px-4 py-2 rounded-xl"
              >
                <ExternalLink className="w-4 h-4" />
              </motion.button>
            </div>

            {/* Why this matches you */}
            <button
              onClick={() => handleExplain(internship.id)}
              className="w-full mt-2 text-xs text-blue-400 hover:text-blue-300 flex items-center justify-center gap-1 py-1"
            >
              {loadingExplain[internship.id] ? '? Analyzing...' : expandedExplain[internship.id] ? '? Hide explanation' : '? Why this matches you?'}
            </button>
            {expandedExplain[internship.id] && explanations[internship.id] && (
              <div className="mt-2 p-3 bg-white/5 rounded-xl text-xs space-y-2">
                {explanations[internship.id].match_reasons?.length > 0 && (
                  <div>
                    <p className="text-green-400 font-medium mb-1">? Why it matches:</p>
                    <ul className="space-y-1">
                      {explanations[internship.id].match_reasons.map((r: string, i: number) => (
                        <li key={i} className="text-white/70">• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {explanations[internship.id].missing_skills?.length > 0 && (
                  <div>
                    <p className="text-orange-400 font-medium mb-1">?? Skills to learn:</p>
                    <div className="flex flex-wrap gap-1">
                      {explanations[internship.id].missing_skills.map((s: string, i: number) => (
                        <span key={i} className="px-2 py-0.5 bg-orange-500/20 text-orange-300 rounded">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {explanations[internship.id].tip && (
                  <p className="text-purple-300 italic">?? {explanations[internship.id].tip}</p>
                )}
              </div>
            )}
          </GlassCard>
        ))}
      </div>

      {/* Load More */}
      <div className="text-center">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleLoadMore}
          disabled={scraping}
          className="glass-card px-8 py-3 rounded-xl font-medium disabled:opacity-70"
        >
          {scraping ? (
            <span className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Finding fresh opportunities for you...
            </span>
          ) : page < totalPages ? (
            'Load More Opportunities'
          ) : (
            'Find More Opportunities'
          )}
        </motion.button>
      </div>
    </div>
  );
}

export { Internships };















