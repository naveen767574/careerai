import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  FileText, Download, Eye, Wand2, Plus,
  Settings, Palette, Layout, RefreshCw, CheckCircle2,
} from 'lucide-react';
import { resumeBuilderService } from '../lib/services';

const defaultTemplates = [
  { id: 1, name: 'Modern', preview: '🎨', color: 'blue' },
  { id: 2, name: 'Professional', preview: '💼', color: 'purple' },
  { id: 3, name: 'Creative', preview: '✨', color: 'cyan' },
  { id: 4, name: 'Minimal', preview: '📄', color: 'blue' },
];

export function ResumeBuilder() {
  const [selectedTemplate, setSelectedTemplate] = useState(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<any>(null);
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [atsScore, setAtsScore] = useState<number | null>(null);
  const [atsDetails, setAtsDetails] = useState<any>(null);
  const [completedSections, setCompletedSections] = useState<string[]>([]);
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);

  const templateNames: Record<number, string> = {
    1: 'modern', 2: 'professional', 3: 'creative', 4: 'minimal'
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const data = await resumeBuilderService.getTemplates();
      setAvailableTemplates(data.templates || []);
    } catch {
      // Use default templates
    }
  };

  const handleStartSession = async () => {
    setStarting(true);
    try {
      const templateName = templateNames[selectedTemplate] || 'modern';
      const data = await resumeBuilderService.startSession(templateName);
      setSessionId(data.session_id);
      if (data.next_question) setCurrentQuestion(data.next_question);
      else if (data.question) setCurrentQuestion({ question: data.question });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start session');
    }
    setStarting(false);
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !sessionId || !currentQuestion) return;
    setSubmitting(true);
    try {
      const data = await resumeBuilderService.submitAnswer(
        sessionId,
        currentQuestion.field || currentQuestion.id || currentQuestion.step,
        answer
      );
      setAnswer('');
      setCompletedSections(prev => {
        const stepToField: Record<number, string> = {
          1: 'personal_info', 2: 'personal_info', 3: 'skills',
          4: 'skills', 5: 'education', 6: 'experience',
          7: 'projects', 8: 'certifications', 9: 'achievements'
        };
        const field = stepToField[currentQuestion?.step] || currentQuestion?.field;
        return field ? [...new Set([...prev, field])] : prev;
      });
      if (data.resume_data_summary) {
        setPreviewData(data.resume_data_summary);
      }
      await loadPreview();
      if (data.next_question) {
        setCurrentQuestion(data.next_question);
      } else if (data.question) {
        setCurrentQuestion({ question: data.question });
      } else {
        setCurrentQuestion(null);
        loadPreview();
      }
    } catch (err) {
      console.log('Submit failed');
    }
    setSubmitting(false);
  };

  const loadPreview = async () => {
    if (!sessionId) return;
    try {
      const data = await resumeBuilderService.getSession(sessionId);
      // Backend stores data in resume_data field
      const rd = data.resume_data || data;
      setPreviewData({
        name: rd.name || '',
        title: rd.career_interests || rd.title || '',
        email: rd.email || '',
        phone: rd.phone || '',
        linkedin: rd.linkedin || '',
        summary: rd.summary || rd.professional_summary || '',
        experience: rd.experience || [],
        education: rd.education || [],
        skills: Array.isArray(rd.skills)
          ? rd.skills
          : typeof rd.skills === 'string'
          ? rd.skills.split(',').map((s: string) => s.trim())
          : [],
        projects: rd.projects || [],
        certifications: rd.certifications || [],
        achievements: rd.achievements || [],
      });
      if (data.ats_score) {
        const score = data.ats_score;
        setAtsScore(typeof score === 'object' ? score.total_score : score);
        if (typeof score === 'object') setAtsDetails(score);
      }
    } catch { }
  };

  const sendCommand = async (command: string) => {
  if (!sessionId) {
    alert('Please start a session first by clicking "Start AI Builder"');
    return;
  }
  setSubmitting(true);
  try {
    const data = await resumeBuilderService.submitAnswer(sessionId, 'command', command);
    if (data.question) setCurrentQuestion({ question: data.question });
    if (data.resume_data_summary) {
      const rd = data.resume_data_summary;
      setPreviewData({
        name: rd.name || '',
        title: rd.career_interests || rd.title || '',
        email: rd.email || '',
        phone: rd.phone || '',
        linkedin: rd.linkedin || '',
        summary: rd.summary || '',
        experience: rd.experience || [],
        education: rd.education || [],
        skills: Array.isArray(rd.skills) ? rd.skills : typeof rd.skills === 'string' ? rd.skills.split(',').map((s: string) => s.trim()) : [],
        projects: rd.projects || [],
        certifications: rd.certifications || [],
      });
      if (rd.ats_score) {
        const score = rd.ats_score;
        setAtsScore(typeof score === 'object' ? score.total_score : score);
        if (typeof score === 'object') setAtsDetails(score);
      }
    }
    // Always reload preview after command
    await loadPreview();
  } catch {
    alert('Command failed. Complete the resume builder steps first.');
  }
  setSubmitting(false);
};

  const handleExportPdf = async () => {
    if (!sessionId) return;
    setExporting(true);
    try {
      const blob = await resumeBuilderService.exportPdf(sessionId);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'resume.pdf';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed. Complete the resume builder first.');
    }
    setExporting(false);
  };

  const handleExportDocx = async () => {
    if (!sessionId) return;
    setExporting(true);
    try {
      const blob = await resumeBuilderService.exportDocx(sessionId);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'resume.docx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed. Complete the resume builder first.');
    }
    setExporting(false);
  };

  const resumePreview = previewData || {
    name: 'Your Name',
    title: 'Your Title',
    email: 'your@email.com',
    phone: '+1 (555) 000-0000',
    location: 'Your City',
    summary: 'Start the AI Resume Builder to generate your personalized resume...',
    experience: [],
    education: [],
    skills: [],
  };

    const sectionsList = [
    { id: 1, name: 'Personal Info', icon: '👤', field: 'personal_info' },
    { id: 2, name: 'Experience', icon: '💼', field: 'experience' },
    { id: 3, name: 'Education', icon: '🎓', field: 'education' },
    { id: 4, name: 'Skills', icon: '⚡', field: 'skills' },
    { id: 5, name: 'Projects', icon: '🚀', field: 'projects' },
    { id: 6, name: 'Certifications', icon: '🏆', field: 'certifications' },
  ];

  const templatesToShow = availableTemplates.length > 0
    ? availableTemplates.map((t: any, idx: number) => ({
        id: idx + 1,
        name: t.name || t.template_id || t.template || `Template ${idx + 1}`,
        preview: t.preview || (defaultTemplates[idx]?.preview || '??'),
        color: t.preview_color || defaultTemplates[idx]?.color || 'blue',
      }))
    : defaultTemplates;

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold mb-2 gradient-text">
            Resume Builder
          </h1>
          <p className="text-white/60">
            Create ATS-friendly resumes with AI assistance
          </p>
        </div>
        <div className="flex gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadPreview}
            className="glass-card px-4 py-2 rounded-xl flex items-center gap-2"
          >
            <Eye className="w-4 h-4" />
            <span className="text-sm">Preview</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleExportPdf}
            disabled={exporting || !sessionId}
            className="bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2 rounded-xl flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            <span className="text-sm font-medium">Export PDF</span>
          </motion.button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Sidebar - Sections */}
        <div className="space-y-4">
          <GlassCard>
            <h3 className="text-lg font-semibold mb-4">Resume Sections</h3>
            <div className="space-y-2">
              {sectionsList.map((section) => (
                <div
                  key={section.id}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl text-left glass-card ${
                    completedSections.includes(section.field) ? 'opacity-100' : 'opacity-50'
                  }`}
                >
                  <span className="text-xl">{section.icon}</span>
                  <span className="text-sm flex-1">{section.name}</span>
                  {completedSections.includes(section.field)
                    ? <div className="w-2 h-2 bg-green-400 rounded-full" />
                    : <span className="text-xs text-white/30">pending</span>
                  }
                </div>
              ))}
            </div>
            <div className="w-full mt-4 glass-card p-3 rounded-xl flex items-center justify-center gap-2 opacity-40 cursor-not-allowed">
              <Plus className="w-4 h-4" />
              <span className="text-sm">Add Section</span>
              <span className="text-xs text-white/40">(soon)</span>
            </div>
          </GlassCard>

          <GlassCard gradient="purple">
            <div className="flex items-start gap-3 mb-3">
              <Wand2 className="w-5 h-5 text-purple-400 mt-0.5" />
              <div>
                <h4 className="font-medium text-sm mb-1">AI Assistant</h4>
                <p className="text-xs text-white/60 mb-3">
                  Let AI enhance your content
                </p>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleStartSession}
                  disabled={starting}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-500 px-3 py-2 rounded-lg text-xs font-medium disabled:opacity-50"
                >
                  {starting ? 'Starting...' : sessionId ? 'Continue Building' : 'Start AI Builder'}
                </motion.button>
              </div>
            </div>
            {sessionId && (
              <div className="mt-4 space-y-2">
                <p className="text-xs text-white/40 mb-2">Quick Actions</p>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendCommand('improve bullets')}
                  disabled={submitting}
                  className="w-full glass-card py-2 rounded-xl text-xs flex items-center gap-2 px-3 hover:bg-white/10"
                >
                  <Wand2 className="w-3 h-3 text-purple-400" />
                  Improve Bullets (AI)
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendCommand('check ats score')}
                  disabled={submitting}
                  className="w-full glass-card py-2 rounded-xl text-xs flex items-center gap-2 px-3 hover:bg-white/10"
                >
                  <CheckCircle2 className="w-3 h-3 text-green-400" />
                  Check ATS Score
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendCommand('finalize')}
                  disabled={submitting}
                  className="w-full glass-card py-2 rounded-xl text-xs flex items-center gap-2 px-3 hover:bg-white/10"
                >
                  <RefreshCw className="w-3 h-3 text-blue-400" />
                  Finalize Resume
                </motion.button>
                {atsScore && (
                  <div className="glass-card p-3 rounded-xl">
                    <div className="text-center mb-2">
                      <p className="text-xs text-white/60">ATS Score</p>
                      <p className="text-2xl font-bold text-green-400">{atsScore}/100</p>
                    </div>
                    {atsDetails && (
                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-white/50">Structure</span>
                          <span className="text-blue-400">{atsDetails.structure_score}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/50">Keywords</span>
                          <span className="text-purple-400">{atsDetails.keyword_score}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/50">Completeness</span>
                          <span className="text-cyan-400">{atsDetails.completeness_score}</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Main Editor Area */}
        <div className="lg:col-span-3 space-y-6">
          {/* Template Selection */}
          <GlassCard>
            <h3 className="text-lg font-semibold mb-4">Choose Template</h3>
            <div className="grid grid-cols-4 gap-4">
              {templatesToShow.map((template) => (
  <div
    key={template.id}
    className={`glass-card p-6 rounded-xl text-center relative ${
      selectedTemplate === template.id
        ? 'border-2 border-blue-500/50 bg-blue-500/10'
        : 'opacity-60'
    }`}
  >
    <div className="text-4xl mb-2">{template.preview}</div>
    <p className="text-sm font-medium">{template.name}</p>
    {template.id !== 1 && (
      <span className="absolute top-2 right-2 text-xs text-white/30">soon</span>
    )}
  </div>
))}
</div>
</GlassCard>

          {sessionId && currentQuestion && (
            <GlassCard gradient="blue">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <Wand2 className="w-5 h-5 text-blue-400" />
                AI Resume Builder
              </h3>
              <p className="text-white/60 text-sm mb-4">
                {currentQuestion.question || currentQuestion.prompt}
              </p>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer..."
                className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm focus:outline-none focus:border-blue-500/50 resize-none mb-3"
                rows={4}
              />
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSubmitAnswer}
                disabled={submitting}
                className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-2 rounded-xl text-sm font-medium disabled:opacity-50"
              >
                {submitting ? 'Saving...' : 'Next ?'}
              </motion.button>
            </GlassCard>
          )}

          {sessionId && !currentQuestion && (
            <GlassCard gradient="blue">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-green-400" />
                <div>
                  <h3 className="font-semibold">Resume Complete!</h3>
                  <p className="text-sm text-white/60">Export your resume below</p>
                </div>
                {atsScore && (
                  <div className="ml-auto text-center">
                    <p className="text-2xl font-bold text-blue-400">{atsScore}%</p>
                    <p className="text-xs text-white/60">ATS Score</p>
                  </div>
                )}
              </div>
            </GlassCard>
          )}

          {/* Resume Preview */}
          <GlassCard>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">Resume Preview</h3>
              <div className="flex gap-2">
                <button className="p-2 glass-card rounded-lg hover:bg-white/10 transition-colors">
                  <Layout className="w-4 h-4" />
                </button>
                <button className="p-2 glass-card rounded-lg hover:bg-white/10 transition-colors">
                  <Palette className="w-4 h-4" />
                </button>
                <button className="p-2 glass-card rounded-lg hover:bg-white/10 transition-colors">
                  <Settings className="w-4 h-4" />
                </button>
              </div>
            </div>

                      {/* Resume Document Preview */}
          <div className="glass-card p-8 rounded-xl min-h-[600px] bg-white/5">
            <div className="space-y-6">
              {/* Header */}
              <div className="text-center pb-6 border-b border-white/10">
                <h2 className="text-3xl font-bold mb-2">{resumePreview.name || 'Your Name'}</h2>
                <p className="text-white/60 mb-2">{resumePreview.title || resumePreview.career_interests || 'Your Title'}</p>
                <div className="flex items-center justify-center gap-4 text-sm text-white/60 flex-wrap">
                  {resumePreview.email && <span>{resumePreview.email}</span>}
                  {resumePreview.phone && <><span>•</span><span>{resumePreview.phone}</span></>}
                  {resumePreview.linkedin && <><span>•</span><a href={resumePreview.linkedin} className="text-blue-400 hover:underline" target="_blank">LinkedIn</a></>}
                </div>
              </div>

              {/* Summary */}
              {resumePreview.summary && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Professional Summary</h3>
                  <p className="text-white/80 leading-relaxed">{resumePreview.summary}</p>
                </div>
              )}

              {/* Experience */}
              {resumePreview.experience?.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Work Experience</h3>
                  <div className="space-y-4">
                    {resumePreview.experience.map((exp: any, idx: number) => (
                      <div key={idx}>
                        <div className="flex justify-between mb-1">
                          <div>
                            <h4 className="font-semibold">{typeof exp === 'string' ? exp : exp.role || exp.title || exp.company}</h4>
                            {typeof exp === 'object' && exp.company && <p className="text-sm text-white/60">{exp.company}</p>}
                          </div>
                          {typeof exp === 'object' && exp.dates && <span className="text-sm text-white/60">{exp.dates}</span>}
                        </div>
                        {typeof exp === 'object' && exp.bullets && (
                          <ul className="list-disc list-inside space-y-1 text-white/80 text-sm">
                            {exp.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {resumePreview.education?.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Education</h3>
                  {resumePreview.education.map((edu: any, idx: number) => (
                    <div key={idx} className="flex justify-between">
                      <div>
                        <h4 className="font-semibold">{typeof edu === 'string' ? edu : edu.degree || edu.institution}</h4>
                        {typeof edu === 'object' && edu.institution && <p className="text-sm text-white/60">{edu.institution}</p>}
                      </div>
                      {typeof edu === 'object' && edu.year && <span className="text-sm text-white/60">{edu.year}</span>}
                    </div>
                  ))}
                </div>
              )}

              {/* Skills */}
              {resumePreview.skills?.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Technical Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {resumePreview.skills.map((skill: string, idx: number) => (
                      <span key={idx} className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-lg text-sm">{skill}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Projects */}
              {resumePreview.projects?.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Projects</h3>
                  {resumePreview.projects.map((proj: any, idx: number) => (
                    <div key={idx} className="mb-2">
                      <h4 className="font-semibold">{typeof proj === 'string' ? proj : proj.name}</h4>
                      {typeof proj === 'object' && proj.description && <p className="text-sm text-white/80">{proj.description}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Certifications */}
              {resumePreview.certifications?.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3 gradient-text">Certifications</h3>
                  <ul className="list-disc list-inside space-y-1 text-white/80 text-sm">
                    {resumePreview.certifications.map((cert: any, idx: number) => (
                      <li key={idx}>{typeof cert === 'string' ? cert : cert.name}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Empty state */}
              {!resumePreview.name && !resumePreview.email && (
                <div className="text-center py-12 text-white/30">
                  <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                  <p>Start the AI Resume Builder to see your resume here</p>
                </div>
              )}
            </div>
          </div>
        </GlassCard>

          {/* Export Options */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: exporting ? 'Exporting...' : 'Export PDF', icon: FileText, action: handleExportPdf },
              { label: 'Export Word', icon: FileText, action: handleExportDocx },
              { label: 'Preview', icon: Eye, action: loadPreview },
            ].map((option, idx) => {
              const Icon = option.icon;
              return (
                <motion.button
                  key={idx}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={option.action}
                  className="glass-card p-4 rounded-xl flex flex-col items-center gap-2 hover:bg-white/5 transition-colors"
                >
                  <Icon className="w-6 h-6 text-white/60" />
                  <span className="text-sm">{option.label}</span>
                </motion.button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}





















