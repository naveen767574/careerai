import api from './api';

export interface User {
  id: number;
  name: string;
  email: string;
}

export const authService = {
  async login(email: string, password: string): Promise<string> {
    const res = await api.post('/auth/login', { email, password });
    const token = res.data.access_token;
    localStorage.setItem('token', token);
    const user = await authService.getMe();
    localStorage.setItem('user', JSON.stringify(user));
    return token;
  },

  async register(name: string, email: string, password: string): Promise<void> {
    await api.post('/auth/register', { name, email, password });
  },

  async getMe(): Promise<User> {
    const res = await api.get('/auth/me');
    return res.data;
  },

  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  },

  getUser(): User | null {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  },

  isLoggedIn(): boolean {
    return !!localStorage.getItem('token');
  },
};
