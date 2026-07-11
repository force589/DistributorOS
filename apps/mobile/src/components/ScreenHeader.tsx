import { Pressable, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { useUnsavedChanges } from '@/navigation/UnsavedChangesContext';

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  backLabel?: string;
  onBack?: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

export function ScreenHeader({ title, subtitle, backLabel, onBack, actionLabel, onAction }: ScreenHeaderProps) {
  const theme = useTheme();
  const { guardNavigation } = useUnsavedChanges();
  const link = (label: string, onPress: () => void) => (
    <Pressable accessibilityRole="button" hitSlop={6} onPress={() => guardNavigation(onPress)} style={{ justifyContent: 'center', minHeight: 44, paddingHorizontal: theme.spacing.sm }}>
      <Text style={[theme.typography.label, { color: theme.colors.primary }]}>{label}</Text>
    </Pressable>
  );
  return (
    <View style={{ backgroundColor: theme.colors.surface, borderBottomColor: theme.colors.border, borderBottomWidth: 1, gap: theme.spacing.xs, paddingHorizontal: theme.spacing.lg, paddingVertical: theme.spacing.md }}>
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          minHeight: 44,
          paddingRight: theme.spacing.xxxl,
        }}
      >
        {backLabel && onBack ? link(backLabel, onBack) : <View />}
        {actionLabel && onAction ? link(actionLabel, onAction) : null}
      </View>
      <Text accessibilityRole="header" style={[theme.typography.title, { color: theme.colors.text }]}>{title}</Text>
      {subtitle ? <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>{subtitle}</Text> : null}
    </View>
  );
}
