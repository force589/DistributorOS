import { Redirect } from 'expo-router';

import { useAuth } from '@/features/auth/AuthContext';

export default function IndexScreen() {
  const { status } = useAuth();
  return <Redirect href={status === 'authenticated' ? '/(app)' : '/(auth)/login'} />;
}

