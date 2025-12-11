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
    // Clear all localStorage on logout
    localStorage.clear();
    set({ user: null, token: null, currentProject: null, currentFolder: null, currentFile: null });
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