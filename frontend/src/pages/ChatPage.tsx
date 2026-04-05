import { useState, type FormEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/services/apiClient';
import { Button, Input, Card, Alert } from '@/components/UI';
import * as t from '@/types';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: t.FAQCitation[];
}

export function ChatPage() {
  const { sessionId } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.resolveIntent(userMessage, sessionId);

      let assistantContent = '';
      let citations: t.FAQCitation[] = [];

      if (response.route === 'clarify') {
        assistantContent =
          "I'm not sure I understand your question. Could you provide more details about your issue?";
      } else if (response.route === 'escalate') {
        assistantContent =
          'This issue requires special attention. A support agent will be with you shortly.';
      } else if (response.answer) {
        assistantContent = response.answer.text;
        citations = response.citations || [];
      } else {
        assistantContent = `I detected a question about: ${response.intent} (confidence: ${(response.confidence * 100).toFixed(0)}%)`;
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: assistantContent,
          citations,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 h-screen flex flex-col">
      <Card className="flex-1 overflow-y-auto mb-4">
        <div className="space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              <p className="text-lg">Start a conversation</p>
              <p className="text-sm">Ask about orders, refunds, account issues, or anything else</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md p-4 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-900 border border-gray-200'
                  }`}
                >
                  <p className="text-sm">{msg.content}</p>
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-300 space-y-2">
                      <p className="text-xs font-semibold opacity-75">Sources:</p>
                      {msg.citations.map((cite, cidx) => (
                        <div key={cidx} className="text-xs opacity-75">
                          <p className="font-semibold">{cite.source_id}</p>
                          <p className="italic">"{cite.snippet}"</p>
                          <p className="text-xs">Score: {(cite.score * 100).toFixed(0)}%</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <form onSubmit={handleSendMessage} className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about orders, refunds, or anything..."
          disabled={loading}
          className="flex-1"
        />
        <Button type="submit" disabled={loading || !input.trim()}>
          {loading ? '...' : 'Send'}
        </Button>
      </form>
    </div>
  );
}
