import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Button, Card, Alert } from '@/components/UI';
import * as t from '@/types';

export function DashboardPage() {
  const { user, isGuest } = useAuth();
  const [accountInfo, setAccountInfo] = useState<{ masked_email: string } | null>(null);
  const [orders, setOrders] = useState<t.Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [orderTimeline, setOrderTimeline] = useState<t.OrderTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setError('');
        if (isGuest) {
          console.debug('[dashboard] guest session detected, skipping account/order fetch');
          setAccountInfo({ masked_email: user?.email || 'Guest user' });
          setOrders([]);
        } else {
          const [accData, ordersData] = await Promise.all([
            apiClient.getAccountMe(),
            apiClient.getUserOrders(),
          ]);
          setAccountInfo(accData);
          setOrders(ordersData);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isGuest, user?.email]);

  const loadOrderTimeline = async (orderId: string) => {
    try {
      const timeline = await apiClient.getOrderTimeline(orderId);
      setOrderTimeline(timeline);
      setSelectedOrderId(orderId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline');
    }
  };

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

      {/* Orders Section */}
      <Card>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Your Orders</h2>
        {orders.length === 0 ? (
          <p className="text-gray-500">No orders found</p>
        ) : (
          <div className="space-y-3">
            {orders.map((order) => (
              <div
                key={order.order_id}
                className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-semibold text-gray-900">{order.order_id}</p>
                    <p className="text-sm text-gray-500">{order.status_label}</p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => loadOrderTimeline(order.order_id)}
                    variant={selectedOrderId === order.order_id ? 'primary' : 'outline'}
                  >
                    View Timeline
                  </Button>
                </div>
                <p className="text-sm text-gray-600">
                  Created: {new Date(order.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Timeline Section */}
      {orderTimeline && (
        <Card className="bg-blue-50">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Timeline for {orderTimeline.order_id}
          </h2>
          <div className="space-y-3">
            <p className="text-sm font-semibold text-gray-700">
              Current Status: {orderTimeline.current_status}
            </p>
            {orderTimeline.timeline.map((event, idx) => (
              <div key={idx} className="flex gap-4">
                <div className="w-2 h-2 bg-blue-600 rounded-full mt-1.5 flex-shrink-0"></div>
                <div>
                  <p className="font-semibold text-gray-900">{event.event}</p>
                  <p className="text-sm text-gray-600">{event.date}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
