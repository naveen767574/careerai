import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { motion } from 'motion/react';
import {
  LayoutDashboard,
  FileText,
  Briefcase,
  TrendingUp,
  KanbanSquare,
  MessageSquare,
  Linkedin,
  
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { authService } from '../lib/auth';

const menuItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: FileText, label: 'Resume Analyzer', path: '/resume-analyzer' },
  { icon: Briefcase, label: 'Internships', path: '/internships' },
  { icon: TrendingUp, label: 'Career Paths', path: '/career-paths' },
  { icon: KanbanSquare, label: 'Applications', path: '/applications' },
  { icon: MessageSquare, label: 'Interview Prep', path: '/interview-prep' },
  { icon: Linkedin, label: 'LinkedIn Analyzer', path: '/linkedin-analyzer' },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const user = authService.getUser();
  const initials = user?.name
    ? user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 80 : 280 }}
      className="h-screen glass-card border-r border-white/10 flex flex-col relative z-10"
    >
      {/* Logo */}
      <div className="p-6 border-b border-white/10 flex items-center justify-between">
        <motion.div
          initial={false}
          animate={{ opacity: collapsed ? 0 : 1 }}
          className="flex items-center gap-2"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <h1 className="text-xl font-bold gradient-text">CareerAI</h1>
          )}
        </motion.div>
      </div>

      {/* Toggle Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-24 w-6 h-6 glass-card rounded-full flex items-center justify-center hover:bg-white/10 transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="w-4 h-4" />
        ) : (
          <ChevronLeft className="w-4 h-4" />
        )}
      </button>

      {/* Menu Items */}
      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <Link key={item.path} to={item.path}>
              <motion.div
                whileHover={{ x: 4 }}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-500/30'
                    : 'hover:bg-white/5'
                }`}
              >
                <Icon
                  className={`w-5 h-5 ${
                    isActive ? 'text-blue-400' : 'text-white/60'
                  }`}
                />
                <motion.span
                  initial={false}
                  animate={{ opacity: collapsed ? 0 : 1 }}
                  className={`text-sm ${
                    isActive ? 'text-white font-medium' : 'text-white/60'
                  }`}
                >
                  {item.label}
                </motion.span>
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/10">
        <div className={`glass-card rounded-xl p-4 flex items-center ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center font-bold text-xs flex-shrink-0">
            {initials}
          </div>
          {!collapsed && (
            <motion.div
              initial={false}
              animate={{ opacity: collapsed ? 0 : 1 }}
              className="ml-3 overflow-hidden"
            >
              <p className="text-sm font-medium truncate">{user?.name || 'User'}</p>
              <p className="text-xs text-white/60 truncate">{user?.email || ''}</p>
            </motion.div>
          )}
        </div>
      </div>
    </motion.aside>
  );
}
