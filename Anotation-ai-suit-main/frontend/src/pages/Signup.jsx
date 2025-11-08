import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { authAPI } from '@/lib/api';
import useStore from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { UserPlus, Sparkles } from 'lucide-react';

const Signup = () => {
  const navigate = useNavigate();
  const { setUser, setToken } = useStore();
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Map frontend fields to backend schema
      const username = formData.email.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '_');
      const payload = {
        email: formData.email,
        username,
        full_name: formData.name,
        password: formData.password,
      };
      const response = await authAPI.signup(payload);
      setToken(response.data.access_token);
      setUser(response.data.user);
      toast.success('Account created successfully!');
      navigate('/');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{
      background: 'linear-gradient(to bottom right, #f0f9ff, #e0f2fe, #fae8ff)'
    }}>
      <Card className="w-full max-w-md shadow-2xl border-0 animate-fade-in">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-3xl font-bold" className="font-semibold">
            Join Interior Design AI
          </CardTitle>
          <CardDescription className="text-base">
            Create your account to get started
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name" data-testid="signup-name-label">Full Name</Label>
              <Input
                id="name"
                type="text"
                placeholder="John Doe"
                autoComplete="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                data-testid="signup-name-input"
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" data-testid="signup-email-label">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                data-testid="signup-email-input"
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" data-testid="signup-password-label">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
                minLength={6}
                data-testid="signup-password-input"
                className="h-11"
              />
            </div>
            <Button
              type="submit"
              className="w-full h-11 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              disabled={loading}
              data-testid="signup-submit-button"
            >
              {loading ? (
                <span>Creating account...</span>
              ) : (
                <span className="flex items-center gap-2">
                  <UserPlus className="w-4 h-4" />
                  Create Account
                </span>
              )}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm">
            <span className="text-muted-foreground">Already have an account? </span>
            <Link to="/login" className="text-blue-600 hover:underline font-medium" data-testid="login-link">
              Sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Signup;