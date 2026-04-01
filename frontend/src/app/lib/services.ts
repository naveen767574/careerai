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
  async explainMatch(internshipId: string) {
    const res = await api.get(`/internships/${internshipId}/explain`);
    // Returns: { match_reasons: string[], missing_skills: string[], tip: string }
    return res.data;
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









