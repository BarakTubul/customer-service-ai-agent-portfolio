import { useNavigate } from 'react-router-dom';
import { Button, Card } from '@/components/UI';

export function IndexPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600">
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold text-white mb-4">Welcome to Support AI</h1>
        <p className="text-xl text-blue-100 mb-8">
          AI-powered customer support with intelligent intent routing and refund management
        </p>

        <div className="flex justify-center gap-4 mb-16">
          <Button
            onClick={() => navigate('/login')}
            className="px-8 py-3 text-lg"
          >
            Login
          </Button>
          <Button
            onClick={() => navigate('/register')}
            variant="secondary"
            className="px-8 py-3 text-lg"
          >
            Register
          </Button>
          <Button
            onClick={() => navigate('/guest')}
            variant="outline"
            className="!border-white !bg-transparent !text-white hover:!bg-white/20 px-8 py-3 text-lg"
          >
            Try as Guest
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
          <Card>
            <div className="text-4xl mb-3">🤖</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Smart Intent Detection</h3>
            <p className="text-gray-600">
              LangGraph-powered hybrid routing with rule-based + LLM fallback for accurate intent classification
            </p>
          </Card>
          <Card>
            <div className="text-4xl mb-3">📚</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">RAG FAQ System</h3>
            <p className="text-gray-600">
              Seeded FAQ corpus with lexical scoring and LLM synthesis for cited, grounded responses
            </p>
          </Card>
          <Card>
            <div className="text-4xl mb-3">💰</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Refund Management</h3>
            <p className="text-gray-600">
              Deterministic eligibility checks with idempotency and order state simulation
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
