import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import { Building2, Calendar, DollarSign, MoreVertical, Plus, Trash2 } from 'lucide-react';
import { applicationService } from '../lib/services';

interface Application {
  id: number;
  company: string;
  position: string;
  salary: string;
  date: string;
  logo: string;
  status: string;
}

const columns = [
  { id: 'saved', title: 'Saved', color: 'blue' },
  { id: 'applied', title: 'Applied', color: 'purple' },
  { id: 'interview', title: 'Interview', color: 'cyan' },
  { id: 'offer', title: 'Offer', color: 'green' },
];

export function ApplicationsTracker() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadApplications();
  }, []);

  const loadApplications = async () => {
    try {
      const data = await applicationService.getAll();
      const apps = data.applications || [];
      const mapped = apps.map((app: any) => ({
        id: app.id,
        company: app.internship?.company || 'Company',
        position: app.internship?.title || 'Position',
        salary: app.internship?.salary_range || 'Competitive',
        date: new Date(app.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric'
        }),
        logo: '??',
        status: app.status,
      }));
      setApplications(mapped);
    } catch (err) {
      console.log('No applications yet');
      setApplications([]);
    }
    setLoading(false);
  };

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await applicationService.update(id, { status: newStatus });
      setApplications(prev =>
        prev.map(app => app.id === id ? { ...app, status: newStatus } : app)
      );
    } catch (err) {
      console.log('Failed to update status');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await applicationService.delete(id);
      setApplications(prev => prev.filter(app => app.id !== id));
    } catch (err) {
      console.log('Failed to delete');
    }
  };

  const getApplicationsByStatus = (status: string) => {
    return applications.filter((app) => app.status === status);
  };

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold mb-2 gradient-text">
            Applications Tracker
          </h1>
          <p className="text-white/60">
            Manage your job applications in one place
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2 rounded-xl flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm font-medium">Add Application</span>
        </motion.button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {columns.map((column) => {
          const count = getApplicationsByStatus(column.id).length;
          return (
            <GlassCard key={column.id}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm mb-1">{column.title}</p>
                  <h3 className="text-2xl font-bold">{count}</h3>
                </div>
                <div
                  className={`w-2 h-12 rounded-full ${
                    column.color === 'blue'
                      ? 'bg-blue-500'
                      : column.color === 'purple'
                      ? 'bg-purple-500'
                      : column.color === 'cyan'
                      ? 'bg-cyan-500'
                      : 'bg-green-500'
                  }`}
                />
              </div>
            </GlassCard>
          );
        })}
      </div>

      {!loading && applications.length === 0 && (
        <GlassCard className="text-center py-12">
          <Building2 className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2">No applications yet</h3>
          <p className="text-white/60">Track internships from the Internships page</p>
        </GlassCard>
      )}

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 overflow-x-auto pb-4">
        {columns.map((column) => (
          <div key={column.id} className="min-w-[300px]">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`w-3 h-3 rounded-full ${
                    column.color === 'blue'
                      ? 'bg-blue-500'
                      : column.color === 'purple'
                      ? 'bg-purple-500'
                      : column.color === 'cyan'
                      ? 'bg-cyan-500'
                      : 'bg-green-500'
                  }`}
                />
                <h3 className="font-semibold">{column.title}</h3>
                <span className="text-sm text-white/60">
                  {getApplicationsByStatus(column.id).length}
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {getApplicationsByStatus(column.id).map((app) => (
                <motion.div
                  key={app.id}
                  layout
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-card glass-card-hover p-4 rounded-xl cursor-grab active:cursor-grabbing"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg glass-card flex items-center justify-center text-xl">
                        {app.logo}
                      </div>
                      <div>
                        <h4 className="font-medium text-sm">{app.company}</h4>
                        <p className="text-xs text-white/60">{app.position}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <select
                        value={app.status}
                        onChange={(e) => handleStatusChange(app.id, e.target.value)}
                        className="text-xs bg-white/5 border border-white/10 rounded-lg px-2 py-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <option value="saved">Saved</option>
                        <option value="applied">Applied</option>
                        <option value="interview">Interview</option>
                        <option value="offer">Offer</option>
                        <option value="rejected">Rejected</option>
                        <option value="withdrawn">Withdrawn</option>
                      </select>
                      <button
                        onClick={() => handleDelete(app.id)}
                        className="p-1 hover:bg-red-500/20 rounded-lg transition-colors text-red-400"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-white/60">
                      <DollarSign className="w-3 h-3" />
                      {app.salary}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-white/60">
                      <Calendar className="w-3 h-3" />
                      {app.date}
                    </div>
                  </div>
                </motion.div>
              ))}

              <motion.button
                whileHover={{ scale: 1.02 }}
                className="w-full glass-card p-3 rounded-xl flex items-center justify-center gap-2 text-sm text-white/60 hover:text-white hover:bg-white/5 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Card
              </motion.button>
            </div>
          </div>
        ))}
      </div>

      {/* Timeline View */}
      <GlassCard>
        <h3 className="text-xl font-semibold mb-6">Recent Activity</h3>
        <div className="space-y-4">
          {applications.slice(0, 5).map((app, idx) => (
            <div key={app.id} className="flex items-start gap-4">
              <div className="relative">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-sm">
                  {app.logo}
                </div>
                {idx < 4 && (
                  <div className="absolute top-8 left-1/2 -translate-x-1/2 w-0.5 h-8 bg-white/10" />
                )}
              </div>
              <div className="flex-1 glass-card p-4 rounded-xl">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-medium">{app.position}</h4>
                    <p className="text-sm text-white/60">{app.company}</p>
                  </div>
                  <span className="text-xs text-white/40">{app.date}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-3 py-1 rounded-full text-xs ${
                      app.status === 'applied'
                        ? 'bg-blue-500/20 text-blue-400'
                        : app.status === 'screening'
                        ? 'bg-purple-500/20 text-purple-400'
                        : app.status === 'interview'
                        ? 'bg-cyan-500/20 text-cyan-400'
                        : 'bg-green-500/20 text-green-400'
                    }`}
                  >
                    {app.status.charAt(0).toUpperCase() + app.status.slice(1)}
                  </span>
                  <span className="text-xs text-white/60">• {app.salary}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
