import { useState, useEffect, useMemo, useCallback, useRef, type ReactNode } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  Building2, Calendar, Plus, Trash2, X, Search, Loader2,
} from 'lucide-react';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { applicationService, recommendationService, internshipService } from '../lib/services';
import { CompanyAvatar } from '../components/CompanyAvatar';

// ─── Constants ────────────────────────────────────────────────────────────────

const DRAG_TYPE = 'APPLICATION_CARD';

const COLUMNS = [
  { id: 'saved',     title: 'Saved',     dot: 'bg-blue-500',   ring: 'ring-blue-400/50',   badge: 'bg-blue-500/20 text-blue-300',   textColor: 'text-blue-300'   },
  { id: 'applied',   title: 'Applied',   dot: 'bg-purple-500', ring: 'ring-purple-400/50', badge: 'bg-purple-500/20 text-purple-300', textColor: 'text-purple-300' },
  { id: 'interview', title: 'Interview', dot: 'bg-cyan-500',   ring: 'ring-cyan-400/50',   badge: 'bg-cyan-500/20 text-cyan-300',   textColor: 'text-cyan-300'   },
  { id: 'offer',     title: 'Offer',     dot: 'bg-green-500',  ring: 'ring-green-400/50',  badge: 'bg-green-500/20 text-green-300', textColor: 'text-green-300'  },
  { id: 'rejected',  title: 'Rejected',  dot: 'bg-red-500',    ring: 'ring-red-400/50',    badge: 'bg-red-500/20 text-red-300',     textColor: 'text-red-300'    },
] as const;

type ColId = typeof COLUMNS[number]['id'];

// ─── Types ────────────────────────────────────────────────────────────────────

interface AppCard {
  id: number;
  internship_id: number;
  company: string;
  position: string;
  date: string;
  status: ColId;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function mapApp(raw: any): AppCard {
  return {
    id: raw.id,
    internship_id: raw.internship?.id ?? raw.internship_id ?? 0,
    company: raw.internship?.company || 'Unknown Company',
    position: raw.internship?.title || 'Unknown Position',
    date: new Date(raw.created_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    }),
    status: raw.status as ColId,
  };
}

function colMeta(id: ColId) {
  return COLUMNS.find(c => c.id === id) ?? COLUMNS[0];
}

// ─── Draggable card ───────────────────────────────────────────────────────────

interface CardProps {
  app: AppCard;
  onDelete: (id: number) => void;
}

function DraggableCard({ app, onDelete }: CardProps) {
  const [{ isDragging }, drag] = useDrag({
    type: DRAG_TYPE,
    item: { id: app.id, fromStatus: app.status },
    collect: (m) => ({ isDragging: m.isDragging() }),
  });

  return (
    <div
      ref={drag}
      style={{ opacity: isDragging ? 0.25 : 1, cursor: isDragging ? 'grabbing' : 'grab' }}
      className="glass-card p-4 rounded-xl border border-white/10 hover:border-white/20 transition-all select-none group"
    >
      <div className="flex items-start gap-3">
        <CompanyAvatar
          name={app.company}
          className="w-9 h-9 rounded-lg flex-shrink-0 text-sm"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-tight truncate">{app.company}</p>
          <p className="text-xs text-white/50 truncate mt-0.5">{app.position}</p>
        </div>
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onDelete(app.id); }}
          className="p-1 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-all flex-shrink-0"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-white/35">
        <Calendar className="w-3 h-3" />
        <span>{app.date}</span>
      </div>
    </div>
  );
}

// ─── Droppable column ─────────────────────────────────────────────────────────

interface ColumnProps {
  col: typeof COLUMNS[number];
  apps: AppCard[];
  onDrop: (id: number, fromStatus: ColId, toStatus: ColId) => void;
  onDelete: (id: number) => void;
  onAddManually: (status: ColId) => void;
}

function DroppableColumn({ col, apps, onDrop, onDelete, onAddManually }: ColumnProps) {
  const [{ isOver }, drop] = useDrop({
    accept: DRAG_TYPE,
    drop: (item: { id: number; fromStatus: ColId }) => {
      if (item.fromStatus !== col.id) {
        onDrop(item.id, item.fromStatus, col.id);
      }
    },
    collect: (m) => ({ isOver: m.isOver() }),
  });

  return (
    <div className="flex flex-col min-w-[220px] flex-1">
      <div className="flex items-center gap-2 mb-3 px-1">
        <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${col.dot}`} />
        <span className="font-semibold text-sm">{col.title}</span>
        <span className="text-xs text-white/35 bg-white/5 px-1.5 py-0.5 rounded-full ml-auto">
          {apps.length}
        </span>
      </div>

      <div
        ref={drop}
        className={`flex-1 min-h-[100px] rounded-xl p-2 space-y-2 transition-all duration-150 border-2 ${
          isOver
            ? `border-dashed ring-2 ${col.ring} border-white/10 bg-white/[0.02]`
            : 'border-transparent'
        }`}
      >
        {apps.map(app => (
          <DraggableCard key={app.id} app={app} onDelete={onDelete} />
        ))}

        <button
          onClick={() => onAddManually(col.id)}
          className="w-full p-2.5 rounded-xl text-xs text-white/25 hover:text-white/60 hover:bg-white/5 transition-colors flex items-center justify-center gap-1.5 border border-dashed border-white/10 hover:border-white/25"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Manually
        </button>
      </div>
    </div>
  );
}

// ─── Modal shell ──────────────────────────────────────────────────────────────

interface ModalShellProps {
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}

function ModalShell({ title, subtitle, onClose, children }: ModalShellProps) {
  useEffect(() => {
    const handle = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-md rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col"
        style={{ background: 'rgba(8,8,20,0.98)', backdropFilter: 'blur(20px)', maxHeight: '80vh' }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 flex-shrink-0">
          <div>
            <h3 className="font-semibold text-base">{title}</h3>
            {subtitle && <div className="text-xs text-white/40 mt-0.5">{subtitle}</div>}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          {children}
        </div>
      </div>
    </div>
  );
}

// ─── Add Recommendation Modal ─────────────────────────────────────────────────
// Triggered by top "Add Application" button.
// Shows AI-matched recs >= 50%, grouped Top/Good, always adds to SAVED.

interface AddRecModalProps {
  existingInternshipIds: Set<number>;
  onClose: () => void;
  onAdded: (app: AppCard) => void;
}

function AddRecommendationModal({ existingInternshipIds, onClose, onAdded }: AddRecModalProps) {
  const [query, setQuery] = useState('');
  const [recs, setRecs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    recommendationService.get()
      .then(d => setRecs(d.recommendations || []))
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return recs
      .filter(r =>
        (r.match_percentage ?? 0) >= 50 &&
        !existingInternshipIds.has(r.internship_id) &&
        (!q ||
          (r.company || '').toLowerCase().includes(q) ||
          (r.title || '').toLowerCase().includes(q))
      )
      .sort((a, b) => (b.match_percentage ?? 0) - (a.match_percentage ?? 0));
  }, [recs, query, existingInternshipIds]);

  const topMatches  = filtered.filter(r => (r.match_percentage ?? 0) >= 70);
  const goodMatches = filtered.filter(r => (r.match_percentage ?? 0) <  70);

  const handleAdd = async (rec: any) => {
    if (adding !== null) return;
    setAdding(rec.internship_id);
    setError('');
    try {
      const created = await applicationService.create(rec.internship_id, 'saved');
      onAdded({
        id: created.id,
        internship_id: rec.internship_id,
        company: created.internship?.company || rec.company || 'Unknown Company',
        position: created.internship?.title || rec.title || 'Unknown Position',
        date: new Date(created.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
        }),
        status: 'saved',
      });
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to add. Please try again.');
      setAdding(null);
    }
  };

  const RecRow = ({ rec }: { rec: any }) => {
    const pct = Math.floor(rec.match_percentage ?? 0);
    const isTop = pct >= 70;
    return (
      <button
        onClick={() => handleAdd(rec)}
        disabled={adding !== null}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left disabled:opacity-50 group"
      >
        <CompanyAvatar
          name={rec.company || 'Unknown'}
          className="w-9 h-9 rounded-lg flex-shrink-0 text-sm"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-tight truncate">
            {rec.title || rec.company || 'Unknown Position'}
          </p>
          <p className="text-xs text-white/45 truncate">{rec.company || 'Unknown Company'}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
            isTop ? 'bg-green-500/15 text-green-400' : 'bg-blue-500/15 text-blue-400'
          }`}>
            {pct}%
          </span>
          {adding === rec.internship_id ? (
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
          ) : (
            <Plus className="w-4 h-4 text-white/15 group-hover:text-blue-400 transition-colors" />
          )}
        </div>
      </button>
    );
  };

  return (
    <ModalShell
      title="Add Application"
      subtitle="Adding to Saved — drag to move between columns"
      onClose={onClose}
    >
      <div className="px-4 pt-4 pb-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search matched internships…"
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>
        {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
      </div>

      <div className="pb-3">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-white/40">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Loading recommendations…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center px-4">
            <Building2 className="w-10 h-10 text-white/15 mx-auto mb-2" />
            <p className="text-sm text-white/40">
              {recs.filter(r => (r.match_percentage ?? 0) >= 50).length === 0
                ? 'No quality matches yet — refresh on the Internships page first'
                : 'No results match your search'}
            </p>
          </div>
        ) : (
          <>
            {topMatches.length > 0 && (
              <>
                <div className="px-4 py-2 text-[11px] font-semibold text-white/30 uppercase tracking-wider">
                  ⭐ Top Matches — ≥70%
                </div>
                {topMatches.map(rec => <RecRow key={rec.internship_id} rec={rec} />)}
              </>
            )}
            {goodMatches.length > 0 && (
              <>
                <div className="px-4 py-2 text-[11px] font-semibold text-white/30 uppercase tracking-wider mt-1">
                  Good Matches — 50–70%
                </div>
                {goodMatches.map(rec => <RecRow key={rec.internship_id} rec={rec} />)}
              </>
            )}
          </>
        )}
      </div>
    </ModalShell>
  );
}

// ─── Add Manually Modal ───────────────────────────────────────────────────────
// Triggered by per-column "Add Manually" button.
// Debounced search across all internships; status fixed to the column.

interface AddManualModalProps {
  targetStatus: ColId;
  existingInternshipIds: Set<number>;
  onClose: () => void;
  onAdded: (app: AppCard) => void;
}

function AddManualModal({ targetStatus, existingInternshipIds, onClose, onAdded }: AddManualModalProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<number | null>(null);
  const [error, setError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const col = colMeta(targetStatus);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) { setResults([]); return; }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await internshipService.getAll({ search: query, limit: 20 });
        const all = (data.internships || data.items || []) as any[];
        setResults(all.filter((r: any) => !existingInternshipIds.has(r.id)));
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, existingInternshipIds]);

  const handleAdd = async (internship: any) => {
    if (adding !== null) return;
    setAdding(internship.id);
    setError('');
    try {
      const created = await applicationService.create(internship.id, targetStatus);
      onAdded({
        id: created.id,
        internship_id: internship.id,
        company: created.internship?.company || internship.company || 'Unknown Company',
        position: created.internship?.title || internship.title || 'Unknown Position',
        date: new Date(created.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
        }),
        status: targetStatus,
      });
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to add. Please try again.');
      setAdding(null);
    }
  };

  return (
    <ModalShell
      title="Add Manually"
      subtitle={
        <span>
          Adding to{' '}
          <span className={`font-semibold ${col.textColor}`}>{col.title}</span>
        </span>
      }
      onClose={onClose}
    >
      <div className="px-4 pt-4 pb-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search all internships by title or company…"
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>
        {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
      </div>

      <div className="pb-3">
        {!query.trim() ? (
          <div className="py-10 text-center text-white/30 text-sm">
            Start typing to search internships
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-white/40">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Searching…</span>
          </div>
        ) : results.length === 0 ? (
          <div className="py-10 text-center px-4">
            <Search className="w-8 h-8 text-white/15 mx-auto mb-2" />
            <p className="text-sm text-white/40">No internships found for "{query}"</p>
          </div>
        ) : (
          results.map((item: any) => (
            <button
              key={item.id}
              onClick={() => handleAdd(item)}
              disabled={adding !== null}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left disabled:opacity-50 group"
            >
              <CompanyAvatar
                name={item.company || 'Unknown'}
                className="w-9 h-9 rounded-lg flex-shrink-0 text-sm"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-tight truncate">
                  {item.title || 'Unknown Position'}
                </p>
                <p className="text-xs text-white/45 truncate">
                  {item.company || 'Unknown Company'}{item.location ? ` · ${item.location}` : ''}
                </p>
              </div>
              <div className="flex-shrink-0">
                {adding === item.id ? (
                  <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                ) : (
                  <Plus className="w-4 h-4 text-white/15 group-hover:text-blue-400 transition-colors" />
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </ModalShell>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type ModalKind =
  | { type: 'recommendations' }
  | { type: 'manual'; status: ColId }
  | null;

export function ApplicationsTracker() {
  const [apps, setApps] = useState<AppCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<ModalKind>(null);

  useEffect(() => { loadApps(); }, []);

  const loadApps = async () => {
    setLoading(true);
    try {
      const data = await applicationService.getAll();
      // Deduplicate by id — guard against any server-side inconsistency
      const seen = new Set<number>();
      const unique: AppCard[] = [];
      for (const raw of (data.applications || [])) {
        if (!seen.has(raw.id)) {
          seen.add(raw.id);
          unique.push(mapApp(raw));
        }
      }
      setApps(unique);
    } catch {
      setApps([]);
    }
    setLoading(false);
  };

  // ── Drag-and-drop ──────────────────────────────────────────────────────────
  const handleDrop = useCallback(async (id: number, fromStatus: ColId, toStatus: ColId) => {
    if (fromStatus === toStatus) return;
    setApps(prev => prev.map(a => a.id === id ? { ...a, status: toStatus } : a));
    try {
      await applicationService.update(id, { status: toStatus });
    } catch {
      setApps(prev => prev.map(a => a.id === id ? { ...a, status: fromStatus } : a));
    }
  }, []);

  // ── Delete ─────────────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (id: number) => {
    setApps(prev => prev.filter(a => a.id !== id));
    try {
      await applicationService.delete(id);
    } catch {
      loadApps();
    }
  }, []);

  // ── onAdded — shared by both modals ───────────────────────────────────────
  const handleAdded = useCallback((newApp: AppCard) => {
    setApps(prev => prev.some(a => a.id === newApp.id) ? prev : [newApp, ...prev]);
    setModal(null);
  }, []);

  const existingInternshipIds = useMemo(
    () => new Set(apps.map(a => a.internship_id)),
    [apps],
  );

  const byStatus = useCallback(
    (id: ColId) => apps.filter(a => a.status === id),
    [apps],
  );

  // Stats derive from apps — single source of truth, no separate counters
  const stats = useMemo(() => COLUMNS.map(c => ({
    ...c,
    count: apps.filter(a => a.status === c.id).length,
  })), [apps]);

  // Recent activity: most recent 6 by ID (server returns updated_at desc)
  const recentApps = useMemo(
    () => [...apps].sort((a, b) => b.id - a.id).slice(0, 6),
    [apps],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  return (
    <DndProvider backend={HTML5Backend}>
      {modal?.type === 'recommendations' && (
        <AddRecommendationModal
          existingInternshipIds={existingInternshipIds}
          onClose={() => setModal(null)}
          onAdded={handleAdded}
        />
      )}
      {modal?.type === 'manual' && (
        <AddManualModal
          targetStatus={modal.status}
          existingInternshipIds={existingInternshipIds}
          onClose={() => setModal(null)}
          onAdded={handleAdded}
        />
      )}

      <div className="space-y-8 p-6">
        {/* Page header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2 gradient-text">Applications Tracker</h1>
            <p className="text-white/55">Drag cards between columns as your status changes</p>
          </div>
          <motion.button
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => setModal({ type: 'recommendations' })}
            className="bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2.5 rounded-xl flex items-center gap-2 text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Add Application
          </motion.button>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {stats.map(s => (
            <GlassCard key={s.id} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/50 text-xs mb-1">{s.title}</p>
                  <p className="text-2xl font-bold">{s.count}</p>
                </div>
                <div className={`w-2 h-10 rounded-full ${s.dot}`} />
              </div>
            </GlassCard>
          ))}
        </div>

        {/* Empty state */}
        {apps.length === 0 && (
          <GlassCard className="text-center py-14">
            <Building2 className="w-14 h-14 text-white/15 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">No applications yet</h3>
            <p className="text-white/50 mb-5">
              Start tracking internships from your AI-matched recommendations
            </p>
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => setModal({ type: 'recommendations' })}
              className="bg-gradient-to-r from-blue-500 to-purple-500 px-5 py-2.5 rounded-xl inline-flex items-center gap-2 text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              Add First Application
            </motion.button>
          </GlassCard>
        )}

        {/* Kanban board */}
        {apps.length > 0 && (
          <div className="overflow-x-auto pb-4">
            <div className="flex gap-4 min-w-max">
              {COLUMNS.map(col => (
                <div key={col.id} className="w-[240px]">
                  <DroppableColumn
                    col={col}
                    apps={byStatus(col.id)}
                    onDrop={handleDrop}
                    onDelete={handleDelete}
                    onAddManually={(status) => setModal({ type: 'manual', status })}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Activity */}
        {apps.length > 0 && (
          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold mb-5">Recent Activity</h3>
            <div className="space-y-4">
              {recentApps.map((app, idx) => {
                const meta = colMeta(app.status);
                return (
                  <div key={app.id} className="flex items-start gap-4">
                    <div className="relative flex-shrink-0">
                      <CompanyAvatar
                        name={app.company}
                        className="w-9 h-9 rounded-full text-sm"
                      />
                      {idx < recentApps.length - 1 && (
                        <div className="absolute top-9 left-1/2 -translate-x-1/2 w-px h-6 bg-white/10" />
                      )}
                    </div>
                    <div className="flex-1 glass-card p-4 rounded-xl min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-medium text-sm truncate">{app.position}</p>
                          <p className="text-xs text-white/50 truncate">{app.company}</p>
                        </div>
                        <span className="text-xs text-white/35 flex-shrink-0">{app.date}</span>
                      </div>
                      <div className="mt-2">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${meta.badge}`}>
                          {meta.title}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </GlassCard>
        )}
      </div>
    </DndProvider>
  );
}
