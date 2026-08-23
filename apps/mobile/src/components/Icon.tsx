import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { type ColorValue, type StyleProp, type TextStyle } from 'react-native';

import { iconSizes } from '@/design/tokens';
import { useTheme } from '@/design/theme';
import type { AppIconName } from '@/design/icons';

export type AppIconSize = keyof typeof iconSizes | number;

function resolveIconSize(size: AppIconSize): number {
  return typeof size === 'number' ? size : iconSizes[size];
}

export function Icon({
  accessibilityLabel,
  color,
  decorative = true,
  name,
  size = 'md',
  style,
}: {
  accessibilityLabel?: string;
  color?: ColorValue;
  decorative?: boolean;
  name: AppIconName;
  size?: AppIconSize;
  style?: StyleProp<TextStyle>;
}) {
  const theme = useTheme();
  const resolvedSize = resolveIconSize(size);
  const accessibilityProps = decorative
    ? {
        'aria-hidden': true,
        accessible: false,
        accessibilityElementsHidden: true,
        importantForAccessibility: 'no-hide-descendants' as const,
      }
    : {
        accessible: true,
        accessibilityLabel,
        accessibilityRole: 'image' as const,
      };

  return (
    <MaterialCommunityIcons
      allowFontScaling={false}
      color={color ?? theme.colors.textMuted}
      name={name}
      size={resolvedSize}
      style={[{ height: resolvedSize, lineHeight: resolvedSize, width: resolvedSize }, style]}
      {...accessibilityProps}
    />
  );
}
