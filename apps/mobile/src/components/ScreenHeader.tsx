import { Pressable, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { HeadingText } from '@/design-system';
import { useUnsavedChanges } from '@/navigation/UnsavedChangesContext';

type ScreenHeaderLevel = 'primary' | 'nested' | 'modal';
type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  level?: ScreenHeaderLevel;
  headingLevel?: HeadingLevel;
  backLabel?: string;
  onBack?: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

export function ScreenHeader({
  title,
  subtitle,
  level = 'nested',
  headingLevel = 1,
  backLabel,
  onBack,
  actionLabel,
  onAction,
}: ScreenHeaderProps) {
  const theme = useTheme();
  const { guardNavigation } = useUnsavedChanges();
  const showBack = level !== 'primary' && Boolean(backLabel && onBack);
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
        {showBack && backLabel && onBack ? link(backLabel, onBack) : <View />}
        {actionLabel && onAction ? link(actionLabel, onAction) : null}
      </View>
      <HeadingText level={headingLevel} style={[theme.typography.title, { color: theme.colors.text }]}>{title}</HeadingText>
      {subtitle ? <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>{subtitle}</Text> : null}
    </View>
  );
}
