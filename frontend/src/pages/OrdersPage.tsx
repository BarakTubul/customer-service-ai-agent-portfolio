import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Alert, Button, Card } from '@/components/UI';
import * as t from '@/types';

export function OrdersPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isGuest } = useAuth();
  const [accountInfo, setAccountInfo] = useState<{ masked_email: string } | null>(null);
  const [orders, setOrders] = useState<t.Order[]>([]);
  const [latestStatuses, setLatestStatuses] = useState<Record<string, string>>({});
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [isStatusFilterTouched, setIsStatusFilterTouched] = useState(false);
  const [dateFromFilter, setDateFromFilter] = useState('');
  const [dateToFilter, setDateToFilter] = useState('');
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

  const getOrderStatus = (order: t.Order): string => latestStatuses[order.order_id] || order.status;

  const statusOptions = useMemo(() => {
    const statuses = new Set<string>();
    orders.forEach((order) => {
      statuses.add(getOrderStatus(order));
    });
    return Array.from(statuses).sort((a, b) => a.localeCompare(b));
  }, [orders, latestStatuses]);

  useEffect(() => {
    if (!isStatusFilterTouched) {
      setSelectedStatuses(statusOptions);
    }
  }, [statusOptions, isStatusFilterTouched]);

  useEffect(() => {
    setDateFromFilter('');
    setDateToFilter('');
    setIsStatusFilterTouched(false);
    setSelectedStatuses(statusOptions);
  }, [location.key]);

  const toggleStatus = (status: string) => {
    setIsStatusFilterTouched(true);
    setSelectedStatuses((current) => {
      if (current.includes(status)) {
        return current.filter((item) => item !== status);
      }
      return [...current, status];
    });
  };

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const status = getOrderStatus(order);
      if (selectedStatuses.length > 0 && !selectedStatuses.includes(status)) {
        return false;
      }

      const created = new Date(order.created_at);

      if (dateFromFilter) {
        const from = new Date(dateFromFilter);
        if (created < from) {
          return false;
        }
      }

      if (dateToFilter) {
        const to = new Date(dateToFilter);
        to.setHours(23, 59, 59, 999);
        if (created > to) {
          return false;
        }
      }

      return true;
    });
  }, [orders, latestStatuses, selectedStatuses, dateFromFilter, dateToFilter]);

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

        <div className="grid gap-4 md:grid-cols-4 mb-4 rounded-xl border border-gray-200 p-4 bg-gray-50">
          <div className="md:col-span-2">
            <p className="block text-xs font-semibold text-gray-600 mb-2">Statuses</p>
            <div className="flex flex-wrap gap-3">
              {statusOptions.map((status) => (
                <label key={status} className="inline-flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={selectedStatuses.includes(status)}
                    onChange={() => toggleStatus(status)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span>{status}</span>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">Choose one or more statuses to display.</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Created from (date)</label>
            <input
              type="date"
              value={dateFromFilter}
              onChange={(event) => setDateFromFilter(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Created to (date)</label>
            <input
              type="date"
              value={dateToFilter}
              onChange={(event) => setDateToFilter(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setIsStatusFilterTouched(false);
                setSelectedStatuses(statusOptions);
                setDateFromFilter('');
                setDateToFilter('');
              }}
            >
              Clear Filters
            </Button>
          </div>
        </div>

        {filteredOrders.length === 0 ? (
          <p className="text-gray-500">No orders found</p>
        ) : (
          <div className="space-y-3">
            {filteredOrders.map((order) => (
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
                      Latest timeline status: {getOrderStatus(order)}
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