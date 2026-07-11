import type { AdjustmentRequest, PositiveStockRequest } from '@distributoros/api-client';
import { useEffect, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';

import {
  type InventoryDraft,
  type InventoryField,
  type InventoryOperation,
  type InventoryValidationErrors,
  normalizeInventoryRequest,
  validateInventoryDraft,
} from './validation';

interface InventoryOperationFormProps {
  operation: InventoryOperation;
  productId: string;
  currentStock: string;
  loading: boolean;
  serverFieldErrors?: Partial<Record<InventoryField, string>>;
  onFieldChange?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (request: PositiveStockRequest | AdjustmentRequest) => void;
}

export function InventoryOperationForm({
  operation,
  productId,
  currentStock,
  loading,
  serverFieldErrors = {},
  onFieldChange,
  onDirtyChange,
  onSubmit,
}: InventoryOperationFormProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<InventoryDraft>({ quantity: '', notes: '' });
  const [validationErrors, setValidationErrors] = useState<InventoryValidationErrors>({});
  const dirty = Boolean(draft.quantity || draft.notes);
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const update = (field: InventoryField, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setValidationErrors((current) => ({ ...current, [field]: undefined }));
    onFieldChange?.();
  };
  const errorFor = (field: InventoryField) => {
    const key = validationErrors[field];
    return key ? t(key) : serverFieldErrors[field];
  };
  const submit = () => {
    const errors = validateInventoryDraft(draft, operation);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    onSubmit(normalizeInventoryRequest(draft, operation, productId));
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.form}>
        <View style={styles.stockSummary}>
          <Text style={styles.stockLabel}>{t('inventory.operations.currentStock')}</Text>
          <Text style={styles.stockValue}>{currentStock}</Text>
        </View>
        <FormField
          error={errorFor('quantity')}
          keyboardType={operation === 'adjustment' ? 'numbers-and-punctuation' : 'decimal-pad'}
          label={t('inventory.operations.quantity')}
          onChangeText={(value) => update('quantity', value)}
          placeholder={t('inventory.operations.quantityPlaceholder')}
          value={draft.quantity}
        />
        <FormField
          error={errorFor('notes')}
          label={
            operation === 'adjustment'
              ? t('inventory.operations.reason')
              : t('inventory.operations.remarks')
          }
          maxLength={1001}
          multiline
          numberOfLines={4}
          onChangeText={(value) => update('notes', value)}
          placeholder={
            operation === 'adjustment'
              ? t('inventory.operations.reasonPlaceholder')
              : t('inventory.operations.remarksPlaceholder')
          }
          textAlignVertical="top"
          value={draft.notes}
        />
        <PrimaryButton
          label={t('inventory.operations.submit')}
          loading={loading}
          loadingLabel={t('inventory.operations.loading')}
          onPress={submit}
        />
      </View>
    </ScrollView>
  );
}

const styles = ThemedStyleSheet.create({
  content: { alignItems: 'center', padding: spacing.lg },
  form: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.lg,
    maxWidth: 720,
    padding: spacing.lg,
    width: '100%',
  },
  stockSummary: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    gap: spacing.xs,
    padding: spacing.md,
  },
  stockLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700' },
  stockValue: { color: colors.text, fontSize: 22, fontWeight: '800' },
});
