import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { authService } from '../lib/auth';
import { applicationService, resumeService, recommendationService } from '../lib/services';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  TrendingUp,
  Briefcase,
  FileText,
  Target,
  Calendar,
  Award,
  Clock,
  CheckCircle2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const applicationData = [
  { month: 'Jan', applications: 12 },
  { month: 'Feb', applications: 19 },
  { month: 'Mar', applications: 15 },
  { month: 'Apr', applications: 24 },
  { month: 'May', applications: 18 },
  { month: 'Jun', applications: 28 },
];

export function Dashboard() {
  const navigate = useNavigate();
  const user = authService.getUser();

  const [stats, setStats] = useState([
    { label: 'Applications Sent', value: '0', change: '', icon: FileText, gradient: 'blue' },
    { label: 'Interviews Scheduled', value: '0', change: '', icon: Calendar, gradient: 'purple' },
    { label: 'Offers Received', value: '0', change: '', icon: Award, gradient: 'cyan' },
    { label: 'Response Rate', value: '0%', change: '', icon: TrendingUp, gradient: 'blue' },
  ]);

  const [skillsData, setSkillsData] = useState([
    { name: 'React', value: 90 },
    { name: 'TypeScript', value: 85 },
    { name: 'Node.js', value: 75 },
    { name: 'Python', value: 70 },
  ]);

  const [statusData, setStatusData] = useState([
    { name: 'Applied', value: 0, color: '#3B82F6' },
    { name: 'Interview', value: 0, color: '#8B5CF6' },
    { name: 'Offer', value: 0, color: '#06B6D4' },
    { name: 'Rejected', value: 0, color: '#EF4444' },
  ]);

  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [resumeScore, setResumeScore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      // Load applications
      const appsData = await applicationService.getAll();
      const apps = appsData.applications || [];

      const applied = apps.filter((a: any) => a.status === 'applied').length;
      const interviews = apps.filter((a: any) => a.status === 'interview').length;
      const offers = apps.filter((a: any) => a.status === 'offer').length;
      const rejected = apps.filter((a: any) => a.status === 'rejected').length;
      const total = apps.length;
      const responseRate = total > 0 ? Math.round(((interviews + offers) / total) * 100) : 0;

      setStats([
        { label: 'Applications Sent', value: String(total), change: '', icon: FileText, gradient: 'blue' },
        { label: 'Interviews Scheduled', value: String(interviews), change: '', icon: Calendar, gradient: 'purple' },
        { label: 'Offers Received', value: String(offers), change: '', icon: Award, gradient: 'cyan' },
        { label: 'Response Rate', value: `${responseRate}%`, change: '', icon: TrendingUp, gradient: 'blue' },
      ]);

      setStatusData([
        { name: 'Applied', value: applied || 0, color: '#3B82F6' },
        { name: 'Interview', value: interviews || 0, color: '#8B5CF6' },
        { name: 'Offer', value: offers || 0, color: '#06B6D4' },
        { name: 'Rejected', value: rejected || 0, color: '#EF4444' },
      ]);

      // Recent activity from applications
      const recent = apps.slice(0, 3).map((a: any) => ({
        type: a.status === 'interview' ? 'interview' : a.status === 'offer' ? 'offer' : 'application',
        company: a.internship?.company || 'Company',
        position: a.internship?.title || 'Position',
        time: new Date(a.updated_at).toLocaleDateString(),
      }));
      setRecentActivity(recent);
    } catch (err) {
      console.log('Applications not loaded yet');
    }

    try {
      // Load resume score and skills
      const resume = await resumeService.getMyResume();
      if (resume?.score) setResumeScore(resume.score);
      if (resume?.skills?.length > 0) {
        const topSkills = resume.skills.slice(0, 4).map((s: any) => ({
          name: typeof s === 'string' ? s : s.name,
          value: Math.floor(Math.random() * 30) + 70,
        }));
        setSkillsData(topSkills);
      }
    } catch (err) {
      console.log('Resume not loaded yet');
    }

    setLoading(false);
  };

  return (
    <div className="space-y-8 pb-8 [&::-webkit-scrollbar]:hidden">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold mb-2 gradient-text">
          Welcome back, {user?.name?.split(' ')[0] || 'there'}! 👋
        </h1>
        <p className="text-white/60">
          Here's what's happening with your career journey
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <GlassCard key={idx} hover gradient={stat.gradient as any}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-white/60 text-sm mb-1">{stat.label}</p>
                  <h3 className="text-3xl font-bold mb-1">{stat.value}</h3>
                  <p className="text-green-400 text-sm">{stat.change} from last month</p>
                </div>
                <div className="p-3 bg-white/10 rounded-xl">
                  <Icon className="w-6 h-6 text-white/80" />
                </div>
              </div>
            </GlassCard>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Application Trends */}
        <GlassCard className="lg:col-span-2">
          <h3 className="text-xl font-semibold mb-6">Application Trends</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={applicationData}>
              <defs>
                <linearGradient id="colorApplications" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="month" stroke="rgba(255,255,255,0.6)" />
              <YAxis stroke="rgba(255,255,255,0.6)" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(13, 13, 26, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                }}
              />
              <Area
                type="monotone"
                dataKey="applications"
                stroke="#3B82F6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorApplications)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        {/* Application Status */}
        <GlassCard>
          <h3 className="text-xl font-semibold mb-6">Application Status</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
              >
                {statusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(13, 13, 26, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2 mt-4">
            {statusData.map((item, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-sm text-white/60">{item.name}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Skills Progress */}
        <GlassCard className="lg:col-span-2">
          <h3 className="text-xl font-semibold mb-6">Top Skills</h3>
          <div className="space-y-4">
            {skillsData.map((skill, idx) => (
              <div key={idx}>
                <div className="flex justify-between mb-2">
                  <span className="text-sm">{skill.name}</span>
                  <span className="text-sm text-white/60">{skill.value}%</span>
                </div>
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${skill.value}%` }}
                    transition={{ duration: 1, delay: idx * 0.1 }}
                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                  />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Recent Activity */}
        <GlassCard>
          <h3 className="text-xl font-semibold mb-6">Recent Activity</h3>
          <div className="space-y-4">
            {recentActivity.map((activity, idx) => (
              <div key={idx} className="flex gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    activity.type === 'application'
                      ? 'bg-blue-500/20'
                      : activity.type === 'interview'
                      ? 'bg-purple-500/20'
                      : 'bg-cyan-500/20'
                  }`}
                >
                  {activity.type === 'application' && (
                    <FileText className="w-5 h-5 text-blue-400" />
                  )}
                  {activity.type === 'interview' && (
                    <Calendar className="w-5 h-5 text-purple-400" />
                  )}
                  {activity.type === 'offer' && (
                    <Award className="w-5 h-5 text-cyan-400" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{activity.company}</p>
                  <p className="text-xs text-white/60">{activity.position}</p>
                  <p className="text-xs text-white/40 mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Quick Actions */}
      <GlassCard>
        <h3 className="text-xl font-semibold mb-6">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { label: 'Analyze Resume', icon: FileText, color: 'blue', path: '/resume-analyzer' },
            { label: 'Find Internships', icon: Briefcase, color: 'purple', path: '/internships' },
            { label: 'Practice Interview', icon: Target, color: 'cyan', path: '/interview-prep' },
          ].map((action, idx) => {
            const Icon = action.icon;
            return (
              <motion.button
                key={idx}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => navigate(action.path)}
                className="glass-card p-6 rounded-xl hover:bg-white/5 transition-all flex flex-col items-center gap-3"
              >
                <div
                  className={`p-4 rounded-xl ${
                    action.color === 'blue'
                      ? 'bg-blue-500/20'
                      : action.color === 'purple'
                      ? 'bg-purple-500/20'
                      : 'bg-cyan-500/20'
                  }`}
                >
                  <Icon className="w-6 h-6" />
                </div>
                <span className="text-sm font-medium">{action.label}</span>
              </motion.button>
            );
          })}
        </div>
      </GlassCard>
    </div>
  );
}

