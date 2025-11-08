import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import useStore from '@/lib/store';
import Login from '@/pages/Login';
import Signup from '@/pages/Signup';
import Dashboard from '@/pages/Dashboard';
import ProjectFiles from '@/pages/ProjectFiles';
import FileMainOptions from '@/pages/FileMainOptions';
import AnnotationPage from '@/pages/AnnotationPage';
import PricingAIPage from '@/pages/PricingAIPage';
import DiscussionPage from '@/pages/DiscussionPage';
import '@/App.css';

const ProtectedRoute = ({ children }) => {
  const token = useStore((state) => state.token);
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/project/:projectId"
            element={
              <ProtectedRoute>
                <ProjectFiles />
              </ProtectedRoute>
            }
          />
          <Route
            path="/file/:fileId"
            element={
              <ProtectedRoute>
                <FileMainOptions />
              </ProtectedRoute>
            }
          />
          <Route
            path="/file/:fileId/annotate"
            element={
              <ProtectedRoute>
                <AnnotationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/file/:fileId/pricing-ai"
            element={
              <ProtectedRoute>
                <PricingAIPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/file/:fileId/discussion"
            element={
              <ProtectedRoute>
                <DiscussionPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;