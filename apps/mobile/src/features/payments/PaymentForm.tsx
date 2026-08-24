import type { Customer, InvoiceListItem, PaymentCreateRequest } from '@distributoros/api-client';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { FilterChipGroup } from '@/design-system';
import { businessDateIso } from '@/formatting/presentation';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

import { formatInr, paymentMethodKeys } from './formatting';
import {
  normalizePayment,
  type PaymentAllocationDraft,
  type PaymentDraft,
  type PaymentValidationErrors,
  validatePayment,
} from './validation';

interface PaymentFormProps {
  actionLabel: string;
  loadingLabel: string;
  loading: boolean;
  serverFieldErrors?: Record<string, string>;
  onFieldChange?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (payment: PaymentCreateRequest) => Promise<void>;
}

const methods: PaymentCreateRequest['payment_method'][] = [
  'cash',
  'upi',
  'bank_transfer',
  'cheque',
  'other',
];

function todayIso(): string {
  return businessDateIso();
}

export function PaymentForm({
  actionLabel,
  loadingLabel,
  loading,
  serverFieldErrors = {},
  onFieldChange,
  onDirtyChange,
  onSubmit,
}: PaymentFormProps) {
  const { t, i18n } = useTranslation();
  const initialDraft = useMemo<PaymentDraft>(() => ({
    customerId: '',
    customerName: '',
    paymentDate: todayIso(),
    amount: '',
    paymentMethod: 'cash',
    referenceNumber: '',
    notes: '',
    allocations: [],
  }), []);
  const [draft, setDraft] = useState<PaymentDraft>(initialDraft);
  const [validationErrors, setValidationErrors] = useState<PaymentValidationErrors>({});
  const [customerSearch, setCustomerSearch] = useState('');
  const dirty = JSON.stringify(draft) !== JSON.stringify(initialDraft);
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);
  const debouncedCustomerSearch = useDebouncedValue(customerSearch.trim(), 300);
  const customers = useQuery({
    queryKey: ['payments', 'customer-picker', debouncedCustomerSearch],
    queryFn: ({ signal }) => apiClient.listCustomers({
      status: 'active',
      sort: 'name_asc',
      search: debouncedCustomerSearch || undefined,
      limit: 20,
    }, signal),
    placeholderData: keepPreviousData,
  });
  const invoices = useQuery({
    queryKey: ['payments', 'invoice-allocation-targets', draft.customerId],
    queryFn: ({ signal }) => apiClient.listCustomerInvoices(draft.customerId, {
      status: 'issued',
      limit: 50,
    }, signal),
    enabled: Boolean(draft.customerId),
    placeholderData: keepPreviousData,
  });
  const allocationTotal = useMemo(
    () => draft.allocations.reduce((sum, allocation) =>
      sum + (Number(allocation.amount) || 0), 0),
    [draft.allocations],
  );
  const openInvoices = useMemo(
    () => invoices.data?.items.filter((invoice) => Number(invoice.outstanding_amount) > 0) ?? [],
    [invoices.data?.items],
  );

  const clearError = (field: string) => {
    setValidationErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    onFieldChange?.();
  };
  const errorFor = (field: string): string | undefined => {
    const key = validationErrors[field];
    return key ? t(key) : serverFieldErrors[field];
  };
  const updateDraft = (patch: Partial<PaymentDraft>, field?: string) => {
    setDraft((current) => ({ ...current, ...patch }));
    if (field) clearError(field);
    else onFieldChange?.();
  };
  const selectCustomer = (customer: Customer) => {
    setDraft((current) => ({
      ...current,
      customerId: customer.id,
      customerName: customer.name,
      allocations: [],
    }));
    clearError('customer_id');
  };
  const addAllocation = (invoice: InvoiceListItem) => {
    if (draft.allocations.some((allocation) => allocation.invoiceId === invoice.id)) {
      setValidationErrors((current) => ({
        ...current,
        allocations: 'payments.validation.duplicateAllocation',
      }));
      return;
    }
    setDraft((current) => ({
      ...current,
      allocations: [...current.allocations, {
        invoiceId: invoice.id,
        reference: invoice.invoice_number,
        amount: '',
      }],
    }));
    clearError('allocations');
  };
  const updateAllocation = (index: number, amount: string) => {
    setDraft((current) => ({
      ...current,
      allocations: current.allocations.map((allocation, allocationIndex) =>
        allocationIndex === index ? { ...allocation, amount } : allocation),
    }));
    clearError(`allocations.${index}.allocated_amount`);
  };
  const removeAllocation = (index: number) => {
    setDraft((current) => ({
      ...current,
      allocations: current.allocations.filter((_, allocationIndex) => allocationIndex !== index),
    }));
    clearError('allocations');
  };
  const submit = async () => {
    const errors = validatePayment(draft);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    await onSubmit(normalizePayment(draft));
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.form}>
        <PickerSection
          error={errorFor('customer_id')}
          label={t('payments.form.customer')}
          loading={customers.isFetching}
          onSearch={setCustomerSearch}
          placeholder={t('payments.form.customerSearchPlaceholder')}
          search={customerSearch}
        >
          {draft.customerId ? (
            <Text style={styles.selectedText}>
              {t('payments.form.selectedCustomer', { name: draft.customerName })}
            </Text>
          ) : null}
          {customers.isError ? <Text style={styles.error}>{t('payments.errors.customerPicker')}</Text> : null}
          {!customers.isFetching && !customers.isError && customers.data?.items.length === 0 ? (
            <Text style={styles.muted}>{t('payments.form.noCustomers')}</Text>
          ) : null}
          {customers.data?.items.map((customer) => (
            <PickerOption
              key={customer.id}
              detail={customer.customer_code}
              label={customer.name}
              onPress={() => selectCustomer(customer)}
              selected={customer.id === draft.customerId}
            />
          ))}
        </PickerSection>

        <View style={styles.fieldRow}>
          <View style={styles.field}>
            <FormField
              error={errorFor('payment_date')}
              keyboardType="numbers-and-punctuation"
              label={t('payments.form.paymentDate')}
              maxLength={10}
              onChangeText={(value) => updateDraft({ paymentDate: value }, 'payment_date')}
              placeholder={t('payments.form.datePlaceholder')}
              value={draft.paymentDate}
            />
          </View>
          <View style={styles.field}>
            <FormField
              error={errorFor('amount')}
              keyboardType="decimal-pad"
              label={t('payments.form.amount')}
              onChangeText={(value) => updateDraft({ amount: value }, 'amount')}
              placeholder={t('payments.form.amountPlaceholder')}
              value={draft.amount}
            />
          </View>
        </View>

        <View style={styles.methodGroup}>
          {errorFor('payment_method') ? (
            <Text style={styles.error}>{errorFor('payment_method')}</Text>
          ) : null}
          <FilterChipGroup
            label={t('payments.form.paymentMethod')}
            onSelect={(value) =>
              updateDraft({ paymentMethod: value as PaymentCreateRequest['payment_method'] }, 'payment_method')}
            options={methods.map((method) => ({
              label: t(paymentMethodKeys[method]),
              value: method,
            }))}
            selected={draft.paymentMethod}
            testIDPrefix="payment-form-method"
          />
        </View>

        <FormField
          autoCapitalize="characters"
          error={errorFor('reference_number')}
          label={t('payments.form.referenceNumber')}
          maxLength={120}
          onChangeText={(value) => updateDraft({ referenceNumber: value }, 'reference_number')}
          placeholder={t('payments.form.referencePlaceholder')}
          value={draft.referenceNumber}
        />
        <FormField
          error={errorFor('notes')}
          label={t('payments.form.notes')}
          multiline
          onChangeText={(value) => updateDraft({ notes: value }, 'notes')}
          placeholder={t('payments.form.notesPlaceholder')}
          value={draft.notes}
        />

        <View style={styles.allocations}>
          <Text style={styles.sectionTitle}>{t('payments.form.allocations')}</Text>
          <Text style={styles.muted}>{t('payments.form.allocationsHelp')}</Text>
          {errorFor('allocations') ? <Text style={styles.error}>{errorFor('allocations')}</Text> : null}
          {!draft.customerId ? (
            <Text style={styles.muted}>{t('payments.form.selectCustomerForAllocations')}</Text>
          ) : null}
          {invoices.isFetching ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.muted}>{t('payments.form.loadingInvoices')}</Text>
            </View>
          ) : null}
          {invoices.isError ? <Text style={styles.error}>{t('payments.errors.invoicePicker')}</Text> : null}
          {draft.customerId && !invoices.isFetching && !invoices.isError && openInvoices.length === 0 ? (
            <Text style={styles.muted}>{t('payments.form.noInvoices')}</Text>
          ) : null}
          {openInvoices.map((invoice) => (
            <PickerOption
              key={invoice.id}
              detail={`${invoice.invoice_number} · ${formatInr(invoice.outstanding_amount, i18n.language)}`}
              disabled={draft.allocations.some((allocation) => allocation.invoiceId === invoice.id)}
              label={t('payments.form.allocateToReference', { reference: invoice.invoice_number })}
              onPress={() => addAllocation(invoice)}
              selected={draft.allocations.some((allocation) => allocation.invoiceId === invoice.id)}
            />
          ))}
          {draft.allocations.map((allocation, index) => (
            <AllocationRow
              allocation={allocation}
              error={errorFor(`allocations.${index}.allocated_amount`)}
              index={index}
              key={allocation.invoiceId}
              onRemove={() => removeAllocation(index)}
              onUpdate={updateAllocation}
            />
          ))}
        </View>

        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>{t('payments.form.allocationTotal')}</Text>
          <Text style={styles.totalValue}>{formatInr(String(allocationTotal), i18n.language)}</Text>
        </View>
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

function PickerSection({
  children,
  error,
  label,
  loading,
  onSearch,
  placeholder,
  search,
}: {
  children: ReactNode;
  error?: string;
  label: string;
  loading: boolean;
  onSearch: (value: string) => void;
  placeholder: string;
  search: string;
}) {
  return (
    <View style={styles.picker}>
      <Text style={styles.sectionTitle}>{label}</Text>
      <View style={styles.searchRow}>
        <TextInput
          accessibilityLabel={label}
          autoCapitalize="none"
          onChangeText={onSearch}
          placeholder={placeholder}
          placeholderTextColor={colors.textMuted}
          style={styles.search}
          value={search}
        />
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <View style={styles.options}>{children}</View>
    </View>
  );
}

function PickerOption({
  detail,
  disabled = false,
  label,
  onPress,
  selected,
}: {
  detail: string;
  disabled?: boolean;
  label: string;
  onPress: () => void;
  selected: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.option, selected && styles.optionSelected]}
    >
      <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>{label}</Text>
      <Text style={[styles.optionDetail, selected && styles.optionLabelSelected]}>{detail}</Text>
    </Pressable>
  );
}

function AllocationRow({
  allocation,
  error,
  index,
  onRemove,
  onUpdate,
}: {
  allocation: PaymentAllocationDraft;
  error?: string;
  index: number;
  onRemove: () => void;
  onUpdate: (index: number, amount: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.allocationRow}>
      <View style={styles.allocationHeader}>
        <Text style={styles.optionLabel}>{allocation.reference}</Text>
        <Pressable accessibilityRole="button" onPress={onRemove} style={styles.removeButton}>
          <Text style={styles.removeText}>{t('payments.form.removeAllocation')}</Text>
        </Pressable>
      </View>
      <FormField
        error={error}
        keyboardType="decimal-pad"
        label={t('payments.form.allocatedAmount')}
        onChangeText={(value) => onUpdate(index, value)}
        placeholder={t('payments.form.amountPlaceholder')}
        value={allocation.amount}
      />
    </View>
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
    maxWidth: 760,
    padding: spacing.lg,
    width: '100%',
  },
  picker: { gap: spacing.sm },
  sectionTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  searchRow: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  search: {
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.text,
    flex: 1,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: spacing.md,
  },
  options: { gap: spacing.xs, maxHeight: 260 },
  option: {
    borderColor: colors.border,
    borderRadius: radii.sm,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.sm,
  },
  optionSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  optionLabel: { color: colors.text, fontSize: 15, fontWeight: '700' },
  optionLabelSelected: { color: colors.textInverse },
  optionDetail: { color: colors.textMuted, fontSize: 12 },
  selectedText: { color: colors.success, fontSize: 14, fontWeight: '700' },
  error: { color: colors.danger, fontSize: 13 },
  muted: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  fieldRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  field: { flex: 1, minWidth: 180 },
  methodGroup: { gap: spacing.sm },
  allocations: { gap: spacing.sm },
  loadingRow: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  allocationRow: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    gap: spacing.md,
    padding: spacing.md,
  },
  allocationHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  removeButton: { padding: spacing.sm },
  removeText: { color: colors.danger, fontSize: 14, fontWeight: '700' },
  totalRow: {
    alignItems: 'center',
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
  },
  totalLabel: { color: colors.textMuted, fontSize: 15, fontWeight: '700' },
  totalValue: { color: colors.text, fontSize: 22, fontWeight: '800' },
});
