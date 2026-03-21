import { useState, useEffect, useRef } from 'react';
import { careerService } from '../lib/services';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  Code,
  Palette,
  BarChart3,
  Server,
  Shield,
  Smartphone,
  TrendingUp,
  CheckCircle2,
  ArrowRight,
  Star,
} from 'lucide-react';

const roadmap = [
  {
    phase: 'Foundation',
    duration: '0-3 months',
    items: [
      'Learn programming fundamentals',
      'Master Git & GitHub',
      'Build 3-5 small projects',
    ],
  },
  {
    phase: 'Skill Building',
    duration: '3-6 months',
    items: [
      'Deep dive into frameworks',
      'Contribute to open source',
      'Build portfolio projects',
    ],
  },
  {
    phase: 'Specialization',
    duration: '6-12 months',
    items: [
      'Choose specialization area',
      'Work on complex projects',
      'Network with professionals',
    ],
  },
  {
    phase: 'Job Ready',
    duration: '12+ months',
    items: [
      'Polish portfolio & resume',
      'Practice technical interviews',
      'Apply to positions',
    ],
  },
];

export function CareerPaths() {
  const [careerPaths, setCareerPaths] = useState<any[]>([]);
  const [topPath, setTopPath] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPath, setSelectedPath] = useState<any>(null);
  const roadmapRef = useRef<HTMLDivElement>(null);

  const iconMap: any = {
    'Frontend': Code,
    'UI': Palette,
    'UX': Palette,
    'Design': Palette,
    'Data': BarChart3,
    'Backend': Server,
    'Security': Shield,
    'Mobile': Smartphone,
    'default': Code,
  };

  const gradients = ['blue', 'purple', 'cyan', 'blue', 'purple', 'cyan'];

  const activeRoadmap = selectedPath?.steps?.length > 0
    ? selectedPath.steps.map((step: any) => ({
        phase: step.level,
        duration: step.level.includes('Entry') ? '0-3 months' : step.level.includes('Mid') ? '3-12 months' : '12+ months',
        items: step.skills_to_acquire,
      }))
    : roadmap;

  useEffect(() => {
    loadCareerPaths();
  }, []);

  const loadCareerPaths = async () => {
    try {
      const data = await careerService.getPaths();
      const paths = data.career_paths || data.paths || data || [];

      const mapped = paths.map((path: any, idx: number) => {
        const iconKey = Object.keys(iconMap).find(k =>
          path.title?.includes(k)
        ) || 'default';
        return {
          id: idx + 1,
          title: path.title || path.path_id || 'Career Path',
          icon: iconMap[iconKey],
          match: path.match_percentage || path.alignment_score || 80,
          salary: path.salary_range || 'Competitive',
          growth: path.growth_rate || '+18%',
          skills: path.required_skills || path.user_has || [],
          missingSkills: path.user_missing || [],
          companies: path.open_positions || 12000,
          gradient: gradients[idx % gradients.length],
          timeline: path.timeline || '6-12 months',
          description: path.description || '',
          steps: path.steps || [],
          whyFits: path.why_fits || '',
          topSkill: path.top_skill_to_learn || '',
        };
      });

      setCareerPaths(mapped);
      if (mapped.length > 0) setTopPath(mapped[0]);
    } catch (err) {
      console.log('Career paths need resume upload first');
      setCareerPaths([]);
    }

    setLoading(false);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold mb-2 gradient-text">Career Paths</h1>
        <p className="text-white/60">
          Explore AI-recommended career trajectories based on your skills
        </p>
      </div>

      {/* Recommended Path */}
      <GlassCard gradient="blue">
        <div className="flex items-start gap-4 mb-6">
          <div className="p-3 bg-blue-500/20 rounded-xl">
            <Star className="w-6 h-6 text-blue-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold mb-2">
              Recommended: {topPath?.title || 'Upload Resume First'}
            </h2>
            <p className="text-white/60">
              {topPath
                ? `Based on your skills and experience, this path has a ${topPath.match}% match`
                : 'Upload your resume to get personalized career path recommendations'}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Skill Match', value: topPath ? `${Math.round(topPath.match)}%` : '--' },
            { label: 'Timeline', value: topPath?.timeline || '--' },
            { label: 'Job Growth', value: topPath?.growth || '--' },
            { label: 'Open Roles', value: topPath ? `${(topPath.companies/1000).toFixed(0)}K+` : '--' },
          ].map((stat, idx) => (
            <div key={idx} className="glass-card p-4 rounded-xl">
              <p className="text-white/60 text-sm mb-1">{stat.label}</p>
              <p className="text-xl font-bold">{stat.value}</p>
            </div>
          ))}
        </div>
      </GlassCard>

      {loading && (
        <div className="text-center py-12 text-white/60">
          Analyzing your career paths...
        </div>
      )}

      {!loading && careerPaths.length === 0 && (
        <GlassCard className="text-center py-12">
          <BarChart3 className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2">No career paths yet</h3>
          <p className="text-white/60">Upload your resume to get AI career recommendations</p>
        </GlassCard>
      )}

      {/* All Career Paths */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {careerPaths.map((path) => {
          const Icon = path.icon;
          return (
            <GlassCard key={path.id} hover gradient={path.gradient as any}>
              <div className="flex items-start justify-between mb-4">
                <div
                  className={`p-3 rounded-xl ${
                    path.gradient === 'blue'
                      ? 'bg-blue-500/20'
                      : path.gradient === 'purple'
                      ? 'bg-purple-500/20'
                      : 'bg-cyan-500/20'
                  }`}
                >
                  <Icon className="w-6 h-6" />
                </div>
                <div className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-xs font-medium">
                  {path.match}% Match
                </div>
              </div>

              <h3 className="text-xl font-semibold mb-2">{path.title}</h3>

              <div className="space-y-2 mb-4">
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Salary Range</span>
                  <span className="font-medium">{path.salary}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Growth Rate</span>
                  <span className="text-green-400 font-medium">{path.growth}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">Open Positions</span>
                  <span className="font-medium">{path.companies.toLocaleString()}</span>
                </div>
              </div>

              <div className="mb-4">
                <p className="text-sm text-white/60 mb-2">Key Skills</p>
                <div className="flex flex-wrap gap-2">
                  {path.skills.map((skill: any, idx: number) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-white/5 rounded-lg text-xs"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {path.whyFits && (
                <p className="text-xs text-white/50 mb-3 italic">✨ {path.whyFits}</p>
              )}

              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  setSelectedPath(path);
                  setTopPath(path);
                  roadmapRef.current?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="w-full glass-card py-2 rounded-xl text-sm font-medium flex items-center justify-center gap-2 hover:bg-white/10 transition-colors"
              >
                View Roadmap
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            </GlassCard>
          );
        })}
      </div>

      {/* Learning Roadmap */}
      <GlassCard ref={roadmapRef}>
        <h2 className="text-2xl font-bold mb-6">
          {topPath?.title || 'Career'} Roadmap
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {activeRoadmap.map((phase, idx) => (
            <div key={idx} className="relative">
              {idx < activeRoadmap.length - 1 && (
                <div className="hidden md:block absolute top-8 left-full w-full h-0.5 bg-gradient-to-r from-blue-500/50 to-transparent" />
              )}
              <div className="glass-card p-6 rounded-xl relative">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center mb-4 font-bold">
                  {idx + 1}
                </div>
                <h3 className="font-semibold mb-1">{phase.phase}</h3>
                <p className="text-xs text-white/60 mb-4">{phase.duration}</p>
                <ul className="space-y-2">
                  {phase.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                      <span className="text-white/80">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Resources */}
      <GlassCard gradient="purple">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-purple-500/20 rounded-xl">
            <TrendingUp className="w-6 h-6 text-purple-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-semibold mb-2">
              Ready to start your journey?
            </h3>
            <p className="text-white/60 mb-4">
              Get personalized learning resources and mentorship
            </p>
            <div className="flex gap-3">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => window.location.href = '/internships'}
                className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-2 rounded-xl text-sm font-medium"
              >
                Find Internships
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => window.open('https://roadmap.sh', '_blank')}
                className="glass-card px-6 py-2 rounded-xl text-sm font-medium"
              >
                View Roadmaps →
              </motion.button>
            </div>
            {topPath?.topSkill && (
              <p className="text-sm text-purple-300 mt-3">
                🎯 Focus next on: <span className="font-semibold">{topPath.topSkill}</span>
              </p>
            )}
          </div>
        </div>
      </GlassCard>
    </div>
  );
}



