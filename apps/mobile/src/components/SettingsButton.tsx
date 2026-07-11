import { Pressable, Text } from 'react-native';

import { useTheme } from '@/design/theme';

export function SettingsButton({
  label,
  hint,
  onPress,
}: {
  label: string;
  hint: string;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityHint={hint}
      accessibilityLabel={label}
      accessibilityRole="button"
      hitSlop={6}
      onPress={onPress}
      style={({ pressed }) => [
        {
          alignItems: 'center',
          backgroundColor: theme.colors.surfaceElevated,
          borderColor: theme.colors.border,
          borderRadius: theme.radii.full,
          borderWidth: 1,
          height: 48,
          justifyContent: 'center',
          opacity: pressed ? 0.76 : 1,
          width: 48,
        },
        theme.elevations.md,
      ]}
      testID="global-settings-button"
    >
      <Text
        accessibilityElementsHidden
        allowFontScaling={false}
        importantForAccessibility="no"
        style={{ color: theme.colors.primary, fontSize: 25, lineHeight: 30 }}
      >
        ⚙
      </Text>
    </Pressable>
  );
}
