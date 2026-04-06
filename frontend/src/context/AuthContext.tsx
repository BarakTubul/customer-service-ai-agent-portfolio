import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import * as t from '@/types';
import { apiClient } from '@/services/apiClient';

interface AuthContextType {
  user: t.User | null;
  isAuthenticated: boolean;
  isGuest: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  guestAccess: (email: string) => Promise<void>;
  logout: () => void;
  sessionId: string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

async function hydrateCurrentUser(): Promise<t.User | null> {
  const session = await apiClient.getSessionState();
  if (!session.authenticated) {
    return null;
  }

  if (session.is_guest) {
    return {
      user_id: String(session.user_id),
      email: `guest-${session.user_id}@guest.local`,
      is_guest: true,
      is_verified: false,
      is_active: session.is_active,
      created_at: new Date().toISOString(),
    };
  }

  try {
    const account = await apiClient.getAccountMe();
    return {
      user_id: String(session.user_id),
      email: account.email_masked || `user-${session.user_id}`,
      is_guest: false,
      is_verified: true,
      is_active: session.is_active,
      created_at: new Date().toISOString(),
    };
  } catch (err) {
    console.warn('[auth] failed to load account profile, using session fallback', err);
    return {
      user_id: String(session.user_id),
      email: `user-${session.user_id}`,
      is_guest: false,
      is_verified: false,
      is_active: session.is_active,
      created_at: new Date().toISOString(),
    };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<t.User | null>(null);
  const [sessionId] = useState<string>(() => {
    const stored = localStorage.getItem('session_id');
    return stored || `session_${Date.now()}`;
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    localStorage.setItem('session_id', sessionId);
  }, [sessionId]);

  useEffect(() => {
    // Restore auth state from server-side auth cookie.
    hydrateCurrentUser()
      .then((restoredUser) => {
        if (restoredUser) {
          console.debug('[auth] restored session', {
            isGuest: restoredUser.is_guest,
          });
        }
        setUser(restoredUser);
      })
      .catch((err) => {
        console.error('[auth] failed to restore session', err);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    try {
      await apiClient.login(email, password);
      const currentUser = await hydrateCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error('[auth] login action failed', { email, error: err });
      throw err;
    }
  };

  const register = async (email: string, password: string) => {
    try {
      await apiClient.register(email, password);
      const currentUser = await hydrateCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error('[auth] register action failed', { email, error: err });
      throw err;
    }
  };

  const guestAccess = async (email: string) => {
    try {
      await apiClient.guestAccess(email);
      const currentUser = await hydrateCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error('[auth] guest access action failed', { email, error: err });
      throw err;
    }
  };

  const logout = () => {
    console.debug('[auth] logout');
    apiClient.logout().catch((err) => {
      console.error('[auth] logout request failed', err);
    });
    setUser(null);
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isGuest: user?.is_guest || false,
    login,
    register,
    guestAccess,
    logout,
    sessionId,
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl text-gray-600">Loading...</div>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
