import { FormEvent, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Button, Card, Input } from '@/components/UI';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import * as t from '@/types';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: t.FAQCitation[];
}

function MarkdownContent({ content, isUser }: { content: string; isUser: boolean }) {
  const textClass = isUser ? 'text-white' : 'text-gray-800';
  const softTextClass = isUser ? 'text-blue-100' : 'text-gray-500';
  const codeBgClass = isUser ? 'bg-blue-500/60' : 'bg-gray-100';

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className={`leading-relaxed ${textClass}`}>{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className={`list-disc pl-5 space-y-1 ${textClass}`}>{children}</ul>,
        ol: ({ children }) => <ol className={`list-decimal pl-5 space-y-1 ${textClass}`}>{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className={`underline underline-offset-2 ${isUser ? 'text-white' : 'text-blue-700'}`}
          >
            {children}
          </a>
        ),
        code: ({ className, children }) => {
          const rawText = String(children);
          const isBlock = Boolean(className) || rawText.includes('\n');
          return isBlock ? (
            <pre className={`mt-2 mb-1 p-2 rounded overflow-x-auto ${codeBgClass}`}>
              <code className={`text-[11px] leading-relaxed ${className || ''}`}>{children}</code>
            </pre>
          ) : (
            <code className={`px-1 py-0.5 rounded text-[11px] ${codeBgClass}`}>{children}</code>
          );
        },
        hr: () => <hr className={`my-2 border ${isUser ? 'border-blue-300' : 'border-gray-200'}`} />,
        blockquote: ({ children }) => (
          <blockquote className={`pl-3 border-l-2 ${isUser ? 'border-blue-300' : 'border-gray-300'} ${softTextClass}`}>
            {children}
          </blockquote>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function normalizeMessage(value: string): string {
  return value.trim().toLowerCase();
}

function isGreetingMessage(value: string): boolean {
  const normalized = normalizeMessage(value);
  if (!normalized) {
    return false;
  }

  const cleaned = normalized.replace(/[^a-z\s]/g, ' ').replace(/\s+/g, ' ').trim();
  return [
    'hi',
    'hello',
    'hey',
    'good morning',
    'good afternoon',
    'good evening',
    'shalom',
  ].includes(cleaned);
}

function inferIntentLocally(value: string): string | null {
  const normalized = normalizeMessage(value);

  if (
    /request\s+a\s+refund|ask\s+for\s+refund|get\s+a\s+refund|refund\s+request|where\s+can\s+i\s+ask\s+for\s+refund|where\s+can\s+i\s+request\s+a\s+refund/.test(
      normalized
    )
  ) {
    return 'refund_request';
  }
  if (/refund|money\s*back|reimburse/.test(normalized)) {
    return 'refund_policy';
  }
  if (
    /order\s+food|place\s+an\s+order|place\s+order|how\s+do\s+i\s+order|where\s+can\s+i\s+order|where\s+can\s+i\s+order\s+food/.test(
      normalized
    )
  ) {
    return 'order_placement';
  }
  if (/order|delivery|tracking|where\s+is\s+my\s+order/.test(normalized)) {
    return 'order_status';
  }
  if (/verify|verification|verified|account\s+verification/.test(normalized)) {
    return 'account_verification';
  }
  return null;
}

export function FloatingChatWidget() {
  const location = useLocation();
  const { sessionId } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingDots, setLoadingDots] = useState(1);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!loading) {
      setLoadingDots(1);
      return;
    }

    const intervalId = window.setInterval(() => {
      setLoadingDots((prev) => (prev % 3) + 1);
    }, 320);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [loading]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    container.scrollTop = container.scrollHeight;
  }, [messages, loading, isOpen]);

  if (location.pathname === '/chat') {
    return null;
  }

  const isBusy = loading || isStreaming;

  const streamAssistantMessage = async (text: string, citations: t.FAQCitation[] = []) => {
    let assistantMessageIndex = -1;
    setMessages((prev) => {
      assistantMessageIndex = prev.length;
      return [...prev, { role: 'assistant', content: '', citations: [] }];
    });

    setIsStreaming(true);
    const chunkSize = text.length > 260 ? 6 : text.length > 120 ? 4 : 2;

    for (let i = chunkSize; i < text.length; i += chunkSize) {
      const partial = text.slice(0, i);
      setMessages((prev) =>
        prev.map((msg, idx) =>
          idx === assistantMessageIndex
            ? {
                ...msg,
                content: partial,
              }
            : msg
        )
      );
      await sleep(18);
    }

    setMessages((prev) =>
      prev.map((msg, idx) =>
        idx === assistantMessageIndex
          ? {
              ...msg,
              content: text,
              citations,
            }
          : msg
      )
    );
    setIsStreaming(false);
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim()) {
      return;
    }

    const userMessage = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setError('');

    if (isGreetingMessage(userMessage)) {
      await streamAssistantMessage(
        'Hi! I can help with refunds, order status, and account verification. What do you need help with?'
      );
      return;
    }

    setLoading(true);

    try {
      let assistantContent = '';
      let citations: t.FAQCitation[] = [];
      const localIntent = inferIntentLocally(userMessage);

      if (localIntent) {
        const faq = await apiClient.searchFAQ(userMessage, sessionId, localIntent);
        assistantContent = faq.answer.text;
        citations = faq.citations || [];
      } else {
        const intent = await apiClient.resolveIntent(
          userMessage,
          sessionId,
          `msg-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
        );

        if (intent.route === 'clarify') {
          assistantContent =
            intent.clarification_question ||
            "I'm not sure I understand your question. Could you provide more details?";
        } else {
          const faq = await apiClient.searchFAQ(userMessage, sessionId, intent.intent);
          assistantContent = faq.answer.text;
          citations = faq.citations || [];
        }
      }

      await streamAssistantMessage(assistantContent, citations);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      await streamAssistantMessage('Sorry, something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-40">
      {isOpen ? (
        <Card className="w-[360px] max-w-[calc(100vw-2rem)] shadow-2xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-gray-900">Support Assistant</h3>
            <button
              type="button"
              className="text-gray-500 hover:text-gray-800 text-sm"
              onClick={() => setIsOpen(false)}
            >
              Close
            </button>
          </div>

          <div
            ref={scrollContainerRef}
            className="h-72 overflow-y-auto border border-gray-100 rounded-md p-2 bg-gray-50 space-y-2 mb-3"
          >
            {messages.length === 0 ? (
              <p className="text-xs text-gray-500">Ask about refunds, orders, or account support.</p>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`text-xs p-2 rounded-md ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white ml-8'
                      : 'bg-white text-gray-800 border border-gray-200 mr-8'
                  }`}
                >
                  <MarkdownContent content={msg.content} isUser={msg.role === 'user'} />
                  {msg.citations && msg.citations.length > 0 && (
                    <p className="mt-1 opacity-75">Source: {msg.citations[0].source_id}</p>
                  )}
                </div>
              ))
            )}

            {loading && (
              <div className="text-xs p-2 rounded-md bg-white text-gray-700 border border-gray-200 mr-8 inline-flex items-center gap-2">
                <span>Thinking</span>
                <span className="inline-flex items-center gap-1">
                  <span
                    className={`h-1.5 w-1.5 rounded-full bg-gray-400 transition-opacity ${
                      loadingDots >= 1 ? 'opacity-100' : 'opacity-30'
                    }`}
                  />
                  <span
                    className={`h-1.5 w-1.5 rounded-full bg-gray-400 transition-opacity ${
                      loadingDots >= 2 ? 'opacity-100' : 'opacity-30'
                    }`}
                  />
                  <span
                    className={`h-1.5 w-1.5 rounded-full bg-gray-400 transition-opacity ${
                      loadingDots >= 3 ? 'opacity-100' : 'opacity-30'
                    }`}
                  />
                </span>
              </div>
            )}
          </div>

          {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

          <form onSubmit={sendMessage} className="flex gap-2">
            <Input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask a question..."
              disabled={isBusy}
              className="text-sm"
            />
            <Button type="submit" size="sm" disabled={isBusy || !input.trim()}>
              {isBusy ? '...' : 'Send'}
            </Button>
          </form>
        </Card>
      ) : (
        <Button onClick={() => setIsOpen(true)} className="rounded-full shadow-lg px-5 py-3">
          Chat
        </Button>
      )}
    </div>
  );
}
