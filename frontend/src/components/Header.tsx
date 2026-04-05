import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/UI';

export function Header() {
  const { user, logout, isGuest } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        <div className="flex items-center gap-6">
          <h1 className="text-2xl font-bold text-blue-600 cursor-pointer" onClick={() => navigate('/dashboard')}>
            Support AI
          </h1>
          {user && (
            <nav className="hidden md:flex gap-4">
              <button
                onClick={() => navigate('/dashboard')}
                className="text-gray-600 hover:text-gray-900 font-medium"
              >
                Dashboard
              </button>
              <button
                onClick={() => navigate('/chat')}
                className="text-gray-600 hover:text-gray-900 font-medium"
              >
                Chat
              </button>
              <button
                onClick={() => navigate('/refund')}
                className="text-gray-600 hover:text-gray-900 font-medium"
              >
                Refunds
              </button>
            </nav>
          )}
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{user.email}</p>
                <p className="text-xs text-gray-500">
                  {isGuest ? 'Guest' : user.is_verified ? 'Verified' : 'Pending'}
                </p>
              </div>
              <Button onClick={() => { logout(); navigate('/'); }} variant="outline" size="sm">
                Logout
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
