import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Alert, Button, Card } from '@/components/UI';
import * as t from '@/types';

export function OrdersPage() {
  const navigate = useNavigate();
  const { user, isGuest } = useAuth();
  const [accountInfo, setAccountInfo] = useState<{ masked_email: string } | null>(null);
  const [orders, setOrders] = useState<t.Order[]>([]);
  const [latestStatuses, setLatestStatuses] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const formatCreatedAt = (value: string): string =>
    new Date(value).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  useEffect(() => {
    const loadData = async () => {
      try {
        setError('');
        if (isGuest) {
          setAccountInfo({ masked_email: user?.email || 'Guest user' });
          setOrders([]);
        } else {
          const [accData, ordersData] = await Promise.all([
            apiClient.getAccountMe(),
            apiClient.getUserOrders(),
          ]);
          setAccountInfo({ masked_email: accData.email_masked || 'Unknown account' });
          setOrders(ordersData);

          const statusEntries = await Promise.all(
            ordersData.map(async (order) => {
              const timeline = await apiClient.getOrderTimeline(order.order_id);
              return [order.order_id, timeline.current_status] as const;
            })
          );
          setLatestStatuses(Object.fromEntries(statusEntries));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load orders');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isGuest, user?.email]);

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading orders...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Card>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">My Orders</h2>
        <p className="text-sm text-gray-600 mb-2">Account: {accountInfo?.masked_email}</p>
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
                  <button
                    type="button"
                    onClick={() => navigate(`/orders/${order.order_id}`)}
                    className="text-left"
                  >
                    <p className="font-semibold text-gray-900">{order.order_id}</p>
                    <p className="text-sm text-gray-500">
                      Latest timeline status: {latestStatuses[order.order_id] || 'loading...'}
                    </p>
                  </button>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => navigate(`/orders/${order.order_id}`)} variant="outline">
                      View Order
                    </Button>
                    <Button size="sm" onClick={() => navigate(`/orders/${order.order_id}/timeline`)}>
                      View Timeline
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-gray-600">
                  Created: {formatCreatedAt(order.created_at)}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}