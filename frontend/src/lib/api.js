import axios from 'axios';

// In production, use relative URL (same domain). In development, use localhost:8000
const getApiUrl = () => {
  // If explicitly set via env var, use that
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL + '/api';
  }
  
  // In production (deployed), use relative path (same domain as frontend)
  if (process.env.NODE_ENV === 'production') {
    return window.location.origin + '/api';
  }
  
  // In development, use localhost
  return 'http://localhost:8000/api';
};

const API_URL = getApiUrl();

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
    // Handle 401 unauthorized
    if (error?.response?.status === 401) {
      try {
        localStorage.removeItem('token');
      } catch {}
      // Avoid redirect loop if already on login
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    
    // Handle errors with arraybuffer responseType
    // When responseType is arraybuffer and there's an error, 
    // axios stores the error message in response.data as ArrayBuffer
    if (error?.config?.responseType === 'arraybuffer' && error?.response?.data) {
      try {
        // Convert ArrayBuffer to text to get the actual error message
        const decoder = new TextDecoder('utf-8');
        const text = decoder.decode(error.response.data);
        const errorData = JSON.parse(text);
        error.response.data = errorData;
      } catch (e) {
        // If parsing fails, leave as is
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
  getAll: (status) => {
    if (status) {
      return api.get('/projects', { params: { status } });
    }
    return api.get('/projects');
  },
  update: (id, data) => api.patch(`/projects/${id}`, data),
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
  download: (id) => api.get(`/files/${id}/download`, {
    responseType: 'arraybuffer',
  }),
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