import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button, Input, Alert, Card } from '@/components/UI';

export function GuestAccessPage() {
  const { guestAccess } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const guestEmail = email.trim() || `guest_${Date.now()}@guest.local`;
      await guestAccess(guestEmail);
      navigate('/dashboard');
    } catch (err) {
      console.error('[auth] guest access failed', {
        providedEmail: email,
        error: err,
      });
      setError(err instanceof Error ? err.message : 'Guest access failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-900 mb-2 text-center">Guest Access</h1>
        <p className="text-gray-600 text-center mb-6">
          Try our service without creating an account
        </p>
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            type="email"
            label="Email (Optional)"
            placeholder="you@example.com (optional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Accessing...' : 'Continue as Guest'}
          </Button>
        </form>
        <div className="mt-6 space-y-2 text-center text-sm text-gray-600">
          <p>
            Want to register?{' '}
            <button
              onClick={() => navigate('/register')}
              className="text-blue-600 hover:underline font-semibold"
            >
              Sign up
            </button>
          </p>
          <p>
            Already have an account?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-blue-600 hover:underline font-semibold"
            >
              Login
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
