import api from './api';

export const resumeService = {
  async upload(file: File) {
    const form = new FormData();
    form.append('file', file);
    const res = await api.post('/resumes/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  async getMyResume() {
    const res = await api.get('/resumes/me');
    return res.data;
  },
  getAnalysis: (resumeId: string) => api.get(`/resume/${resumeId}/analysis`).then(r => r.data),
  async optimize() {
    // Uses the user's stored resume (auth). Returns:
    // { improvements: string[], missing_keywords: string[],
    //   improved_bullets: { original: string; improved: string }[] }
    const res = await api.post('/resume/optimize');
    return res.data;
  },
  async careerAnalysis() {
    const res = await api.post('/resume/career-analysis');
    return res.data as {
      target_role: string;
      confidence: number;
      reasoning: string;
      match_score: number;
      level: string;
      role_analysis: string;
      readiness_score: number;
      readiness_summary: string;
      present_skills: string[];
      missing_skills: string[];
      missing_skills_detailed: {
        skill: string;
        priority: 'High' | 'Medium' | 'Low';
        why_it_matters: string;
        how_to_learn: string[];
        project_idea: string;
      }[];
      missing_experience: string[];
      recommended_projects: string[];
      action_plan: { day: string; focus: string }[];
      career_guidance: string;
      resume_improvements: string[];
      _error?: boolean;
    };
  },
};

export const internshipService = {
  async getAll(params?: { page?: number; limit?: number; search?: string }) {
    const res = await api.get('/internships', { params });
    return res.data;
  },
  async getById(id: number) {
    const res = await api.get(`/internships/${id}`);
    return res.data;
  },
  async explainMatch(internshipId: string | number) {
    const res = await api.get(`/internships/${internshipId}/explain`);
    // Phase 3 grounded explanation. Every skill named inside `explanation` is
    // guaranteed to be a member of matched_skills / missing_skills — the backend
    // discards any LLM output that references anything else.
    return res.data as {
      internship_id: number;
      title: string | null;
      company: string | null;
      match_score: number;
      match_label: string | null;
      matched_skills: string[];
      missing_skills: string[];
      explanation: {
        matched_skill_explanations: { skill: string; explanation: string }[];
        missing_skill_advice: { skill: string; advice: string }[];
        summary: string;
      };
      source: 'cache' | 'llm' | 'fallback';
    };
  },
  async getSkillGap(internshipId: string | number) {
    const res = await api.get(`/internships/${internshipId}/skill-gap`);
    // Returns: { matched_skills: string[], missing_skills: string[], match_percentage: number }
    return res.data;
  },
  async getSkillSimulations(internshipId: string | number) {
    const res = await api.get(`/internships/${internshipId}/skill-gap/simulations`);
    // Returns: { current_pct: number, simulations: [{skill, simulated_pct, delta_pct, new_label}] }
    return res.data as {
      current_pct: number;
      simulations: { skill: string; simulated_pct: number; delta_pct: number; new_label: string }[];
    };
  },
  async getMatchInsights(internshipId: string | number) {
    const res = await api.get(`/internships/${internshipId}/match-insights`);
    // Role-aware, stack-aware insight bundle. match_percentage is the SAME
    // weighted skill-coverage score as /skill-gap — enriched, never a second number.
    return res.data as {
      role_type: string;
      role_label: string;
      stack_type: string;
      stack_label: string;
      match_percentage: number;
      matched_skills: string[];
      missing_skills: { core: string[]; secondary: string[]; optional: string[] };
      explanation: string;
      match_reasons: string[];
      recommendation: string;
      top_missing_skill: string;
      skill_impacts: { skill: string; impact: number }[];
    };
  },
};

export const internshipStatsService = {
  async get(token?: string) {
    const res = await api.get('/internships/stats');
    return res.data as {
      total_positions: number;
      new_this_week: number;
      high_match: number;
      saved: number;
    };
  },
};

export const recommendationService = {
  async get() {
    const res = await api.get('/recommendations');
    return res.data;
  },
  async refresh() {
    const res = await api.post('/recommendations/refresh');
    return res.data;
  },
};

export const careerService = {
  async getPaths() {
    const res = await api.get('/career/paths');
    return res.data;
  },
};

export const applicationService = {
  async getAll(status?: string) {
    const res = await api.get('/applications', { params: { status } });
    return res.data;
  },
  async create(internship_id: number, status: string = 'saved') {
    const res = await api.post('/applications', { internship_id, status });
    return res.data;
  },
  async update(id: number, data: { status?: string; notes?: string }) {
    const res = await api.patch(`/applications/${id}`, data);
    return res.data;
  },
  async delete(id: number) {
    await api.delete(`/applications/${id}`);
  },
};

export const boltService = {
  async chat(message: string, session_id: string) {
    const res = await api.post('/bolt/chat', { message, session_id });
    return res.data;
  },
  async getHistory(session_id: string) {
    const res = await api.get('/bolt/history', { params: { session_id } });
    return res.data;
  },
};

export const interviewService = {
  async start(internship_id: number) {
    const res = await api.post('/interview/start', { internship_id });
    return res.data;
  },
  async submitAnswer(session_id: string, question_id: number, answer: string) {
    const res = await api.post('/interview/answer', { session_id, question_id, answer_text: answer });
    return res.data;
  },
  async complete(session_id: string) {
    const res = await api.post('/interview/complete', { session_id });
    return res.data;
  },
  async getReport(session_id: string) {
    const res = await api.get(`/interview/report/${session_id}`);
    return res.data;
  },
  async getHistory() {
    const res = await api.get('/interview/history');
    return res.data;
  },
  async getQuestions(sessionId: string) {
    const res = await api.get(`/interview/questions/${sessionId}`);
    return res.data;
  },
};

export const linkedinService = {
  async analyze(payload: any) {
    const res = await api.post('/linkedin/analyze', payload);
    return res.data;
  },
  async getLatest() {
    const res = await api.get('/linkedin/latest');
    return res.data;
  },
};

export const resumeBuilderService = {
  async startSession(template_id: string = 'modern') {
    const res = await api.post('/resume-agent/start-session', { template_id });
    return res.data;
  },
  async submitAnswer(session_id: string, step: any, answer: string) {
    const res = await api.post('/resume-agent/answer', { session_id, message: answer });
    return res.data;
  },
  async getSession(session_id: string) {
    const res = await api.get(`/resume-agent/session/${session_id}`);
    return res.data;
  },
  async exportPdf(session_id: string) {
    const res = await api.post('/resume-agent/export-pdf', { session_id }, { responseType: 'blob' });
    return res.data;
  },
  async exportDocx(session_id: string) {
    const res = await api.post('/resume-agent/export-docx', { session_id }, { responseType: 'blob' });
    return res.data;
  },
};

export const notificationService = {
  async getAll() {
    const res = await api.get('/notifications');
    return res.data;
  },
  async markRead(id: number) {
    await api.patch(`/notifications/${id}/read`);
  },
  async markAllRead() {
    await api.patch('/notifications/read-all');
  },
};










export const draftsService = {
  async generate(internship_id: number) {
    const res = await api.post('/drafts/generate', { internship_id });
    return res.data;
  },
  async getAll() {
    const res = await api.get('/drafts');
    return res.data;
  },
  async update(id: number, content: string) {
    const res = await api.patch(`/drafts/${id}`, { content });
    return res.data;
  },
  async approve(id: number) {
    const res = await api.patch(`/drafts/${id}/approve`);
    return res.data;
  },
  async discard(id: number) {
    await api.delete(`/drafts/${id}`);
  },
};
