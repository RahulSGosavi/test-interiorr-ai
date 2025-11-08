import { create } from 'zustand';

const useStore = create((set) => ({
  user: null,
  token: localStorage.getItem('token') || null,
  
  setUser: (user) => set({ user }),
  setToken: (token) => {
    localStorage.setItem('token', token);
    set({ token });
  },
  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null });
  },
  
  // Current project/folder/file
  currentProject: null,
  currentFolder: null,
  currentFile: null,
  
  setCurrentProject: (project) => set({ currentProject: project }),
  setCurrentFolder: (folder) => set({ currentFolder: folder }),
  setCurrentFile: (file) => set({ currentFile: file }),
}));

export default useStore;