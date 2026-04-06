import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/UI';

export function Header() {
  const { user, logout, isGuest } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'My Orders', path: '/orders' },
    { label: 'Chat', path: '/chat' },
    { label: 'Order', path: '/order' },
    { label: 'Refunds', path: '/refund' },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-cyan-100 bg-white/80 shadow-sm backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center gap-6">
          <h1
            className="text-2xl font-black tracking-tight cursor-pointer bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 bg-clip-text text-transparent"
            onClick={() => navigate('/order')}
          >
            Support Flow
          </h1>
          {user && (
            <nav className="hidden md:flex gap-2 rounded-full border border-cyan-100 bg-cyan-50/50 p-1">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className={`px-3 py-1.5 rounded-full text-sm font-semibold transition ${
                      isActive
                        ? 'bg-white text-cyan-800 shadow-sm border border-cyan-200'
                        : 'text-gray-600 hover:text-cyan-900 hover:bg-white/70'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </nav>
          )}
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <>
              <div className="text-right px-3 py-1.5 rounded-xl border border-gray-200 bg-white/70">
                <p className="text-sm font-semibold text-gray-900">{user.email}</p>
                <p className="text-xs text-gray-500 font-medium">
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
