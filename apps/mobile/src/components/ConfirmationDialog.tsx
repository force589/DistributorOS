import { View } from 'react-native';

import { useTheme } from '@/design/theme';
import { Button, Dialog } from '@/design-system';

interface ConfirmationDialogProps {
  visible: boolean;
  title: string;
  message: string;
  cancelLabel: string;
  confirmLabel: string;
  confirmAccessibilityLabel?: string;
  loadingLabel: string;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmationDialog({
  visible,
  title,
  message,
  cancelLabel,
  confirmLabel,
  confirmAccessibilityLabel,
  loadingLabel,
  loading = false,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const theme = useTheme();
  return (
    <Dialog message={message} onDismiss={loading ? () => undefined : onCancel} title={title} visible={visible}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing.sm, justifyContent: 'flex-end' }}>
        <Button disabled={loading} label={cancelLabel} onPress={onCancel} variant="ghost" />
        <Button
          accessibilityLabel={confirmAccessibilityLabel}
          label={loading ? loadingLabel : confirmLabel}
          loading={loading}
          onPress={onConfirm}
          variant="destructive"
        />
      </View>
    </Dialog>
  );
}
