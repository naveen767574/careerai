import { useState, useEffect } from 'react';
import { GlassCard } from '../components/GlassCard';
import { motion } from 'motion/react';
import {
  Upload, FileText, CheckCircle2, AlertCircle,
  TrendingUp, Target, Zap, RefreshCw,
} from 'lucide-react';
import { resumeService } from '../lib/services';
import api from '../lib/api';

export function ResumeAnalyzer() {
  const [dragOver, setDragOver] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState('');
  const [resumeData, setResumeData] = useState<any>(null);

  useEffect(() => {
    loadExistingResume();
  }, []);

  const loadExistingResume = async () => {
    try {
      const data = await resumeService.getMyResume();
      if (data) {
        setFileName(data.file_name || 'resume');
        setUploaded(true);
        // Fetch analysis using resume id
        try {
          const analysis = await resumeService.getAnalysis(data.id);
          setResumeData(analysis);
        } catch {
          setResumeData(data);
        }
      }
    } catch {
      // No resume yet
    }
  };

  const handleFile = async (file: File) => {
    if (!file) return;
    setError('');
    setUploading(true);
    setFileName(file.name);
    try {
      await resumeService.upload(file);
      setUploaded(true);
      setAnalyzing(true);
      // Wait for analysis then fetch
      setTimeout(async () => {
        try {
          const resume = await resumeService.getMyResume();
          const analysis = await resumeService.getAnalysis(resume.id);
          setResumeData(analysis);

        } catch {
          // fallback
        }
        setAnalyzing(false);
        // Trigger recommendation refresh + scraper in background
        try {
          await api.post('/recommendations/refresh');
        } catch { }
        try {
          api.post('/agent/trigger', { trigger: 'resume_upload' }).catch(() => {});
        } catch { }
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
      setUploading(false);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleClick = () => {
    const input = document.getElementById('resume-file-input') as HTMLInputElement;
    if (input) input.click();
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const score = resumeData?.ats_score || resumeData?.score || 0;
  const skills = resumeData?.extracted_skills || resumeData?.analysis?.skills || [];
  const suggestions = resumeData?.missing_sections?.map((s: string) => `Add ${s} section`) ||
    resumeData?.improvements || [
    'Add more quantified achievements',
    'Include relevant certifications',
    'Expand your skills section',
  ];

  return (
    <div className="p-6 space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
          Resume Analyzer
        </h1>
        <p className="text-gray-400 mt-1">Upload your resume to get AI-powered insights</p>
      </motion.div>

      {error && (
        <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          {error}
        </div>
      )}

      <input
        id="resume-file-input"
        type="file"
        accept=".pdf,.docx"
        style={{ display: 'none' }}
        onChange={handleFileInput}
      />

      {!uploaded ? (
        <GlassCard
          className={`border-2 border-dashed transition-all duration-300 cursor-pointer p-12 text-center ${
            dragOver ? 'border-blue-400 bg-blue-500/10' : 'border-gray-600'
          }`}
          onDragOver={(e: React.DragEvent) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <Upload className="w-16 h-16 text-blue-400 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">
            {uploading ? 'Uploading...' : 'Drop your resume here'}
          </h3>
          <p className="text-gray-400">Supports PDF and DOCX files</p>
        </GlassCard>
      ) : (
        <div className="space-y-4">
          <GlassCard className="p-6 flex items-center gap-4">
            <FileText className="w-10 h-10 text-blue-400" />
            <div className="flex-1">
              <p className="text-white font-semibold">{fileName}</p>
              <p className="text-gray-400 text-sm">
                {analyzing ? 'Analyzing with AI...' : 'Analyzed successfully'}
              </p>
            </div>
            {analyzing ? (
              <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
            ) : (
              <CheckCircle2 className="w-6 h-6 text-green-400" />
            )}
            <button
              onClick={handleClick}
              className="ml-2 text-xs text-blue-400 hover:text-blue-300 underline"
            >
              Replace
            </button>
          </GlassCard>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: TrendingUp, label: 'Resume Score', value: analyzing ? '...' : `${score}/100`, color: 'text-blue-400' },
              { icon: Target, label: 'Skills Found', value: analyzing ? '...' : `${skills.length} skills`, color: 'text-violet-400' },
              { icon: Zap, label: 'ATS Ready', value: analyzing ? '...' : score > 60 ? 'Yes' : 'Needs Work', color: 'text-cyan-400' },
            ].map((stat) => (
              <GlassCard key={stat.label} className="p-6 text-center">
                <stat.icon className={`w-8 h-8 ${stat.color} mx-auto mb-2`} />
                <p className="text-2xl font-bold text-white">{stat.value}</p>
                <p className="text-gray-400 text-sm">{stat.label}</p>
              </GlassCard>
            ))}
          </div>

          {skills.length > 0 && (
            <GlassCard className="p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-400" />
                Detected Skills
              </h3>
              <div className="flex flex-wrap gap-2">
                {skills.slice(0, 20).map((skill: any, idx: number) => (
                  <span key={idx} className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-lg text-xs">
                    {typeof skill === 'string' ? skill : skill.name}
                  </span>
                ))}
              </div>
            </GlassCard>
          )}

          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-400" />
              Improvement Suggestions
            </h3>
            <ul className="space-y-2 text-gray-300">
              {(Array.isArray(suggestions) ? suggestions : [suggestions]).map((s: string, idx: number) => (
                <li key={idx} className="flex items-center gap-2">
                  • {s}
                </li>
              ))}
            </ul>
          </GlassCard>
        </div>
      )}
    </div>
  );
}








