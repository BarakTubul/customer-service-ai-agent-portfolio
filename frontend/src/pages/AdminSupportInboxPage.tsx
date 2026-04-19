import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { Alert, Button, Card, Input } from '@/components/UI';
import { apiClient } from '@/services/apiClient';
import * as t from '@/types';

type ThreadMessage = {
  message_id: string;
  sender_role: string;
  body: string;
  created_at: string;
};

type ConversationPriorityFilter = 'all' | 'normal' | 'high';

const THREAD_PAGE_SIZE = 30;

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function toIsoDateTime(dateValue: string, endOfDay = false): string | undefined {
  if (!dateValue) {
    return undefined;
  }
  const suffix = endOfDay ? 'T23:59:59.999' : 'T00:00:00.000';
  const date = new Date(`${dateValue}${suffix}`);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}

function badgeClasses(priority: string, unreadCount: number) {
  const base = 'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold';

  const priorityClass = priority === 'high'
    ? 'bg-rose-100 text-rose-700'
    : 'bg-slate-100 text-slate-600';

  const unreadClass = unreadCount > 0
    ? 'bg-rose-600 text-white'
    : 'bg-emerald-100 text-emerald-700';

  return { base, priorityClass, unreadClass };
}

export function AdminSupportInboxPage() {
  const [conversations, setConversations] = useState<t.SupportConversationResponse[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<t.SupportConversationResponse | null>(null);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [loadingList, setLoadingList] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadLoadingOlder, setThreadLoadingOlder] = useState(false);
  const [threadHasMore, setThreadHasMore] = useState(true);
  const [threadChunkLoadedNotice, setThreadChunkLoadedNotice] = useState(false);
  const [draftPriority, setDraftPriority] = useState<'normal' | 'high'>('normal');
  const [priorityFilter, setPriorityFilter] = useState<ConversationPriorityFilter>('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [createdAfter, setCreatedAfter] = useState('');
  const [createdBefore, setCreatedBefore] = useState('');
  const [updatedAfter, setUpdatedAfter] = useState('');
  const [updatedBefore, setUpdatedBefore] = useState('');
  const [threadAtBottom, setThreadAtBottom] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);
  const messageIdsRef = useRef(new Set<string>());
  const threadContainerRef = useRef<HTMLDivElement | null>(null);
  const threadChunkLoadedTimerRef = useRef<number | null>(null);

  const selectedConversationState = useMemo(() => selectedConversation, [selectedConversation]);
  const selectedConversationListItem = useMemo(
    () => conversations.find((item) => item.conversation_id === selectedConversationId),
    [conversations, selectedConversationId]
  );

  const upsertConversationInList = (conversation: t.SupportConversationResponse) => {
    setConversations((current) => {
      const existing = current.find((item) => item.conversation_id === conversation.conversation_id);
      const mergedConversation: t.SupportConversationResponse = {
        ...conversation,
        customer_email: conversation.customer_email || existing?.customer_email || null,
      };
      const next = current.filter((item) => item.conversation_id !== conversation.conversation_id);
      if (unreadOnly && (mergedConversation.unread_message_count || 0) === 0) {
        return next;
      }
      next.push(mergedConversation);
      next.sort((left, right) => {
        const rightUpdatedAt = new Date(right.updated_at).getTime();
        const leftUpdatedAt = new Date(left.updated_at).getTime();
        if (rightUpdatedAt !== leftUpdatedAt) {
          return rightUpdatedAt - leftUpdatedAt;
        }

        const rightCreatedAt = new Date(right.created_at).getTime();
        const leftCreatedAt = new Date(left.created_at).getTime();
        return rightCreatedAt - leftCreatedAt;
      });
      return next;
    });
  };

  const markSelectedConversationRead = async () => {
    if (!selectedConversationId) {
      return;
    }
    if ((selectedConversationListItem?.unread_message_count || 0) <= 0) {
      return;
    }

    try {
      const updated = await apiClient.markSupportConversationRead(selectedConversationId);
      setSelectedConversation((current) => ({
        ...current,
        ...updated,
        customer_email: current?.customer_email ?? updated.customer_email ?? null,
      }));
      upsertConversationInList(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark support conversation as read');
    }
  };

  const loadConversations = async () => {
    setLoadingList(true);
    setError('');
    try {
      const response = await apiClient.listAdminSupportConversations({
        limit: 100,
        priority: priorityFilter,
        unreadOnly,
        createdAfter: toIsoDateTime(createdAfter, false),
        createdBefore: toIsoDateTime(createdBefore, true),
        updatedAfter: toIsoDateTime(updatedAfter, false),
        updatedBefore: toIsoDateTime(updatedBefore, true),
      });
      setConversations(response.items);

      if (!selectedConversationId && response.items.length > 0) {
        setSelectedConversationId(response.items[0].conversation_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support conversations');
    } finally {
      setLoadingList(false);
    }
  };

  const loadThread = async (conversationId: string) => {
    setThreadLoading(true);
    setError('');
    try {
      const [conversationResponse, messageResponse] = await Promise.all([
        apiClient.getSupportConversation(conversationId),
        apiClient.listSupportMessages(conversationId, THREAD_PAGE_SIZE),
      ]);

      setSelectedConversation(conversationResponse);
      setDraftPriority(conversationResponse.priority === 'high' ? 'high' : 'normal');
      setMessages(
        messageResponse.items.map((item) => ({
          message_id: item.message_id,
          sender_role: item.sender_role,
          body: item.body,
          created_at: item.created_at,
        }))
      );
      messageIdsRef.current = new Set(messageResponse.items.map((item) => item.message_id));
      setThreadHasMore(messageResponse.items.length >= THREAD_PAGE_SIZE);
      setSelectedConversationId(conversationId);
      setThreadAtBottom(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support conversation');
    } finally {
      setThreadLoading(false);
    }
  };

  useEffect(() => {
    void loadConversations();
    return () => {
      if (threadChunkLoadedTimerRef.current !== null) {
        window.clearTimeout(threadChunkLoadedTimerRef.current);
      }
    };
  }, [priorityFilter, unreadOnly, createdAfter, createdBefore, updatedAfter, updatedBefore]);

  useEffect(() => {
    if (!selectedConversationId) {
      return;
    }

    socketRef.current?.close();
    messageIdsRef.current.clear();
    setThreadLoading(true);

    const token = apiClient.getAccessToken();
    const wsBase = 'ws://localhost:8000/api/v1/ws/support';
    const wsUrl = token
      ? `${wsBase}/${selectedConversationId}?token=${encodeURIComponent(token)}`
      : `${wsBase}/${selectedConversationId}`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as { type: string; payload?: unknown };

        if (data.type === 'conversation.snapshot') {
          const payload = data.payload as {
            conversation: t.SupportConversationResponse;
            messages: ThreadMessage[];
          };
          setSelectedConversation((current) => ({
            ...payload.conversation,
            customer_email: payload.conversation.customer_email || current?.customer_email || null,
          }));
          setMessages(payload.messages || []);
          messageIdsRef.current = new Set((payload.messages || []).map((item) => item.message_id));
          setThreadHasMore((payload.messages || []).length >= THREAD_PAGE_SIZE);
          setThreadLoading(false);
          return;
        }

        if (data.type === 'conversation.updated') {
          const payload = data.payload as t.SupportConversationResponse;
          setSelectedConversation((current) => ({
            ...current,
            ...payload,
            customer_email: current?.customer_email ?? payload.customer_email ?? null,
          }));
          setDraftPriority(payload.priority === 'high' ? 'high' : 'normal');
          upsertConversationInList(payload);
          return;
        }

        if (data.type === 'message.new') {
          const payload = data.payload as ThreadMessage;
          if (!messageIdsRef.current.has(payload.message_id)) {
            messageIdsRef.current.add(payload.message_id);
            setMessages((current) => [...current, payload]);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to parse support websocket event');
      }
    };

    socket.onerror = () => {
      setError('Support websocket connection failed. Using manual reload fallback.');
      setThreadLoading(false);
    };

    socket.onclose = () => {
      setThreadLoading(false);
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [selectedConversationId]);

  useEffect(() => {
    if (!selectedConversationId || threadLoading) {
      return;
    }
    if (!threadAtBottom) {
      return;
    }

    void markSelectedConversationRead();
  }, [selectedConversationId, messages, threadAtBottom, threadLoading]);

  const loadOlderThreadMessages = async () => {
    if (!selectedConversation || threadLoadingOlder || !threadHasMore) {
      return;
    }

    const oldestMessageId = messages[0]?.message_id;
    if (!oldestMessageId) {
      setThreadHasMore(false);
      return;
    }

    const container = threadContainerRef.current;
    const previousHeight = container?.scrollHeight || 0;

    setThreadLoadingOlder(true);
    setError('');
    try {
      const response = await apiClient.listSupportMessages(
        selectedConversation.conversation_id,
        THREAD_PAGE_SIZE,
        oldestMessageId
      );
      const olderMessages = response.items.map((item) => ({
        message_id: item.message_id,
        sender_role: item.sender_role,
        body: item.body,
        created_at: item.created_at,
      }));

      if (olderMessages.length === 0) {
        setThreadHasMore(false);
        return;
      }

      setMessages((current) => {
        const deduped = olderMessages.filter((item) => !messageIdsRef.current.has(item.message_id));
        deduped.forEach((item) => messageIdsRef.current.add(item.message_id));
        return [...deduped, ...current];
      });

      setThreadChunkLoadedNotice(true);
      if (threadChunkLoadedTimerRef.current !== null) {
        window.clearTimeout(threadChunkLoadedTimerRef.current);
      }
      threadChunkLoadedTimerRef.current = window.setTimeout(() => {
        setThreadChunkLoadedNotice(false);
      }, 1400);

      if (olderMessages.length < THREAD_PAGE_SIZE) {
        setThreadHasMore(false);
      }

      window.requestAnimationFrame(() => {
        const nextContainer = threadContainerRef.current;
        if (!nextContainer) {
          return;
        }
        const nextHeight = nextContainer.scrollHeight;
        nextContainer.scrollTop = nextHeight - previousHeight;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load older thread messages');
    } finally {
      setThreadLoadingOlder(false);
    }
  };

  const handleThreadScroll = () => {
    const container = threadContainerRef.current;
    if (!container || threadLoadingOlder || !threadHasMore) {
      if (container) {
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        setThreadAtBottom(distanceFromBottom <= 80);
      }
      return;
    }
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    setThreadAtBottom(distanceFromBottom <= 80);
    if (container.scrollTop <= 24) {
      void loadOlderThreadMessages();
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    setSelectedConversationId(conversationId);
  };

  const handlePrioritySave = async () => {
    if (!selectedConversation) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const updated = await apiClient.updateSupportConversationPriority(
        selectedConversation.conversation_id,
        draftPriority
      );
      setSelectedConversation((current) => ({
        ...current,
        ...updated,
        customer_email: current?.customer_email ?? updated.customer_email ?? null,
      }));
      setDraftPriority(updated.priority === 'high' ? 'high' : 'normal');
      upsertConversationInList(updated);
      setSuccess(`Marked the conversation as ${updated.priority}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update urgency');
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reply');
    } finally {
      setActionLoading(false);
    }
  };

  const selectedUnreadCount = selectedConversationState?.unread_message_count || 0;
  const selectedLastMessage = selectedConversationState?.last_message_preview || 'No preview available';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-white px-4 py-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-3 rounded-3xl border border-cyan-100 bg-white/90 p-6 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-700">Admin support inbox</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Live customer conversations</h1>
            <p className="mt-2 text-sm text-slate-600">All conversations in one list with unread markers, urgency, and time filters.</p>
          </div>
          <Button onClick={() => void loadConversations()} disabled={loadingList || actionLoading} variant="outline">
            {loadingList ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <Card className="border border-slate-200 bg-white shadow-xl">
          <div className="grid gap-4 lg:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Urgency</label>
              <select
                value={priorityFilter}
                onChange={(event) => setPriorityFilter(event.target.value as ConversationPriorityFilter)}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <option value="all">All</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </select>
            </div>

            <div className="flex items-end">
              <Button
                type="button"
                variant={unreadOnly ? 'secondary' : 'outline'}
                onClick={() => setUnreadOnly((current) => !current)}
                className="w-full justify-center"
              >
                Unread only
              </Button>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Created from</label>
              <Input type="date" value={createdAfter} onChange={(event) => setCreatedAfter(event.target.value)} />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Created to</label>
              <Input type="date" value={createdBefore} onChange={(event) => setCreatedBefore(event.target.value)} />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Updated from</label>
              <Input type="date" value={updatedAfter} onChange={(event) => setUpdatedAfter(event.target.value)} />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Updated to</label>
              <Input type="date" value={updatedBefore} onChange={(event) => setUpdatedBefore(event.target.value)} />
            </div>

            <div className="flex items-end gap-2 lg:justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setPriorityFilter('all');
                  setUnreadOnly(false);
                  setCreatedAfter('');
                  setCreatedBefore('');
                  setUpdatedAfter('');
                  setUpdatedBefore('');
                }}
              >
                Clear filters
              </Button>
            </div>
          </div>
        </Card>

        <div className="grid gap-6 lg:grid-cols-[1.05fr_1.15fr] lg:items-stretch">
          <Card className="h-[40rem] border border-slate-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Conversations ({conversations.length})</h2>
                <p className="text-sm text-slate-500">Newest activity first.</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {conversations.length === 0 ? (
                <p className="text-sm text-slate-500">No conversations match the current filters.</p>
              ) : (
                conversations.map((conversation) => {
                  const isSelected = selectedConversationId === conversation.conversation_id;
                  const unreadCount = conversation.unread_message_count || 0;
                  const unreadBadge = badgeClasses(conversation.priority, unreadCount);
                  return (
                    <button
                      key={conversation.conversation_id}
                      type="button"
                      onClick={() => handleSelectConversation(conversation.conversation_id)}
                      className={`w-full rounded-2xl border p-4 text-left transition ${
                        isSelected ? 'border-cyan-300 bg-cyan-50' : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-slate-900">
                              {conversation.customer_email || `Customer ${conversation.customer_user_id}`}
                            </p>
                            {unreadCount > 0 ? (
                              <span className={`${unreadBadge.base} ${unreadBadge.unreadClass}`}>
                                {unreadCount} new
                              </span>
                            ) : (
                              <span className={`${unreadBadge.base} ${unreadBadge.priorityClass}`}>
                                caught up
                              </span>
                            )}
                            <span className={`${unreadBadge.base} ${unreadBadge.priorityClass}`}>
                              {conversation.priority}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-600">{conversation.customer_email || 'Unknown customer'}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            Last activity: {conversation.last_message_at ? formatDateTime(conversation.last_message_at) : 'No messages yet'}
                          </p>
                          <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                            {conversation.last_message_preview || 'No preview available'}
                          </p>
                        </div>
                        <div className="text-right text-xs text-slate-500">
                          <p>Updated {formatDateTime(conversation.updated_at)}</p>
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </Card>

          <Card className="h-[40rem] border border-slate-200 bg-white shadow-xl">
            {!selectedConversation ? (
              <div className="flex h-full min-h-[28rem] items-center justify-center text-center text-slate-500">
                <div>
                  <p className="text-lg font-semibold text-slate-900">No conversation selected</p>
                  <p className="mt-2 text-sm">Choose any conversation from the list to open the thread.</p>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-0 flex-col">
                <div className="border-b border-slate-100 pb-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">Conversation</p>
                      <h2 className="mt-1 text-xl font-bold text-slate-900">
                        {selectedConversation.customer_email || `Customer ${selectedConversation.customer_user_id}`}
                      </h2>
                      <p className="text-sm text-slate-500">
                        {selectedConversation.customer_email || 'No customer email available'} • {selectedConversation.priority} • {selectedUnreadCount} unread
                      </p>
                    </div>
                    <div className="space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-3">
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Urgency</label>
                      <div className="flex flex-wrap gap-2">
                        <select
                          value={draftPriority}
                          onChange={(event) => setDraftPriority(event.target.value === 'high' ? 'high' : 'normal')}
                          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                          disabled={actionLoading}
                        >
                          <option value="normal">Normal</option>
                          <option value="high">High</option>
                        </select>
                        <Button size="sm" onClick={() => void handlePrioritySave()} disabled={actionLoading || draftPriority === selectedConversation.priority}>
                          Save urgency
                        </Button>
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Last message: {selectedLastMessage}</p>
                </div>

                <div
                  ref={threadContainerRef}
                  onScroll={handleThreadScroll}
                  className="mt-4 flex-1 min-h-0 overflow-y-auto rounded-2xl border border-slate-100 bg-slate-50 p-4"
                >
                  <div className="space-y-3">
                    {threadLoadingOlder && (
                      <div className="flex w-full items-center justify-center gap-2 py-1 text-xs text-slate-500">
                        <span>Loading older messages</span>
                        <span className="inline-flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse" />
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:120ms]" />
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:240ms]" />
                        </span>
                      </div>
                    )}
                    {threadChunkLoadedNotice && !threadLoadingOlder && (
                      <p className="text-center text-xs text-emerald-600">Older messages loaded</p>
                    )}
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
