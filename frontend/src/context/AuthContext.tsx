import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import type { UserProfileResponse, TokenResponse } from '../client/types.gen';
import { getMeAuthMeGet, logoutAuthLogoutPost } from '../client/sdk.gen';
import { client } from '../client/client.gen';

interface AuthContextValue {
  user: UserProfileResponse | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  role: string | null;
  login: (tokens: TokenResponse) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(
    () => localStorage.getItem(ACCESS_TOKEN_KEY)
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(
    () => localStorage.getItem(REFRESH_TOKEN_KEY)
  );
  const [isLoading, setIsLoading] = useState(true);

  // Sync token into the hey-api client on every change
  useEffect(() => {
    if (accessToken) {
      client.setConfig({ auth: accessToken });
      localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    } else {
      client.setConfig({ auth: undefined });
      localStorage.removeItem(ACCESS_TOKEN_KEY);
    }
  }, [accessToken]);

  useEffect(() => {
    if (refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  }, [refreshToken]);

  // On mount, rehydrate user from stored token
  useEffect(() => {
    const hydrate = async () => {
      if (!accessToken) {
        setIsLoading(false);
        return;
      }
      try {
        const result = await getMeAuthMeGet();
        if (result.data) setUser(result.data);
        else clearAuth();
      } catch {
        clearAuth();
      } finally {
        setIsLoading(false);
      }
    };
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearAuth = () => {
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);
  };

  const login = useCallback(async (tokens: TokenResponse) => {
    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);
    // Immediately apply the token so the /me call succeeds
    client.setConfig({ auth: tokens.access_token });
    const result = await getMeAuthMeGet();
    if (result.data) setUser(result.data);
  }, []);

  const logout = useCallback(async () => {
    if (refreshToken) {
      try {
        await logoutAuthLogoutPost({ body: { refresh_token: refreshToken } });
      } catch { /* best-effort */ }
    }
    clearAuth();
  }, [refreshToken]);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        refreshToken,
        isLoading,
        isAuthenticated: !!user,
        role: user?.role ?? null,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}