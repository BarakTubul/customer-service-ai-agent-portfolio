import { useEffect, useMemo, useState } from 'react';

import { Alert, Button, Card } from '@/components/UI';
import { apiClient } from '@/services/apiClient';
import * as t from '@/types';

export function AdminRefundReviewPage() {
  const [queue, setQueue] = useState<t.ManualReviewQueueItem[]>([]);
  const [activeRequest, setActiveRequest] = useState<t.RefundRequest | null>(null);
  const [reviewerNote, setReviewerNote] = useState('');
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const activeEscalationStatus = activeRequest?.manual_review_handoff?.escalation_status || null;
  const queueCountLabel = useMemo(() => `${queue.length} queued`, [queue.length]);

  const loadQueue = async () => {
    setLoadingQueue(true);
    setError('');
    try {
      const response = await apiClient.listManualReviewQueue(100);
      setQueue(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load manual-review queue');
    } finally {
      setLoadingQueue(false);
    }
  };

  useEffect(() => {
    void loadQueue();
  }, []);

  const handleClaim = async (refundRequestId: string) => {
    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const claimed = await apiClient.claimManualReviewRequest(refundRequestId);
      setActiveRequest(claimed);
      setSuccess(`Claimed ${refundRequestId} for review.`);
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to claim request');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDecision = async (decision: 'resolved' | 'rejected') => {
    if (!activeRequest) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const decided = await apiClient.decideManualReviewRequest(
        activeRequest.refund_request_id,
        decision,
        reviewerNote
      );
      setActiveRequest(decided);
      setReviewerNote('');
      setSuccess(`Marked ${activeRequest.refund_request_id} as ${decision}.`);
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit review decision');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Manager Review Queue</h1>
        <Button onClick={() => void loadQueue()} disabled={loadingQueue || actionLoading} variant="outline">
          {loadingQueue ? 'Refreshing...' : 'Refresh Queue'}
        </Button>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Queued Requests</h2>
            <span className="text-sm text-gray-600">{queueCountLabel}</span>
          </div>

          {queue.length === 0 ? (
            <p className="text-sm text-gray-600">No queued manual-review requests.</p>
          ) : (
            <div className="space-y-3">
              {queue.map((item) => (
                <div
                  key={item.refund_request_id}
                  className="border border-gray-200 rounded-lg p-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{item.refund_request_id}</p>
                    <p className="text-xs text-gray-600">Order: {item.order_id}</p>
                    <p className="text-xs text-gray-600">
                      SLA: {new Date(item.handoff.sla_deadline_at).toLocaleString()}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => void handleClaim(item.refund_request_id)}
                    disabled={actionLoading}
                  >
                    Claim
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Active Manager Review</h2>
          {!activeRequest ? (
            <p className="text-sm text-gray-600">Claim a request to review and decide.</p>
          ) : (
            <div className="space-y-3">
              <p className="text-sm"><span className="font-semibold">Request:</span> {activeRequest.refund_request_id}</p>
              <p className="text-sm"><span className="font-semibold">Order:</span> {activeRequest.order_id}</p>
              <p className="text-sm"><span className="font-semibold">Escalation:</span> {activeEscalationStatus}</p>
              <textarea
                className="w-full border border-gray-300 rounded-md p-2 text-sm"
                rows={3}
                placeholder="Optional reviewer note"
                value={reviewerNote}
                onChange={(event) => setReviewerNote(event.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  variant="secondary"
                  onClick={() => void handleDecision('resolved')}
                  disabled={actionLoading || activeEscalationStatus !== 'in_review'}
                >
                  Resolve
                </Button>
                <Button
                  className="flex-1"
                  variant="outline"
                  onClick={() => void handleDecision('rejected')}
                  disabled={actionLoading || activeEscalationStatus !== 'in_review'}
                >
                  Reject
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
