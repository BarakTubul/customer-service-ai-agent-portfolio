import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Card, Alert } from '@/components/UI';

export function DashboardPage() {
  const { user, isGuest } = useAuth();
  const [accountInfo, setAccountInfo] = useState<{ masked_email: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setError('');
        if (isGuest) {
          console.debug('[dashboard] guest session detected, skipping account/order fetch');
          setAccountInfo({ masked_email: user?.email || 'Guest user' });
        } else {
          const accData = await apiClient.getAccountMe();
          setAccountInfo({ masked_email: accData.email_masked || 'Unknown account' });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isGuest, user?.email]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {/* Profile Section */}
      <Card>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Profile</h2>
        <div className="space-y-2">
          <p className="text-gray-700">
            <span className="font-semibold">Email:</span> {accountInfo?.masked_email}
          </p>
          <p className="text-gray-700">
            <span className="font-semibold">Status:</span>{' '}
            {isGuest ? (
              <span className="text-orange-600">🔓 Guest Access (Limited functionality)</span>
            ) : user?.is_verified ? (
              <span className="text-green-600">✓ Verified Account</span>
            ) : (
              <span className="text-yellow-600">⏳ Pending Verification</span>
            )}
          </p>
          {isGuest && (
            <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded">
              <p className="text-sm text-orange-800">
                You're accessing as a guest. Some features like refunds are limited.{' '}
                <button className="text-blue-600 hover:underline font-semibold">
                  Create an account
                </button>
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
