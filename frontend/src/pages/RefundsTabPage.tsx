import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Alert, Button, Card } from '@/components/UI';
import {
  formatRefundDecisionLabel,
  formatRefundReasonLabel,
  formatRefundResolutionLabel,
  formatRefundStatusLabel,
} from '@/lib/refundCopy';
import * as t from '@/types';

const PAGE_SIZE = 8;

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'approved', label: 'Approved' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'denied', label: 'Denied' },
  { value: 'pending_manual_review', label: 'Waiting for review' },
  { value: 'resolved', label: 'Resolved' },
];

function formatCreatedAt(value: string): string {
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCents(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100);
}

function getStatusBadgeColor(status: string): string {
  switch (status) {
    case 'approved':
      return 'bg-green-100 text-green-900';
    case 'denied':
      return 'bg-red-100 text-red-900';
    case 'pending':
      return 'bg-yellow-100 text-yellow-900';
    case 'resolved':
      return 'bg-green-100 text-green-900';
    case 'queued':
      return 'bg-blue-100 text-blue-900';
    case 'in_review':
      return 'bg-orange-100 text-orange-900';
    case 'rejected':
      return 'bg-red-100 text-red-900';
    default:
      return 'bg-gray-100 text-gray-900';
  }
}

export function RefundsTabPage() {
  const navigate = useNavigate();
  const { isGuest } = useAuth();
  const [refunds, setRefunds] = useState<t.RefundRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedRefund, setExpandedRefund] = useState<string | null>(null);

  useEffect(() => {
    const loadRefunds = async () => {
      setLoading(true);
      try {
        setError('');
        if (isGuest) {
          setRefunds([]);
          setTotal(0);
        } else {
          const data = await apiClient.listUserRefundRequests({
            limit: PAGE_SIZE,
            offset: page * PAGE_SIZE,
            status: statusFilter || undefined,
            query: query || undefined,
          });
          setRefunds(data.items);
          setTotal(data.total);
          setExpandedRefund(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load refund requests');
      } finally {
        setLoading(false);
      }
    };

    loadRefunds();
  }, [isGuest, page, query, statusFilter]);

  const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;
  const startItem = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const endItem = Math.min((page + 1) * PAGE_SIZE, total);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(0);
    setQuery(queryInput.trim());
  };

  const handleStatusChange = (value: string) => {
    setPage(0);
    setStatusFilter(value);
  };

  const handleClearFilters = () => {
    setPage(0);
    setQueryInput('');
    setQuery('');
    setStatusFilter('');
  };

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading refund requests...</div>;
  }

  if (isGuest) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <Card className="bg-orange-50 border-2 border-orange-300">
          <h2 className="text-2xl font-bold text-orange-900 mb-2">Refunds - Guest Limitation</h2>
          <p className="text-orange-700 mb-4">
            Refund tracking is only available for registered users. Please create an account to access this feature.
          </p>
          <Button onClick={() => navigate('/login')} variant="outline">
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Card>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Refund Applications</h2>
        <p className="text-sm text-gray-600 mb-4">
          Search and filter your refund applications without loading the full history at once.
        </p>

        <form onSubmit={handleSearchSubmit} className="grid gap-3 md:grid-cols-[1fr_220px_auto] md:items-end mb-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2" htmlFor="refund-search">
              Search
            </label>
            <input
              id="refund-search"
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="Order ID, request ID, or reason"
              className="w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2" htmlFor="refund-status-filter">
              Status
            </label>
            <select
              id="refund-status-filter"
              value={statusFilter}
              onChange={(event) => handleStatusChange(event.target.value)}
              className="w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {STATUS_FILTER_OPTIONS.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              Search
            </Button>
            <Button type="button" variant="outline" className="w-full" onClick={handleClearFilters} disabled={loading}>
              Clear
            </Button>
          </div>
        </form>

        <div className="flex flex-wrap items-center justify-between gap-3 mb-4 text-sm text-gray-600">
          <p>
            Showing {startItem === 0 ? 0 : startItem}-{endItem} of {total} requests
          </p>
          <p>
            Page {totalPages === 0 ? 0 : page + 1} of {totalPages}
          </p>
        </div>

        {refunds.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-4">
              {query || statusFilter
                ? 'No refund applications match your current search or filter.'
                : "You haven't submitted any refund applications yet."}
            </p>
            {query || statusFilter ? (
              <Button onClick={handleClearFilters} variant="outline">
                Clear filters
              </Button>
            ) : (
              <Button onClick={() => navigate('/orders')} variant="outline">
                Go to Orders
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {refunds.map((refund) => (
              <div
                key={refund.refund_request_id}
                className="border border-gray-200 rounded-lg overflow-hidden hover:bg-gray-50 transition"
              >
                <button
                  type="button"
                  onClick={() =>
                    setExpandedRefund(
                      expandedRefund === refund.refund_request_id ? null : refund.refund_request_id
                    )
                  }
                  className="w-full text-left p-4 flex items-center justify-between hover:bg-gray-50"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <p className="font-semibold text-gray-900">Order {refund.order_id}</p>
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${getStatusBadgeColor(
                          refund.status
                        )}`}
                      >
                        {refund.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">
                      Request ID: {refund.refund_request_id}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">Submitted: {formatCreatedAt(refund.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {refund.refundable_amount && (
                      <p className="font-semibold text-gray-900">
                        {formatCents(refund.refundable_amount.value * 100, refund.refundable_amount.currency)}
                      </p>
                    )}
                    <svg
                      className={`w-5 h-5 text-gray-400 transform transition ${
                        expandedRefund === refund.refund_request_id ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 14l-7 7m0 0l-7-7m7 7V3"
                      />
                    </svg>
                  </div>
                </button>

                {expandedRefund === refund.refund_request_id && (
                  <div className="border-t border-gray-200 bg-gray-50 p-4 space-y-3">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase">Reason for Refund</p>
                        <p className="text-sm text-gray-900 mt-1">
                          {formatRefundReasonLabel(refund.reason_code)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase">Status</p>
                        <p className="text-sm text-gray-900 mt-1">{formatRefundStatusLabel(refund.status)}</p>
                      </div>
                      {refund.status_reason && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase">Status Reason</p>
                          <p className="text-sm text-gray-900 mt-1">
                            {formatRefundDecisionLabel(refund.status_reason)}
                          </p>
                        </div>
                      )}
                      {refund.resolution_action && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase">Resolution Action</p>
                          <p className="text-sm text-gray-900 mt-1">
                            {formatRefundResolutionLabel(refund.resolution_action)}
                          </p>
                        </div>
                      )}
                      {refund.policy_version && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase">Policy Version</p>
                          <p className="text-sm text-gray-900 mt-1">{refund.policy_version}</p>
                        </div>
                      )}
                      {refund.refundable_amount && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase">Refund Amount</p>
                          <p className="text-sm text-gray-900 mt-1">
                            {formatCents(refund.refundable_amount.value * 100, refund.refundable_amount.currency)}
                          </p>
                        </div>
                      )}
                    </div>

                    {refund.decision_reason_codes && refund.decision_reason_codes.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Decision Reasons</p>
                        <div className="flex flex-wrap gap-2">
                          {refund.decision_reason_codes.map((code) => (
                            <span
                              key={code}
                              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
                            >
                              {formatRefundDecisionLabel(code)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {refund.manual_review_handoff && (
                      <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3">
                        <p className="text-xs font-semibold text-yellow-900 uppercase mb-1">
                          Manual Review
                        </p>
                        <p className="text-sm text-yellow-800">
                          This refund is queued for manual review in the{' '}
                          <span className="font-semibold">{refund.manual_review_handoff.queue_name}</span> queue.
                        </p>
                        {refund.manual_review_handoff.sla_deadline_at && (
                          <p className="text-xs text-yellow-700 mt-2">
                            SLA deadline:{' '}
                            {new Date(refund.manual_review_handoff.sla_deadline_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                    )}
                    <div className="flex gap-2 pt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate(`/orders/${refund.order_id}`)}
                      >
                        View Order
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex flex-wrap items-center justify-between gap-3 mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => setPage((currentPage) => Math.max(0, currentPage - 1))}
              disabled={page === 0 || loading}
            >
              Previous
            </Button>
            <p className="text-sm text-gray-600">
              Page {page + 1} of {totalPages}
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => setPage((currentPage) => Math.min(totalPages - 1, currentPage + 1))}
              disabled={page >= totalPages - 1 || loading}
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      <Button onClick={() => navigate('/orders')} variant="outline">
        Back to Orders
      </Button>
    </div>
  );
}
