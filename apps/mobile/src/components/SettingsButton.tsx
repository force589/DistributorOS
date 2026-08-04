import { appIcons } from '@/design/icons';
import { IconButton } from '@/design-system';

export function SettingsButton({
  label,
  hint,
  onPress,
}: {
  label: string;
  hint: string;
  onPress: () => void;
}) {
  return (
    <IconButton
      accessibilityHint={hint}
      accessibilityLabel={label}
      icon={appIcons.settings}
      onPress={onPress}
      testID="global-settings-button"
    />
  );
}
