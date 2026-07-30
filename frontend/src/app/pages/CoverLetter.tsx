import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion, AnimatePresence } from 'motion/react';
import {
  FileText, Sparkles, Check, Trash2, RefreshCw,
  Copy, ChevronDown, ChevronUp, AlertCircle,
} from 'lucide-react';
import { draftsService, internshipService } from '../lib/services';

/**
 * CoverLetter page
 *
 * All data comes from real API endpoints — no hardcoded or generated content
 * is displayed without a backend round-trip:
 *   POST /api/drafts/generate  → generate
 *   GET  /api/drafts           → list
 *   PATCH /api/drafts/:id      → save edits
 *   PATCH /api/drafts/:id/approve → approve
 *   DELETE /api/drafts/:id     → discard (soft)
 */

export function CoverLetter() {
  const [internships, setInternships] = useState<any[]>([]);
  const [selectedId, setSelectedId]   = useState<number | ''>('');

  const [generating, setGenerating]   = useState(false);
  const [genError, setGenError]       = useState<string | null>(null);

  // active draft being edited
  const [draft, setDraft]             = useState<any>(null);
  const [content, setContent]         = useState('');
  const [saving, setSaving]           = useState(false);
  const [copied, setCopied]           = useState(false);

  // past drafts panel
  const [drafts, setDrafts]           = useState<any[]>([]);
  const [loadingDrafts, setLoadingDrafts] = useState(true);
  const [showPast, setShowPast]       = useState(false);

  useEffect(() => {
    loadInternships();
    loadDrafts();
  }, []);

  const loadInternships = async () => {
    try {
      const data = await internshipService.getAll({ limit: 50 });
      setInternships(data.internships || data.items || []);
    } catch {}
  };

  const loadDrafts = async () => {
    setLoadingDrafts(true);
    try {
      const data = await draftsService.getAll();
      // Only show non-discarded drafts in the list
      setDrafts((data.drafts || []).filter((d: any) => d.status !== 'discarded'));
    } catch {}
    setLoadingDrafts(false);
  };

  // ── Generate ────────────────────────────────────────────────────────────────

  const handleGenerate = async () => {
    if (!selectedId) return;
    setGenerating(true);
    setGenError(null);
    setDraft(null);
    setContent('');
    try {
      const result = await draftsService.generate(Number(selectedId));
      setDraft(result);
      setContent(result.content || '');
      setShowPast(false);
      await loadDrafts();
    } catch (e: any) {
      const msg = e?.response?.data?.detail;
      setGenError(
        msg
          ? String(msg)
          : 'Generation failed — make sure you have uploaded a resume and the internship exists.'
      );
    }
    setGenerating(false);
  };

  // ── Save / Approve / Discard ─────────────────────────────────────────────────

  const handleSave = async (): Promise<boolean> => {
    if (!draft) return false;
    setSaving(true);
    try {
      const updated = await draftsService.update(draft.id, content);
      setDraft(updated);
      await loadDrafts();
      setSaving(false);
      return true;
    } catch {
      setSaving(false);
      return false;
    }
  };

  const handleApprove = async () => {
    const saved = await handleSave();
    if (!saved) return;
    try {
      const approved = await draftsService.approve(draft.id);
      setDraft(approved);
      await loadDrafts();
    } catch {}
  };

  const handleDiscard = async (id: number) => {
    try {
      await draftsService.discard(id);
      if (draft?.id === id) { setDraft(null); setContent(''); }
      await loadDrafts();
    } catch {}
  };

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const openDraft = (d: any) => {
    setDraft(d);
    setContent(d.content || '');
    setGenError(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const selectedInternship = internships.find(i => i.id === selectedId);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold mb-2 gradient-text">Cover Letter Generator</h1>
        <p className="text-white/60">
          AI generates a personalised letter from your resume and the job description.
          Edit freely, then approve when ready.
        </p>
      </div>

      {/* ── Generator card ────────────────────────────────────────────────── */}
      <GlassCard>
        <h2 className="text-xl font-semibold mb-6">Generate New Cover Letter</h2>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-white/60 mb-2 block">Select Internship</label>
            <select
              value={selectedId}
              onChange={e => setSelectedId(e.target.value ? Number(e.target.value) : '')}
              className="w-full border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500/50 cursor-pointer"
              style={{ background: '#1a1a2e' }}
            >
              <option value="" style={{ background: '#1a1a2e' }}>Choose an internship…</option>
              {internships.map(i => (
                <option key={i.id} value={i.id} style={{ background: '#1a1a2e' }}>
                  {i.title} — {i.company}
                </option>
              ))}
            </select>
            {selectedInternship && (
              <p className="text-xs text-white/40 mt-1 ml-1">
                {selectedInternship.location} · {selectedInternship.source}
              </p>
            )}
          </div>

          {genError && (
            <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{genError}</p>
            </div>
          )}

          <motion.button
            whileHover={generating || !selectedId ? {} : { scale: 1.02 }}
            whileTap={generating || !selectedId ? {} : { scale: 0.98 }}
            onClick={handleGenerate}
            disabled={generating || !selectedId}
            className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {generating ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> Generating with AI…</>
            ) : (
              <><Sparkles className="w-4 h-4" /> Generate Cover Letter</>
            )}
          </motion.button>
        </div>
      </GlassCard>

      {/* ── Generated / editing draft ────────────────────────────────────── */}
      <AnimatePresence>
        {draft && (
          <motion.div
            key={draft.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <GlassCard>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold">Cover Letter</h2>
                  {draft.status === 'approved' && (
                    <span className="text-xs px-3 py-1 bg-green-500/20 text-green-400 rounded-full flex items-center gap-1">
                      <Check className="w-3 h-3" /> Approved
                    </span>
                  )}
                </div>
                <button
                  onClick={handleCopy}
                  className="text-xs px-3 py-1 glass-card rounded-lg hover:bg-white/10 transition-colors flex items-center gap-1.5"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>

              {/* Editable content */}
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                rows={20}
                spellCheck
                className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm leading-relaxed focus:outline-none focus:border-blue-500/50 resize-y font-mono"
              />

              <p className="text-xs text-white/40 mt-2 mb-4">
                Edit freely above. Your changes are saved to the draft when you click Save or Approve.
              </p>

              {/* Action row */}
              <div className="flex gap-3">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 glass-card py-2.5 rounded-xl text-sm font-medium hover:bg-white/10 transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving…' : 'Save Changes'}
                </motion.button>

                {draft.status !== 'approved' && (
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleApprove}
                    disabled={saving}
                    className="flex-1 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" /> Approve & Save
                  </motion.button>
                )}

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleDiscard(draft.id)}
                  title="Discard this draft"
                  className="px-4 glass-card rounded-xl hover:bg-red-500/10 hover:border-red-500/30 transition-colors text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </motion.button>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Past drafts ──────────────────────────────────────────────────── */}
      <GlassCard>
        <button
          className="w-full flex items-center justify-between"
          onClick={() => setShowPast(!showPast)}
        >
          <h2 className="text-xl font-semibold">Past Drafts</h2>
          <div className="flex items-center gap-2 text-white/60">
            <span className="text-sm">{drafts.length} saved</span>
            {showPast
              ? <ChevronUp className="w-4 h-4" />
              : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        <AnimatePresence>
          {showPast && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-4 space-y-3">
                {loadingDrafts ? (
                  <p className="text-sm text-white/60 text-center py-6">Loading drafts…</p>
                ) : drafts.length === 0 ? (
                  <p className="text-sm text-white/60 text-center py-6">
                    No saved drafts yet — generate your first one above.
                  </p>
                ) : (
                  drafts.map((d: any) => (
                    <div
                      key={d.id}
                      className="glass-card p-4 rounded-xl flex items-start justify-between gap-4"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <FileText className="w-4 h-4 text-blue-400 flex-shrink-0" />
                          <p className="text-sm font-medium">Draft #{d.id}</p>
                          {d.status === 'approved' && (
                            <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">
                              Approved
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-white/50 line-clamp-2 mb-1">
                          {(d.content || '').slice(0, 140)}…
                        </p>
                        {d.created_at && (
                          <p className="text-xs text-white/30">
                            {new Date(d.created_at).toLocaleDateString('en-IN', {
                              day: 'numeric', month: 'short', year: 'numeric',
                            })}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => openDraft(d)}
                          className="text-xs px-3 py-1.5 glass-card rounded-lg hover:bg-white/10 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDiscard(d.id)}
                          title="Discard"
                          className="text-xs p-1.5 glass-card rounded-lg hover:bg-red-500/10 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </div>
  );
}
