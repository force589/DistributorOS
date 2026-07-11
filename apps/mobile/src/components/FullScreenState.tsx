import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '@/design/theme';
import { ErrorState, LoadingState } from '@/design-system';

interface FullScreenStateProps {
  title: string;
  message: string;
  loading?: boolean;
  actionLabel?: string;
  onAction?: () => void;
}

export function FullScreenState({ title, message, loading = false, actionLabel, onAction }: FullScreenStateProps) {
  const theme = useTheme();
  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1, justifyContent: 'center' }}>
      {loading ? <LoadingState message={message} title={title} /> : <ErrorState message={message} onRetry={onAction} retryLabel={actionLabel} title={title} />}
    </SafeAreaView>
  );
}
