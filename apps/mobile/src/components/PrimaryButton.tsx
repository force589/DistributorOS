import { Button } from '@/design-system';

interface PrimaryButtonProps {
  label: string;
  onPress: () => void;
  loadingLabel?: string;
  loading?: boolean;
  disabled?: boolean;
  destructive?: boolean;
  testID?: string;
}

export function PrimaryButton({
  label,
  onPress,
  loadingLabel,
  loading = false,
  disabled = false,
  destructive = false,
  testID,
}: PrimaryButtonProps) {
  return (
    <Button
      disabled={disabled}
      label={loading ? (loadingLabel ?? label) : label}
      loading={loading}
      onPress={onPress}
      testID={testID}
      variant={destructive ? 'destructive' : 'primary'}
    />
  );
}
