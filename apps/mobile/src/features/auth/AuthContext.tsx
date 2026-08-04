import {
  ApiError,
  type BusinessSettings,
  type BusinessSettingsUpdateRequest,
  type ChangePasswordRequest,
  type ForgotPasswordRequest,
  type AuthResponse,
  type LoginRequest,
  type MessageResponse,
  type ResetPasswordRequest,
  type SignupRequest,
  type User,
} from '@distributoros/api-client';
import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Platform } from 'react-native';

import { apiClient } from '@/api/client';
import {
  getActiveQueryBusiness,
  setActiveQueryBusiness,
} from '@/api/queryScope';

import { authStorage } from './authStorage';
import { restoreSession } from './sessionBootstrap';
import {
  publishWebLogout,
  publishWebSession,
  subscribeToWebSession,
} from './webSessionCoordinator';

export type AuthStatus = 'checking' | 'authenticated' | 'anonymous' | 'error';

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (request: LoginRequest) => Promise<void>;
  signup: (request: SignupRequest) => Promise<void>;
  forgotPassword: (request: ForgotPasswordRequest) => Promise<MessageResponse>;
  resetPassword: (request: ResetPasswordRequest) => Promise<MessageResponse>;
  changePassword: (request: ChangePasswordRequest) => Promise<MessageResponse>;
  logout: () => Promise<void>;
  updateBusinessSettings: (
    request: BusinessSettingsUpdateRequest,
  ) => Promise<BusinessSettings>;
  retrySessionCheck: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
let bootstrapPromise: Promise<AuthResponse | null> | null = null;

function beginSessionRestore(): Promise<AuthResponse | null> {
  bootstrapPromise ??= restoreSession({
    api: apiClient,
    storage: authStorage,
    platform: Platform.OS,
  });
  return bootstrapPromise;
}

export function canAccessProtectedRoutes(status: AuthStatus): boolean {
  return status === 'authenticated';
}

export function isSessionRestorePending(status: AuthStatus): boolean {
  return status === 'checking';
}

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [user, setUser] = useState<User | null>(null);
  const [restoreAttempt, setRestoreAttempt] = useState(0);

  const acceptSession = useCallback(async (session: AuthResponse): Promise<void> => {
    const businessId = session.user.business.id;
    if (getActiveQueryBusiness() !== businessId) {
      queryClient.clear();
      setActiveQueryBusiness(businessId);
    }
    apiClient.setAccessToken(session.access_token);
    if (session.refresh_token) {
      await authStorage.setRefreshToken(session.refresh_token);
    }
    setUser(session.user);
    setStatus('authenticated');
  }, [queryClient]);

  const clearSession = useCallback(async (): Promise<void> => {
    apiClient.setAccessToken(null);
    await authStorage.clearRefreshToken();
    queryClient.clear();
    setActiveQueryBusiness(null);
    setUser(null);
    setStatus('anonymous');
  }, [queryClient]);

  useEffect(() => {
    let active = true;
    apiClient.setUnauthorizedHandler(async () => {
      const session = await restoreSession({
        api: apiClient,
        storage: authStorage,
        platform: Platform.OS,
      });
      if (!session) {
        if (active) {
          await clearSession();
        }
        return null;
      }
      if (active) {
        await acceptSession(session);
      }
      return session.access_token;
    });

    void beginSessionRestore()
      .then(async (session) => {
        if (!active) {
          return;
        }
        if (session) {
          await acceptSession(session);
        } else {
          setStatus('anonymous');
        }
      })
      .catch(() => {
        if (active) {
          setStatus('error');
        }
      });

    return () => {
      active = false;
      apiClient.setUnauthorizedHandler(null);
    };
  }, [acceptSession, clearSession, restoreAttempt]);

  useEffect(() => subscribeToWebSession((message) => {
    if (message.type === 'session') void acceptSession(message.session);
    else void clearSession();
  }), [acceptSession, clearSession]);

  const login = useCallback(
    async (request: LoginRequest): Promise<void> => {
      const session = await apiClient.login(request);
      await acceptSession(session);
      if (Platform.OS === 'web') publishWebSession(session);
    },
    [acceptSession],
  );

  const signup = useCallback(
    async (request: SignupRequest): Promise<void> => {
      const session = await apiClient.signup(request);
      await acceptSession(session);
      if (Platform.OS === 'web') publishWebSession(session);
    },
    [acceptSession],
  );

  const forgotPassword = useCallback(
    (request: ForgotPasswordRequest) => apiClient.forgotPassword(request),
    [],
  );

  const resetPassword = useCallback(
    (request: ResetPasswordRequest) => apiClient.resetPassword(request),
    [],
  );

  const changePassword = useCallback(async (request: ChangePasswordRequest) => {
    const result = await apiClient.changePassword(request);
    await clearSession();
    if (Platform.OS === 'web') publishWebLogout();
    return result;
  }, [clearSession]);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiClient.logout();
      await clearSession();
      if (Platform.OS === 'web') publishWebLogout();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearSession();
        if (Platform.OS === 'web') publishWebLogout();
        return;
      }
      throw error;
    }
  }, [clearSession]);

  const updateBusinessSettings = useCallback(
    async (request: BusinessSettingsUpdateRequest): Promise<BusinessSettings> => {
      const settings = await apiClient.updateBusinessSettings(request);
      setUser((current) =>
        current
          ? {
              ...current,
              business: { ...current.business, ...settings },
            }
          : current,
      );
      return settings;
    },
    [],
  );

  const retrySessionCheck = useCallback(() => {
    bootstrapPromise = null;
    setStatus('checking');
    setRestoreAttempt((attempt) => attempt + 1);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login,
      signup,
      forgotPassword,
      resetPassword,
      changePassword,
      logout,
      updateBusinessSettings,
      retrySessionCheck,
    }),
    [
      status,
      user,
      login,
      signup,
      forgotPassword,
      resetPassword,
      changePassword,
      logout,
      updateBusinessSettings,
      retrySessionCheck,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.');
  }
  return context;
}
