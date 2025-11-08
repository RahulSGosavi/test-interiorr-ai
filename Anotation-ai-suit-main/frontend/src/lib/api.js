import axios from 'axios';

const API_URL = (process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000') + '/api';

const api = axios.create({
  baseURL: API_URL,
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 globally: clear token and redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      try {
        localStorage.removeItem('token');
      } catch {}
      // Avoid redirect loop if already on login
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

export const authAPI = {
  signup: (data) => api.post('/auth/signup', data),
  login: (data) => api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
};

export const projectsAPI = {
  create: (data) => api.post('/projects', data),
  getAll: () => api.get('/projects'),
  delete: (id) => api.delete(`/projects/${id}`),
};

export const foldersAPI = {
  create: (projectId, data) => api.post(`/projects/${projectId}/folders`, data),
  getAll: (projectId) => api.get(`/projects/${projectId}/folders`),
  delete: (id) => api.delete(`/folders/${id}`),
};

export const filesAPI = {
  upload: (folderId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/folders/${folderId}/files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAll: (folderId) => api.get(`/folders/${folderId}/files`),
  getOne: (id) => api.get(`/files/${id}`),
  delete: (id) => api.delete(`/files/${id}`),
};

export const annotationsAPI = {
  save: (fileId, data) => api.post(`/files/${fileId}/annotations`, data),
  getAll: (fileId) => api.get(`/files/${fileId}/annotations`),
};

export const pricingAIAPI = {
  query: (data) => api.post('/pricing-ai/query', data),
};

export const messagesAPI = {
  create: (fileId, data) => api.post(`/files/${fileId}/messages`, data),
  getAll: (fileId) => api.get(`/files/${fileId}/messages`),
};