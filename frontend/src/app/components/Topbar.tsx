import { useState, useRef, useEffect } from 'react';
import { Bell, Search, Settings, LogOut } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { authService } from '../lib/auth';
import { notificationService } from '../lib/services';
import { useNavigate } from 'react-router';

export function Topbar() {
  const user = authService.getUser();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notifRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadNotifications();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setShowSettings(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const loadNotifications = async () => {
    try {
      const data = await notificationService.getAll();
      const notifs = data.notifications || [];
      setNotifications(notifs);
      setUnreadCount(notifs.filter((n: any) => !n.is_read).length);
    } catch { }
  };

  const handleMarkRead = async (id: number) => {
    const notif = notifications.find(n => n.id === id);
    if (!notif || notif.is_read) return; // already read — no-op
    try {
      await notificationService.markRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationService.markAllRead();
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch { }
  };

  const timeAgo = (dateStr: string): string => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const m = Math.floor(diff / 60_000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  };

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      if (searchQuery.toLowerCase().includes('intern')) navigate('/internships');
      else if (searchQuery.toLowerCase().includes('resume')) navigate('/resume-analyzer');
      else if (searchQuery.toLowerCase().includes('career')) navigate('/career-paths');
      else if (searchQuery.toLowerCase().includes('application')) navigate('/applications');
      else if (searchQuery.toLowerCase().includes('interview')) navigate('/interview-prep');
      else if (searchQuery.toLowerCase().includes('linkedin')) navigate('/linkedin-analyzer');
      else if (searchQuery.toLowerCase().includes('builder')) navigate('/resume-builder');
      else navigate('/internships');
      setSearchQuery('');
    }
  };

  const initials = user?.name
    ? user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <div className="h-20 glass-card border-b border-white/10 flex items-center justify-between px-8" style={{ position: 'relative', zIndex: 99999 }}>
      {/* Search */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearch}
            placeholder="Search pages... (press Enter)"
            className="w-full bg-white/5 border border-white/10 rounded-xl pl-12 pr-4 py-3 text-sm focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-4">

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => { setShowNotifications(!showNotifications); setShowSettings(false); }}
            className="relative p-2 glass-card rounded-xl hover:bg-white/10 transition-colors"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 rounded-full text-xs flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </motion.button>

          <AnimatePresence>
            {showNotifications && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                style={{
                  position: 'fixed',
                  top: '60px',
                  right: '16px',
                  width: '320px',
                  zIndex: 99999,
                  background: 'rgba(10,10,25,0.98)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                  backdropFilter: 'blur(20px)',
                }}
              >
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                  <h3 className="font-semibold text-sm">Notifications</h3>
                  <button onClick={handleMarkAllRead} className="text-xs text-blue-400 hover:text-blue-300">
                    Mark all read
                  </button>
                </div>
                <div className="max-h-80 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                  {notifications.length === 0 ? (
                    <div className="py-10 text-center">
                      <Bell className="w-8 h-8 text-white/20 mx-auto mb-2" />
                      <p className="text-white/40 text-sm">No notifications yet</p>
                      <p className="text-white/25 text-xs mt-1">Run a recommendation refresh to get job alerts</p>
                    </div>
                  ) : (
                    notifications.slice(0, 15).map((n: any) => (
                      <div
                        key={n.id}
                        onClick={() => handleMarkRead(n.id)}
                        className={`flex gap-3 p-4 border-b border-white/5 transition-colors cursor-pointer hover:bg-white/5 ${!n.is_read ? 'bg-blue-500/5' : ''}`}
                      >
                        {/* Unread dot */}
                        <div className="flex-shrink-0 pt-1.5">
                          {!n.is_read
                            ? <div className="w-2 h-2 rounded-full bg-blue-400" />
                            : <div className="w-2 h-2" />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className={`text-sm leading-tight ${!n.is_read ? 'font-semibold text-white' : 'font-medium text-white/80'}`}>
                            {n.title}
                          </p>
                          <p className="text-xs text-white/55 mt-0.5 line-clamp-2">{n.message}</p>
                          <p className="text-[10px] text-white/30 mt-1">{timeAgo(n.created_at)}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>


        {/* Settings */}
        <div className="relative" ref={settingsRef}>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => { setShowSettings(!showSettings); setShowNotifications(false); }}
            className="p-2 glass-card rounded-xl hover:bg-white/10 transition-colors"
          >
            <Settings className="w-5 h-5 text-white/80" />
          </motion.button>

          <AnimatePresence>
            {showSettings && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="absolute right-0 top-12 w-48 glass-card border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden"
              >
                <div className="p-2">
                  <button
                    onClick={() => { authService.logout(); window.location.href = '/login'; }}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-red-500/20 text-red-500 dark:text-red-400 transition-colors text-sm"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* User Avatar */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-white/70">{user?.name || 'User'}</span>
          <div className="w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center font-bold text-sm">
            {initials}
          </div>
        </div>
      </div>
    </div>
  );
}









