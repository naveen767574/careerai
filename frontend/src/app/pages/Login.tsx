import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, Mail, Lock, ArrowRight, ArrowLeft, KeyRound, CheckCircle2, Copy, Eye, EyeOff } from 'lucide-react';
import { Link, useNavigate } from 'react-router';
import { authService } from '../lib/auth';
import api from '../lib/api';

type View = 'login' | 'forgot-email' | 'forgot-token' | 'forgot-done';

export function Login() {
  const navigate  = useNavigate();
  const [view, setView] = useState<View>('login');

  // Login
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  // Forgot — step 1
  const [forgotEmail,   setForgotEmail]   = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotError,   setForgotError]   = useState('');

  // Forgot — step 2  (token shown + new password)
  const [resetToken,   setResetToken]   = useState('');
  const [tokenInput,   setTokenInput]   = useState('');
  const [newPassword,  setNewPassword]  = useState('');
  const [showNewPw,    setShowNewPw]    = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError,   setResetError]   = useState('');
  const [copied,       setCopied]       = useState(false);

  // ── Login handler ──────────────────────────────────────────────────────────
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await authService.login(email, password);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── Forgot step 1: request token ───────────────────────────────────────────
  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotLoading(true);
    setForgotError('');
    try {
      const res = await api.post('/auth/request-reset', { email: forgotEmail });
      const token: string | null = res.data.reset_token ?? null;
      if (token) {
        // Email found — pre-fill token and advance to step 2
        setResetToken(token);
        setTokenInput(token);
        setView('forgot-token');
      } else {
        // Email not registered — show a gentle message, don't advance
        // (backend always returns 200 to prevent email enumeration)
        setForgotError('No account found for that email address. Please check and try again.');
      }
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 429) {
        setForgotError(err.response.data.detail || 'Too many attempts. Please wait before trying again.');
      } else {
        setForgotError('Something went wrong. Please try again.');
      }
    } finally {
      setForgotLoading(false);
    }
  };

  // ── Forgot step 2: set new password ───────────────────────────────────────
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setResetError('Password must be at least 6 characters.');
      return;
    }
    setResetLoading(true);
    setResetError('');
    try {
      await api.post('/auth/reset-password', {
        token: tokenInput,
        new_password: newPassword,
      });
      setView('forgot-done');
    } catch (err: any) {
      setResetError(err.response?.data?.detail || 'Reset failed. Please try again.');
    } finally {
      setResetLoading(false);
    }
  };

  const copyToken = () => {
    navigator.clipboard.writeText(resetToken).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const goBack = () => {
    setView('login');
    setForgotEmail('');
    setForgotError('');
    setResetToken('');
    setTokenInput('');
    setNewPassword('');
    setResetError('');
  };

  // ── Shared background ──────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative overflow-hidden">
      <div className="absolute inset-0 mesh-gradient opacity-30" />
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 8, repeat: Infinity }}
        className="absolute top-20 left-20 w-96 h-96 bg-blue-500 rounded-full blur-3xl"
      />
      <motion.div
        animate={{ scale: [1.2, 1, 1.2], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 8, repeat: Infinity, delay: 1 }}
        className="absolute bottom-20 right-20 w-96 h-96 bg-purple-500 rounded-full blur-3xl"
      />

      <AnimatePresence mode="wait">

        {/* ── LOGIN VIEW ──────────────────────────────────────────────────── */}
        {view === 'login' && (
          <motion.div key="login"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            className="glass-card rounded-3xl p-12 w-full max-w-md relative z-10"
          >
            <div className="flex items-center justify-center gap-2 mb-8">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <h1 className="text-3xl font-bold gradient-text">CareerAI</h1>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">Welcome Back</h2>
              <p className="text-white/60">Sign in to continue your career journey</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Email</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input type="email" placeholder="john@example.com"
                    value={email} onChange={e => setEmail(e.target.value)} required
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input type={showPw ? 'text' : 'password'} placeholder="••••••••"
                    value={password} onChange={e => setPassword(e.target.value)} required
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-10 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                  <button type="button" onClick={() => setShowPw(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded border-white/20" />
                  <span className="text-sm text-white/60">Remember me</span>
                </label>
                <button type="button" onClick={() => setView('forgot-email')}
                  className="text-sm text-blue-400 hover:text-blue-300 transition-colors">
                  Forgot password?
                </button>
              </div>

              {error && <p className="text-red-400 text-sm text-center">{error}</p>}

              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                type="submit" disabled={loading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 font-medium flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-60">
                {loading ? 'Signing in…' : 'Sign In'}
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-white/60">
                Don't have an account?{' '}
                <Link to="/register" className="text-blue-400 hover:text-blue-300 font-medium">Sign up</Link>
              </p>
            </div>
          </motion.div>
        )}

        {/* ── FORGOT — STEP 1: enter email ────────────────────────────────── */}
        {view === 'forgot-email' && (
          <motion.div key="forgot-email"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            className="glass-card rounded-3xl p-12 w-full max-w-md relative z-10"
          >
            <button onClick={goBack}
              className="flex items-center gap-1 text-sm text-white/50 hover:text-white/80 transition-colors mb-8">
              <ArrowLeft className="w-4 h-4" /> Back to login
            </button>

            <div className="flex items-center justify-center mb-6">
              <div className="w-14 h-14 rounded-2xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                <KeyRound className="w-7 h-7 text-blue-400" />
              </div>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">Reset Password</h2>
              <p className="text-white/60 text-sm">Enter the email address linked to your account. We'll generate a reset token for you instantly.</p>
            </div>

            <form onSubmit={handleRequestReset} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-2">Email address</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input type="email" placeholder="john@example.com" autoFocus
                    value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} required
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                </div>
              </div>

              {forgotError && <p className="text-red-400 text-sm text-center">{forgotError}</p>}

              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                type="submit" disabled={forgotLoading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 font-medium flex items-center justify-center gap-2 disabled:opacity-60">
                {forgotLoading ? 'Generating token…' : 'Get Reset Token'}
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </form>
          </motion.div>
        )}

        {/* ── FORGOT — STEP 2: show token + set new password ──────────────── */}
        {view === 'forgot-token' && (
          <motion.div key="forgot-token"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            className="glass-card rounded-3xl p-10 w-full max-w-md relative z-10"
          >
            <button onClick={goBack}
              className="flex items-center gap-1 text-sm text-white/50 hover:text-white/80 transition-colors mb-6">
              <ArrowLeft className="w-4 h-4" /> Back to login
            </button>

            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold mb-1">Set New Password</h2>
              <p className="text-white/60 text-sm">Your reset token is ready. Set your new password below.</p>
            </div>

            {/* Token display box */}
            <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-blue-300 font-medium uppercase tracking-wide">Reset Token</p>
                <button onClick={copyToken}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors">
                  <Copy className="w-3 h-3" />
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <p className="text-[10px] font-mono text-white/70 break-all leading-relaxed">
                {resetToken}
              </p>
              <p className="text-[10px] text-white/40 mt-2">This token is pre-filled in the field below. Valid for 1 hour.</p>
            </div>

            <form onSubmit={handleResetPassword} className="space-y-4">
              {/* Token input — pre-filled, editable in case user has a different token */}
              <div>
                <label className="block text-sm font-medium mb-2">Reset Token</label>
                <div className="relative">
                  <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input type="text"
                    value={tokenInput} onChange={e => setTokenInput(e.target.value)} required
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 text-xs font-mono focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">New Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                  <input type={showNewPw ? 'text' : 'password'} placeholder="Min. 6 characters" autoFocus
                    value={newPassword} onChange={e => setNewPassword(e.target.value)} required minLength={6}
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-10 py-3 focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                  <button type="button" onClick={() => setShowNewPw(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors">
                    {showNewPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {resetError && <p className="text-red-400 text-sm text-center">{resetError}</p>}

              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                type="submit" disabled={resetLoading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 font-medium flex items-center justify-center gap-2 disabled:opacity-60">
                {resetLoading ? 'Resetting…' : 'Reset Password'}
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </form>
          </motion.div>
        )}

        {/* ── FORGOT — DONE ────────────────────────────────────────────────── */}
        {view === 'forgot-done' && (
          <motion.div key="forgot-done"
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
            className="glass-card rounded-3xl p-12 w-full max-w-md relative z-10 text-center"
          >
            <div className="flex items-center justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-green-500/20 border border-green-500/30 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-green-400" />
              </div>
            </div>
            <h2 className="text-2xl font-bold mb-2">Password Reset!</h2>
            <p className="text-white/60 mb-8">Your password has been updated successfully. You can now sign in with your new password.</p>
            <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={goBack}
              className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 font-medium flex items-center justify-center gap-2">
              Back to Login <ArrowRight className="w-5 h-5" />
            </motion.button>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
}
