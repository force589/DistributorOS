import type { Customer, CustomerCreateRequest } from '@distributoros/api-client';
import { useEffect, useMemo, useState } from 'react';
import { ScrollView, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';

import {
  type CustomerField,
  type CustomerValidationErrors,
  normalizeCustomer,
  validateCustomer,
} from './validation';

type CustomerDraft = Record<CustomerField, string>;

interface CustomerFormProps {
  initialCustomer?: Customer;
  actionLabel: string;
  loadingLabel: string;
  loading: boolean;
  serverFieldErrors?: Partial<Record<CustomerField, string>>;
  onFieldChange?: (field: CustomerField) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (customer: CustomerCreateRequest) => Promise<void>;
}

function toDraft(customer?: Customer): CustomerDraft {
  return {
    name: customer?.name ?? '',
    phone: customer?.phone ?? '',
    email: customer?.email ?? '',
    address_line_1: customer?.address_line_1 ?? '',
    address_line_2: customer?.address_line_2 ?? '',
    city: customer?.city ?? '',
    state: customer?.state ?? '',
    postal_code: customer?.postal_code ?? '',
    notes: customer?.notes ?? '',
  };
}

export function CustomerForm({
  initialCustomer,
  actionLabel,
  loadingLabel,
  loading,
  serverFieldErrors = {},
  onFieldChange,
  onDirtyChange,
  onSubmit,
}: CustomerFormProps) {
  const { t } = useTranslation();
  const initialDraft = useMemo(() => toDraft(initialCustomer), [initialCustomer]);
  const [draft, setDraft] = useState<CustomerDraft>(initialDraft);
  const [validationErrors, setValidationErrors] = useState<CustomerValidationErrors>({});
  const dirty = JSON.stringify(draft) !== JSON.stringify(initialDraft);
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const update = (field: CustomerField, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setValidationErrors((current) => ({ ...current, [field]: undefined }));
    onFieldChange?.(field);
  };

  const errorFor = (field: CustomerField): string | undefined => {
    const localKey = validationErrors[field];
    return localKey ? t(localKey) : serverFieldErrors[field];
  };

  const submit = async () => {
    const errors = validateCustomer(draft);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    await onSubmit(normalizeCustomer(draft));
  };

  return (
    <ScrollView
      contentContainerStyle={styles.scrollContent}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.form}>
        <FormField
          autoCapitalize="words"
          error={errorFor('name')}
          label={t('customers.fields.name')}
          maxLength={161}
          onChangeText={(value) => update('name', value)}
          placeholder={t('customers.placeholders.name')}
          value={draft.name}
        />
        <FormField
          error={errorFor('phone')}
          keyboardType="phone-pad"
          label={t('customers.fields.phone')}
          maxLength={32}
          onChangeText={(value) => update('phone', value)}
          placeholder={t('customers.placeholders.phone')}
          value={draft.phone}
        />
        <FormField
          autoCapitalize="none"
          autoCorrect={false}
          error={errorFor('email')}
          keyboardType="email-address"
          label={t('customers.fields.email')}
          maxLength={320}
          onChangeText={(value) => update('email', value)}
          placeholder={t('customers.placeholders.email')}
          value={draft.email}
        />
        <FormField
          error={errorFor('address_line_1')}
          label={t('customers.fields.addressLine1')}
          maxLength={201}
          onChangeText={(value) => update('address_line_1', value)}
          placeholder={t('customers.placeholders.addressLine1')}
          value={draft.address_line_1}
        />
        <FormField
          error={errorFor('address_line_2')}
          label={t('customers.fields.addressLine2')}
          maxLength={201}
          onChangeText={(value) => update('address_line_2', value)}
          placeholder={t('customers.placeholders.addressLine2')}
          value={draft.address_line_2}
        />
        <View style={styles.row}>
          <View style={styles.rowField}>
            <FormField
              error={errorFor('city')}
              label={t('customers.fields.city')}
              maxLength={101}
              onChangeText={(value) => update('city', value)}
              placeholder={t('customers.placeholders.city')}
              value={draft.city}
            />
          </View>
          <View style={styles.rowField}>
            <FormField
              error={errorFor('state')}
              label={t('customers.fields.state')}
              maxLength={101}
              onChangeText={(value) => update('state', value)}
              placeholder={t('customers.placeholders.state')}
              value={draft.state}
            />
          </View>
        </View>
        <FormField
          error={errorFor('postal_code')}
          label={t('customers.fields.postalCode')}
          maxLength={21}
          onChangeText={(value) => update('postal_code', value)}
          placeholder={t('customers.placeholders.postalCode')}
          value={draft.postal_code}
        />
        <FormField
          error={errorFor('notes')}
          label={t('customers.fields.notes')}
          maxLength={2001}
          multiline
          numberOfLines={4}
          onChangeText={(value) => update('notes', value)}
          placeholder={t('customers.placeholders.notes')}
          textAlignVertical="top"
          value={draft.notes}
        />
        <PrimaryButton
          label={actionLabel}
          loading={loading}
          loadingLabel={loadingLabel}
          onPress={() => void submit()}
        />
      </View>
    </ScrollView>
  );
}

const styles = ThemedStyleSheet.create({
  scrollContent: {
    alignItems: 'center',
    padding: spacing.lg,
  },
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
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  rowField: {
    flex: 1,
    minWidth: 220,
  },
});
