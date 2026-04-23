import { useNavigate } from 'react-router-dom';
import { Button, Card } from '@/components/UI';

export function IndexPage() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-900">
      <video
        className="absolute inset-0 h-full w-full object-cover"
        autoPlay
        muted
        loop
        playsInline
        poster="/images/catalog/hero-poster.jpg"
      >
        <source src="/videos/welcome-bg.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950/85 via-slate-900/70 to-cyan-950/70" />

      <div className="relative max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold text-white mb-4">Welcome to the Food Ordering Platform</h1>
        <p className="text-xl text-slate-200 mb-8 max-w-3xl mx-auto">
          Manage orders, refunds, live support, and guided help in one place. 
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
            <div className="text-4xl mb-3">🛒</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Ordering Workflow</h3>
            <p className="text-gray-600">
              Browse catalog, build cart, validate checkout, and place orders with simulation-ready flow tracking.
            </p>
          </Card>
          <Card>
            <div className="text-4xl mb-3">💸</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Refunds & Wallet</h3>
            <p className="text-gray-600">
              Track refund lifecycle, policy decisions, manual review paths, and wallet balance updates in real time.
            </p>
          </Card>
          <Card>
            <div className="text-4xl mb-3">🤝</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Support Suite</h3>
            <p className="text-gray-600">
              Use FAQ/bot guidance when useful, then escalate seamlessly to human support and admin review.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
