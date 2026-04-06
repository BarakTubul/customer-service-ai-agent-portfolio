import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Alert, Button, Card } from '@/components/UI';
import * as t from '@/types';

function formatCents(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100);
}

function formatCreatedAt(value: string): string {
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function OrderDetailPage() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { isGuest } = useAuth();
  const [order, setOrder] = useState<t.Order | null>(null);
  const [timelineStatus, setTimelineStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadOrder = async () => {
      if (!orderId) {
        setError('Missing order id');
        setLoading(false);
        return;
      }

      try {
        setError('');
        const [response, timelineResponse] = await Promise.all([
          apiClient.getOrderDetail(orderId),
          apiClient.getOrderTimeline(orderId),
        ]);
        setOrder(response);
        setTimelineStatus(timelineResponse.current_status);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load order');
      } finally {
        setLoading(false);
      }
    };

    loadOrder();
  }, [orderId]);

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading order...</div>;
  }

  if (!order) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-4">
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        <Button onClick={() => navigate('/dashboard')} variant="outline">
          Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Card className="bg-amber-50 border-amber-200">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Order Summary</h1>
            <p className="text-gray-600 mt-1">{order.order_id}</p>
          </div>
          <Button onClick={() => navigate(`/orders/${order.order_id}/timeline`)}>
            View Timeline
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 text-sm text-gray-700">
          <div>
            <p className="font-semibold text-gray-500">Latest timeline status</p>
            <p>{timelineStatus || order.status_label}</p>
          </div>
          <div>
            <p className="font-semibold text-gray-500">Created</p>
            <p>{formatCreatedAt(order.created_at)}</p>
          </div>
          <div>
            <p className="font-semibold text-gray-500">What was ordered</p>
            <p>{order.ordered_items_summary || 'No item summary available'}</p>
          </div>
          <div>
            <p className="font-semibold text-gray-500">Price</p>
            <p>{order.total_cents != null ? formatCents(order.total_cents) : 'Not available'}</p>
          </div>
          <div>
            <p className="font-semibold text-gray-500">ETA</p>
            <p>
              {order.eta_from && order.eta_to
                ? `${new Date(order.eta_from).toLocaleTimeString()} - ${new Date(order.eta_to).toLocaleTimeString()}`
                : 'Not available yet'}
            </p>
          </div>
        </div>

        <p className="mt-4 text-sm text-gray-600">The live progress appears in the timeline.</p>

        {isGuest && <p className="mt-4 text-sm text-orange-700">Guest accounts have limited order features.</p>}
      </Card>

      <Link to="/dashboard" className="text-blue-600 hover:underline text-sm font-semibold">
        Back to Dashboard
      </Link>
    </div>
  );
}