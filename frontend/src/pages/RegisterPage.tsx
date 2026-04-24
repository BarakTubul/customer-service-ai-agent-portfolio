import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button, Input, Alert, Card } from '@/components/UI';

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [address, setAddress] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (!fullName.trim()) {
      setError('Full name is required');
      return;
    }

    if (!dateOfBirth) {
      setError('Date of birth is required');
      return;
    }

    if (!address.trim()) {
      setError('Address is required');
      return;
    }

    setLoading(true);
    try {
      await register(email, password, {
        fullName: fullName.trim(),
        dateOfBirth,
        address: address.trim(),
      });
      navigate('/dashboard');
    } catch (err) {
      console.error('[auth] registration failed', {
        email,
        error: err,
      });
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-900 mb-6 text-center">Register</h1>
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
            type="text"
            label="Full Name"
            placeholder="Jane Doe"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
          <Input
            type="date"
            label="Date of Birth"
            value={dateOfBirth}
            onChange={(e) => setDateOfBirth(e.target.value)}
            required
          />
          <Input
            type="text"
            label="Address"
            placeholder="123 Main St, City"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
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
          <Input
            type="password"
            label="Confirm Password"
            placeholder="••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Creating account...' : 'Register'}
          </Button>
        </form>
        <div className="mt-6 space-y-2 text-center text-sm text-gray-600">
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
