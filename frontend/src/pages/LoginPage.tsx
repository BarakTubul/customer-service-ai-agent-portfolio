import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button, Input, Alert, Card } from '@/components/UI';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('[auth] login failed', {
        email,
        error: err,
      });
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-900 mb-6 text-center">Login</h1>
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            type="email"
            label="Email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            label="Password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button
            type="submit"
            className="w-full !bg-blue-600 !text-white hover:!bg-blue-700"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </Button>
        </form>
        <div className="mt-6 space-y-2 text-center text-sm">
          <p className="text-gray-600">
            Don't have an account?{' '}
            <button
              onClick={() => navigate('/register')}
              className="text-blue-600 hover:underline font-semibold"
            >
              Register
            </button>
          </p>
          <p className="text-gray-600">
            Want to try as guest?{' '}
            <button
              onClick={() => navigate('/guest')}
              className="text-blue-600 hover:underline font-semibold"
            >
              Guest Access
            </button>
          </p>
          <p>
            <button
              onClick={() => navigate('/')}
              className="text-gray-500 hover:text-blue-600 hover:underline font-semibold"
            >
              Back to Home
            </button>
          </p>
        </div>
      </Card>
    </div>
  );
}
