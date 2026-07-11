import '@/localization/i18n';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FullScreenState } from '@/components/FullScreenState';
import { businessQueryHash } from '@/api/queryScope';
import { AppPreferencesProvider, useTheme } from '@/design/theme';
import {
  AuthProvider,
  canAccessProtectedRoutes,
  useAuth,
} from '@/features/auth/AuthContext';

function RootNavigator() {
  const { t } = useTranslation();
  const { status, retrySessionCheck } = useAuth();
  const theme = useTheme();

  if (status === 'checking') {
    return (
      <FullScreenState
        loading
        message={t('startup.loadingMessage')}
        title={t('startup.loadingTitle')}
      />
    );
  }
  if (status === 'error') {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('startup.errorMessage')}
        onAction={retrySessionCheck}
        title={t('startup.errorTitle')}
      />
    );
  }

  const authenticated = canAccessProtectedRoutes(status);
  return (
    <Stack
      screenOptions={{
        contentStyle: { backgroundColor: theme.colors.background },
        headerShown: false,
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Protected guard={!authenticated}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={authenticated}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
    </Stack>
  );
}

function AppContent() {
  const theme = useTheme();
  return (
    <>
      <StatusBar style={theme.mode === 'dark' ? 'light' : 'dark'} />
      <RootNavigator />
    </>
  );
}

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            queryKeyHashFn: businessQueryHash,
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: { retry: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppPreferencesProvider>
          <AppContent />
        </AppPreferencesProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
