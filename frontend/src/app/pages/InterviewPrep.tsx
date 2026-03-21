import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  MessageSquare, Code, Brain, Users, Play,
  CheckCircle2, Clock, Trophy, Target, RefreshCw,
} from 'lucide-react';
import { interviewService, internshipService } from '../lib/services';

const categories = [
  { id: 'technical', title: 'Technical', icon: Code, count: 3, color: 'blue' },
  { id: 'behavioral', title: 'Behavioral', icon: Users, count: 3, color: 'purple' },
  { id: 'project', title: 'Project Based', icon: Brain, count: 2, color: 'cyan' },
  { id: 'situational', title: 'Situational', icon: MessageSquare, count: 2, color: 'blue' },
];

export function InterviewPrep() {
  const [selectedCategory, setSelectedCategory] = useState('technical');
  const [internships, setInternships] = useState<any[]>([]);
  const [selectedInternship, setSelectedInternship] = useState<number | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [currentQuestion, setCurrentQuestion] = useState<any>(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [stats, setStats] = useState({
    solved: 0,
    time: '0h',
    successRate: '0%',
    sessions: 0,
  });
  const [questions, setQuestions] = useState<any[]>([]);
  const [feedback, setFeedback] = useState<any>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [showFullHistory, setShowFullHistory] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [difficultyFilter, setDifficultyFilter] = useState('All');

  const filteredQuestions = questions.filter(q => {
    const diffMatch = difficultyFilter === 'All' || q.difficulty?.toLowerCase() === difficultyFilter.toLowerCase();
    const catMatch = categoryFilter === 'All' || q.category?.toLowerCase() === categoryFilter.toLowerCase();
    return diffMatch && catMatch;
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const intData = await internshipService.getAll({ limit: 20 });
      setInternships(intData.internships || []);
    } catch { }

    try {
      const histData = await interviewService.getHistory();
      const sessions = histData.sessions || histData || [];
      setHistory(sessions);
      const completedSessions = sessions.filter((s: any) => s.overall_score !== null && s.overall_score > 0);
      setStats({
        solved: completedSessions.length * 10, // 10 questions per completed session
        time: `${sessions.length * 15}m`,
        successRate: completedSessions.length > 0
          ? `${Math.round(completedSessions.reduce((acc: number, s: any) => acc + (s.overall_score || 0), 0) / completedSessions.length)}%`
          : '0%',
        sessions: sessions.length,
      });
    } catch { }
  };

  const handleStartSession = async () => {
    if (!selectedInternship) return;
    setLoading(true);
    try {
      const session = await interviewService.start(selectedInternship);
      setActiveSession(session);
      setAnsweredCount(0);
      setFeedback(null);
      const allQ = await interviewService.getQuestions(session.session_id);
      setQuestions(allQ.questions || []);
      if (session.first_question) {
        setCurrentQuestion(session.first_question);
      } else if (allQ.questions?.length > 0) {
        setCurrentQuestion(allQ.questions[0]);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start session');
    }
    setLoading(false);
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !activeSession || !currentQuestion) return;
    setSubmitting(true);
    try {
      const fb = await interviewService.submitAnswer(
        activeSession.session_id,
        currentQuestion.id,
        answer
      );
      setAnswer('');
      setAnsweredCount(prev => prev + 1);
      setStats(prev => ({ ...prev, solved: prev.solved + 1 }));
      setFeedback({
        score: fb.score,
        verdict: fb.verdict,
        strengths: fb.strengths || [],
        weaknesses: fb.weaknesses || [],
        model_answer: fb.model_answer,
        improvement_tip: fb.improvement_tip,
      });
      setQuestions(prev => prev.map(q =>
        q.id === currentQuestion.id ? { ...q, completed: true } : q
      ));
      if (fb.next_question) {
        setCurrentQuestion(fb.next_question);
      } else {
        await interviewService.complete(activeSession.session_id);
        const rep = await interviewService.getReport(activeSession.session_id);
        setReport(rep);
        setActiveSession(null);
        setCurrentQuestion(null);
        loadData();
      }
    } catch (err) {
      console.log('Submit failed', err);
    }
    setSubmitting(false);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold mb-2 gradient-text">
          Interview Preparation
        </h1>
        <p className="text-white/60">
          Practice with AI-powered mock interviews and questions
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: 'Questions Solved', value: stats.solved.toString(), icon: CheckCircle2, color: 'blue' },
          { label: 'Practice Time', value: stats.time, icon: Clock, color: 'purple' },
          { label: 'Success Rate', value: stats.successRate, icon: Trophy, color: 'cyan' },
          { label: 'Mock Interviews', value: stats.sessions.toString(), icon: Target, color: 'blue' },
        ].map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <GlassCard key={idx} hover>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-white/60 text-sm mb-1">{stat.label}</p>
                  <h3 className="text-3xl font-bold">{stat.value}</h3>
                </div>
                <div
                  className={`p-3 rounded-xl ${
                    stat.color === 'blue'
                      ? 'bg-blue-500/20'
                      : stat.color === 'purple'
                      ? 'bg-purple-500/20'
                      : 'bg-cyan-500/20'
                  }`}
                >
                  <Icon className="w-6 h-6" />
                </div>
              </div>
            </GlassCard>
          );
        })}
      </div>

      {/* Categories */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {categories.map((category) => {
          const Icon = category.icon;
          return (
            <GlassCard
              key={category.id}
              hover
              gradient={category.color as any}
              onClick={() => setCategoryFilter(categoryFilter === category.id ? 'All' : category.id)}
              className={`cursor-pointer transition-all ${categoryFilter === category.id ? 'ring-2 ring-blue-500/50' : ''}`}
            >
              <div
                className={`p-3 rounded-xl mb-4 w-fit ${
                  category.color === 'blue'
                    ? 'bg-blue-500/20'
                    : category.color === 'purple'
                    ? 'bg-purple-500/20'
                    : 'bg-cyan-500/20'
                }`}
              >
                <Icon className="w-6 h-6" />
              </div>
              <h3 className="font-semibold mb-1">{category.title}</h3>
              <p className="text-sm text-white/60">{category.count} questions</p>
            </GlassCard>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Practice Questions */}
        <GlassCard className="lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold">Practice Questions</h3>
            <div className="flex gap-2">
              {['All', 'Easy', 'Medium', 'Hard'].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setDifficultyFilter(filter)}
                  className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                    difficultyFilter === filter
                      ? 'bg-blue-500/30 text-blue-400 border border-blue-500/50'
                      : 'glass-card hover:bg-white/10'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            {filteredQuestions.map((q: any) => (
              <div
                key={q.id}
                onClick={() => {
                  if (activeSession) setCurrentQuestion(q);
                }}
                className="glass-card p-4 rounded-xl flex items-center justify-between group hover:bg-white/5 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-4 flex-1">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      q.completed
                        ? 'bg-green-500/20'
                        : 'bg-white/5'
                    }`}
                  >
                    {q.completed ? (
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                    ) : (
                      <Play className="w-5 h-5 text-white/60" />
                    )}
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium mb-1">{q.question_text || q.question}</h4>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-white/60">{q.category || q.type || 'Question'}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          q.difficulty?.toLowerCase() === 'easy'
                            ? 'bg-green-500/20 text-green-400'
                            : q.difficulty?.toLowerCase() === 'medium'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}
                      >
                        {q.difficulty || 'Medium'}
                      </span>
                      <span className="text-xs text-white/60">• {q.time || '15 min'}</span>
                    </div>
                  </div>
                </div>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2 rounded-xl text-sm"
                >
                  Start
                </motion.button>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Upcoming Mock Interviews */}
        <GlassCard>
          <h3 className="text-xl font-semibold mb-6">Start Mock Interview</h3>

          {report ? (
            <div className="space-y-4">
              <div className="text-center py-4">
                <Trophy className="w-12 h-12 text-yellow-400 mx-auto mb-2" />
                <h4 className="text-xl font-bold">Session Complete!</h4>
                <p className="text-3xl font-bold text-blue-400 mt-2">
                  {report.overall_score || report.score || 0}%
                </p>
                <p className="text-white/60 text-sm">Overall Score</p>
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                onClick={() => { setReport(null); setStats(s => ({...s})); loadData(); }}
                className="w-full glass-card py-3 rounded-xl text-sm font-medium"
              >
                Start New Session
              </motion.button>
            </div>
          ) : activeSession && currentQuestion ? (
            <div className="space-y-4">
              <div className="glass-card p-4 rounded-xl">
                <p className="text-xs text-white/60 mb-2">Question</p>
                <p className="text-sm font-medium">{currentQuestion.question_text || currentQuestion.question}</p>
              </div>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer here..."
                className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm focus:outline-none focus:border-blue-500/50 resize-none"
                rows={5}
              />
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSubmitAnswer}
                disabled={submitting}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 text-sm font-medium"
              >
                {submitting ? 'Submitting...' : 'Submit Answer'}
              </motion.button>
              {feedback && (
                <div className="glass-card p-4 rounded-xl space-y-2 mt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Last Answer Feedback</span>
                    <span className={`text-sm font-bold ${feedback.score >= 7 ? 'text-green-400' : feedback.score >= 5 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {feedback.score}/10 — {feedback.verdict}
                    </span>
                  </div>
                  {feedback.strengths?.length > 0 && (
                    <div>
                      <p className="text-xs text-green-400 mb-1">? Strengths</p>
                      {feedback.strengths.map((s: string, i: number) => (
                        <p key={i} className="text-xs text-white/70">• {s}</p>
                      ))}
                    </div>
                  )}
                  {feedback.weaknesses?.length > 0 && (
                    <div>
                      <p className="text-xs text-orange-400 mb-1">Improve</p>
                      {feedback.weaknesses.map((w: string, i: number) => (
                        <p key={i} className="text-xs text-white/70">• {w}</p>
                      ))}
                    </div>
                  )}
                  {feedback.improvement_tip && (
                    <p className="text-xs text-purple-300 italic">{feedback.improvement_tip}</p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <select
                value={selectedInternship || ''}
                onChange={(e) => setSelectedInternship(Number(e.target.value))}
                className="w-full bg-gray-900 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500/50 cursor-pointer"
              >
                <option value="" className="bg-gray-900">Select an internship...</option>
                {internships.map((i: any) => (
                  <option key={i.id} value={i.id} className="bg-gray-900">
                    {i.title} — {i.company}
                  </option>
                ))}
              </select>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleStartSession}
                disabled={!selectedInternship || loading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl py-3 text-sm font-medium disabled:opacity-50"
              >
                {loading ? 'Starting...' : 'Start Mock Interview'}
              </motion.button>
            </div>
          )}

          {history.length > 0 && !activeSession && !report && (
            <div className="mt-6">
              <h4 className="text-sm font-medium text-white/60 mb-3">Past Sessions</h4>
              {history.slice(0, 3).map((s: any, idx: number) => (
                <div key={idx} className="glass-card p-3 rounded-xl mb-2 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{s.internship_title || s.internship?.title || 'Session'}</p>
                    <p className="text-xs text-white/60">
                      {s.overall_score ? `Score: ${Math.round(s.overall_score)}%` : 'In Progress'}
                    </p>
                  </div>
                  {!s.overall_score && s.status === 'in_progress' && (
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      onClick={() => {
                        setActiveSession({ session_id: s.session_id });
                        interviewService.getQuestions(s.session_id).then(data => {
                          setQuestions(data.questions || []);
                          const unanswered = (data.questions || []).find((q: any) => !q.completed);
                          if (unanswered) setCurrentQuestion(unanswered);
                        });
                      }}
                      className="text-xs bg-blue-500/20 text-blue-400 px-3 py-1 rounded-lg"
                    >
                      Resume
                    </motion.button>
                  )}
                </div>
              ))}
              {history.length > 3 && (
                <button
                  onClick={() => setShowFullHistory(!showFullHistory)}
                  className="w-full text-xs text-white/40 hover:text-white/60 py-2"
                >
                  {showFullHistory ? 'Show Less ?' : `View More (${history.length - 3} more) ?`}
                </button>
              )}
              {showFullHistory && history.slice(3).map((s: any, idx: number) => (
                <div key={idx} className="glass-card p-3 rounded-xl mb-2">
                  <p className="text-sm font-medium">{s.internship_title || s.internship?.title || 'Session'}</p>
                  <p className="text-xs text-white/60">
                    {s.overall_score ? `Score: ${Math.round(s.overall_score)}%` : 'In Progress'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      <GlassCard gradient="purple">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-purple-500/20 rounded-xl">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold mb-1">AI Interview Coach</h3>
            <p className="text-sm text-white/60 mb-3">
              Voice-based AI coaching with real-time feedback on tone, clarity and structure.
            </p>
            <span className="text-xs px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full">
              ?? Coming Soon
            </span>
          </div>
        </div>
      </GlassCard>
    </div>
  );
}


