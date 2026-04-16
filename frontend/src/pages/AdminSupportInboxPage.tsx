import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { Alert, Button, Card, Input } from '@/components/UI';
import { apiClient } from '@/services/apiClient';
import * as t from '@/types';

type InboxSection = 'queue' | 'assigned';

interface SupportThreadMessage {
  message_id: string;
  sender_role: string;
  body: string;
  created_at: string;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function conversationSummary(conversation: t.SupportConversationResponse): string {
  const parts = [conversation.status, conversation.priority];
  if (conversation.assigned_admin_user_id) {
    parts.push(`admin ${conversation.assigned_admin_user_id}`);
  }
  return parts.join(' • ');
}

export function AdminSupportInboxPage() {
  const [queue, setQueue] = useState<t.SupportConversationResponse[]>([]);
  const [assigned, setAssigned] = useState<t.SupportConversationResponse[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<t.SupportConversationResponse | null>(null);
  const [messages, setMessages] = useState<SupportThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [activeSection, setActiveSection] = useState<InboxSection>('queue');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [threadLoading, setThreadLoading] = useState(false);

  const selectedConversationState = useMemo(() => {
    if (!selectedConversation) {
      return null;
    }
    return selectedConversation;
  }, [selectedConversation]);

  const loadInbox = async () => {
    setLoading(true);
    setError('');
    try {
      const [queueResponse, assignedResponse] = await Promise.all([
        apiClient.listSupportQueue(100),
        apiClient.listAssignedSupportConversations(100),
      ]);
      setQueue(queueResponse.items);
      setAssigned(assignedResponse.items);

      if (!selectedConversationId && queueResponse.items.length > 0) {
        setSelectedConversationId(queueResponse.items[0].conversation_id);
        setActiveSection('queue');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support inbox');
    } finally {
      setLoading(false);
    }
  };

  const loadThread = async (conversationId: string) => {
    setThreadLoading(true);
    setError('');
    try {
      const [conversationResponse, messageResponse] = await Promise.all([
        apiClient.getSupportConversation(conversationId),
        apiClient.listSupportMessages(conversationId, 100),
      ]);

      setSelectedConversation(conversationResponse);
      setMessages(
        messageResponse.items.map((item) => ({
          message_id: item.message_id,
          sender_role: item.sender_role,
          body: item.body,
          created_at: item.created_at,
        }))
      );
      setSelectedConversationId(conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support conversation');
    } finally {
      setThreadLoading(false);
    }
  };

  useEffect(() => {
    void loadInbox();
  }, []);

  useEffect(() => {
    if (!selectedConversationId) {
      return;
    }
    void loadThread(selectedConversationId);
  }, [selectedConversationId]);

  useEffect(() => {
    if (!selectedConversationId) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadInbox();
      void loadThread(selectedConversationId);
    }, 4000);

    return () => window.clearInterval(intervalId);
  }, [selectedConversationId]);

  const handleSelectConversation = (conversationId: string, section: InboxSection) => {
    setActiveSection(section);
    setSelectedConversationId(conversationId);
  };

  const handleClaim = async (conversationId: string) => {
    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const claimed = await apiClient.claimSupportConversation(conversationId);
      setSuccess(`Claimed ${conversationId}.`);
      setSelectedConversation(claimed);
      setSelectedConversationId(conversationId);
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to claim conversation');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRelease = async () => {
    if (!selectedConversation) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const released = await apiClient.releaseSupportConversation(selectedConversation.conversation_id);
      setSuccess(`Released ${selectedConversation.conversation_id}.`);
      setSelectedConversation(released);
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to release conversation');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClose = async () => {
    if (!selectedConversation) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const closed = await apiClient.closeSupportConversation(selectedConversation.conversation_id);
      setSuccess(`Closed ${selectedConversation.conversation_id}.`);
      setSelectedConversation(closed);
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to close conversation');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSend = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedConversation || !input.trim()) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      await apiClient.sendSupportMessage(selectedConversation.conversation_id, input.trim());
      setInput('');
      setSuccess('Reply sent.');
      await loadThread(selectedConversation.conversation_id);
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reply');
    } finally {
      setActionLoading(false);
    }
  };

  const threadStatus = selectedConversationState
    ? selectedConversationState.status === 'closed'
      ? 'Closed'
      : selectedConversationState.assigned_admin_user_id
        ? `Assigned to ${selectedConversationState.assigned_admin_user_id}`
        : 'Unassigned'
    : 'Select a conversation';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-white px-4 py-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-3 rounded-3xl border border-cyan-100 bg-white/90 p-6 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-700">Admin support inbox</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Live customer conversations</h1>
            <p className="mt-2 text-sm text-slate-600">Claim a conversation, reply in-thread, then release or close it when finished.</p>
          </div>
          <Button onClick={() => void loadInbox()} disabled={loading || actionLoading} variant="outline">
            {loading ? 'Refreshing...' : 'Refresh inbox'}
          </Button>
        </div>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <div className="grid gap-6 lg:grid-cols-[1.05fr_1.15fr]">
          <Card className="border border-slate-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Queues</h2>
                <p className="text-sm text-slate-500">Open and assigned conversations.</p>
              </div>
              <div className="flex gap-2 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setActiveSection('queue')}
                  className={`rounded-full px-3 py-1.5 ${activeSection === 'queue' ? 'bg-cyan-600 text-white' : 'bg-slate-100 text-slate-600'}`}
                >
                  Queue ({queue.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSection('assigned')}
                  className={`rounded-full px-3 py-1.5 ${activeSection === 'assigned' ? 'bg-cyan-600 text-white' : 'bg-slate-100 text-slate-600'}`}
                >
                  Assigned ({assigned.length})
                </button>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {activeSection === 'queue' ? (
                queue.length === 0 ? (
                  <p className="text-sm text-slate-500">No open conversations in the queue.</p>
                ) : (
                  queue.map((conversation) => (
                    <div
                      key={conversation.conversation_id}
                      className={`rounded-2xl border p-4 transition ${selectedConversationId === conversation.conversation_id ? 'border-cyan-300 bg-cyan-50' : 'border-slate-200 bg-slate-50'}`}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <button
                          type="button"
                          className="text-left"
                          onClick={() => handleSelectConversation(conversation.conversation_id, 'queue')}
                        >
                          <p className="font-semibold text-slate-900">{conversation.conversation_id}</p>
                          <p className="text-xs text-slate-600">Customer {conversation.customer_user_id}</p>
                          <p className="text-xs text-slate-600">{conversationSummary(conversation)}</p>
                          <p className="text-xs text-slate-500">Created {formatDateTime(conversation.created_at)}</p>
                        </button>
                        <Button size="sm" onClick={() => void handleClaim(conversation.conversation_id)} disabled={actionLoading}>
                          Claim
                        </Button>
                      </div>
                    </div>
                  ))
                )
              ) : assigned.length === 0 ? (
                <p className="text-sm text-slate-500">No assigned conversations.</p>
              ) : (
                assigned.map((conversation) => (
                  <div
                    key={conversation.conversation_id}
                    className={`rounded-2xl border p-4 transition ${selectedConversationId === conversation.conversation_id ? 'border-cyan-300 bg-cyan-50' : 'border-slate-200 bg-slate-50'}`}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => handleSelectConversation(conversation.conversation_id, 'assigned')}
                    >
                      <p className="font-semibold text-slate-900">{conversation.conversation_id}</p>
                      <p className="text-xs text-slate-600">Customer {conversation.customer_user_id}</p>
                      <p className="text-xs text-slate-600">{conversationSummary(conversation)}</p>
                      <p className="text-xs text-slate-500">Updated {formatDateTime(conversation.updated_at)}</p>
                    </button>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card className="border border-slate-200 bg-white shadow-xl">
            {!selectedConversation ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center text-center text-slate-500">
                <div>
                  <p className="text-lg font-semibold text-slate-900">No conversation selected</p>
                  <p className="mt-2 text-sm">Choose a queue item or assigned conversation to open the thread.</p>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[28rem] flex-col">
                <div className="border-b border-slate-100 pb-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">Conversation</p>
                      <h2 className="mt-1 text-xl font-bold text-slate-900">{selectedConversation.conversation_id}</h2>
                      <p className="text-sm text-slate-500">Customer {selectedConversation.customer_user_id}</p>
                      <p className="text-sm text-slate-500">{threadStatus}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => void handleClaim(selectedConversation.conversation_id)} disabled={actionLoading}>
                        Claim
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => void handleRelease()} disabled={actionLoading || !selectedConversation.assigned_admin_user_id}>
                        Release
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => void handleClose()} disabled={actionLoading || selectedConversation.status === 'closed'}>
                        Close
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex-1 overflow-y-auto rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="space-y-3">
                    {threadLoading ? (
                      <p className="text-sm text-slate-500">Loading thread...</p>
                    ) : messages.length === 0 ? (
                      <p className="text-sm text-slate-500">No messages yet.</p>
                    ) : (
                      messages.map((message) => {
                        const isAdmin = message.sender_role === 'admin';
                        const isSystem = message.sender_role === 'system' || message.sender_role === 'bot';
                        return (
                          <div key={message.message_id} className={`flex ${isAdmin ? 'justify-end' : 'justify-start'}`}>
                            <div
                              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                                isAdmin
                                  ? 'bg-cyan-600 text-white'
                                  : isSystem
                                    ? 'border border-amber-200 bg-amber-50 text-amber-900'
                                    : 'border border-slate-200 bg-white text-slate-900'
                              }`}
                            >
                              <div className="mb-1 flex items-center justify-between gap-4 text-[11px] uppercase tracking-wide opacity-70">
                                <span>{isAdmin ? 'You' : isSystem ? 'System' : 'Customer'}</span>
                                <span>{formatDateTime(message.created_at)}</span>
                              </div>
                              <p className="whitespace-pre-wrap leading-6">{message.body}</p>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                <form onSubmit={handleSend} className="mt-4 space-y-3 border-t border-slate-100 pt-4">
                  <Input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder={selectedConversation.status === 'closed' ? 'Conversation closed' : 'Write your reply as an admin...'}
                    disabled={actionLoading || selectedConversation.status === 'closed'}
                  />
                  <div className="flex gap-2">
                    <Button type="submit" disabled={actionLoading || selectedConversation.status === 'closed' || !input.trim()}>
                      {actionLoading ? 'Sending...' : 'Send reply'}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => void loadThread(selectedConversation.conversation_id)} disabled={actionLoading}>
                      Reload thread
                    </Button>
                  </div>
                </form>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}