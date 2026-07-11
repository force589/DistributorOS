import { Text, View } from 'react-native';

import { useTheme } from '@/design/theme';

interface FeedbackBannerProps {
  message: string;
  tone?: 'error' | 'warning' | 'success';
}

export function FeedbackBanner({ message, tone = 'error' }: FeedbackBannerProps) {
  const theme = useTheme();
  const backgroundColor = tone === 'success' ? theme.colors.successBackground : tone === 'warning' ? theme.colors.warningBackground : theme.colors.dangerBackground;
  const color = tone === 'success' ? theme.colors.success : tone === 'warning' ? theme.colors.warning : theme.colors.danger;
  return (
    <View accessibilityLiveRegion="polite" style={{ backgroundColor, borderRadius: theme.radii.md, padding: theme.spacing.md }}>
      <Text style={[theme.typography.label, { color }]}>{message}</Text>
    </View>
  );
}
