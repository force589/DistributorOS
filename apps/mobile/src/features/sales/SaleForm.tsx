import type {
  Customer,
  Product,
  ProductUnit,
  Sale,
  SaleCreateRequest,
} from '@distributoros/api-client';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
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
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { productUnitKeys } from '@/features/products/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

import { formatInr } from './formatting';
import {
  normalizeSale,
  type SaleDraft,
  type SaleDraftLine,
  type SaleValidationErrors,
  validateSale,
} from './validation';

interface SaleFormProps {
  initialSale?: Sale;
  actionLabel: string;
  loadingLabel: string;
  loading: boolean;
  serverFieldErrors?: Record<string, string>;
  onFieldChange?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (sale: SaleCreateRequest) => Promise<void>;
}

function initialDraft(sale?: Sale): SaleDraft {
  return {
    customerId: sale?.customer_id ?? '',
    customerName: sale?.customer_name ?? '',
    items: sale?.items.map((item) => ({
      productId: item.product_id,
      productName: item.product_name_snapshot,
      unit: item.unit_snapshot,
      quantity: item.quantity,
      unitPrice: item.unit_price,
    })) ?? [],
  };
}

export function SaleForm({
  initialSale,
  actionLabel,
  loadingLabel,
  loading,
  serverFieldErrors = {},
  onFieldChange,
  onDirtyChange,
  onSubmit,
}: SaleFormProps) {
  const { t, i18n } = useTranslation();
  const baseline = useMemo(() => initialDraft(initialSale), [initialSale]);
  const [draft, setDraft] = useState<SaleDraft>(baseline);
  const [validationErrors, setValidationErrors] = useState<SaleValidationErrors>({});
  const [customerSearch, setCustomerSearch] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [removingIndex, setRemovingIndex] = useState<number | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);
  const debouncedCustomerSearch = useDebouncedValue(customerSearch.trim(), 300);
  const debouncedProductSearch = useDebouncedValue(productSearch.trim(), 300);
  const customers = useQuery({
    queryKey: ['sales', 'customer-picker', debouncedCustomerSearch],
    queryFn: ({ signal }) => apiClient.listCustomers({
      status: 'active',
      sort: 'name_asc',
      search: debouncedCustomerSearch || undefined,
      limit: 20,
    }, signal),
    placeholderData: keepPreviousData,
  });
  const products = useQuery({
    queryKey: ['sales', 'product-picker', debouncedProductSearch],
    queryFn: ({ signal }) => apiClient.listProducts({
      status: 'active',
      sort: 'name_asc',
      search: debouncedProductSearch || undefined,
      limit: 20,
    }, signal),
    placeholderData: keepPreviousData,
  });
  const subtotal = useMemo(
    () => draft.items.reduce(
      (sum, item) => sum + (Number(item.quantity) * Number(item.unitPrice) || 0),
      0,
    ),
    [draft.items],
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
  const selectCustomer = (customer: Customer) => {
    setDraft((current) => ({
      ...current,
      customerId: customer.id,
      customerName: customer.name,
    }));
    clearError('customer_id');
  };
  const addProduct = (product: Product) => {
    if (draft.items.some((item) => item.productId === product.id)) {
      setValidationErrors((current) => ({
        ...current,
        items: 'sales.validation.duplicateProduct',
      }));
      return;
    }
    if (draft.items.length >= 100) {
      setValidationErrors((current) => ({
        ...current,
        items: 'sales.validation.itemsTooMany',
      }));
      return;
    }
    setDraft((current) => ({
      ...current,
      items: [...current.items, {
        productId: product.id,
        productName: product.name,
        unit: product.unit,
        quantity: '1',
        unitPrice: product.selling_price,
      }],
    }));
    clearError('items');
  };
  const updateLine = (index: number, field: 'quantity' | 'unitPrice', value: string) => {
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item),
    }));
    clearError(`items.${index}.${field === 'unitPrice' ? 'unit_price' : field}`);
  };
  const removeLine = () => {
    if (removingIndex === null) return;
    setDraft((current) => ({
      ...current,
      items: current.items.filter((_, index) => index !== removingIndex),
    }));
    setRemovingIndex(null);
    setValidationErrors({});
    onFieldChange?.();
  };
  const submit = async () => {
    const errors = validateSale(draft);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    await onSubmit(normalizeSale(draft));
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.form}>
        <PickerSection
          error={errorFor('customer_id')}
          label={t('sales.form.customer')}
          loading={customers.isFetching}
          onSearch={setCustomerSearch}
          placeholder={t('sales.form.customerSearchPlaceholder')}
          search={customerSearch}
        >
          {draft.customerId ? (
            <Text style={styles.selectedText}>
              {t('sales.form.selectedCustomer', { name: draft.customerName })}
            </Text>
          ) : null}
          {customers.isError ? <Text style={styles.error}>{t('sales.errors.customerPicker')}</Text> : null}
          {!customers.isFetching && !customers.isError && customers.data?.items.length === 0 ? (
            <Text style={styles.muted}>{t('sales.form.noCustomers')}</Text>
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

        <PickerSection
          error={errorFor('items')}
          label={t('sales.form.products')}
          loading={products.isFetching}
          onSearch={setProductSearch}
          placeholder={t('sales.form.productSearchPlaceholder')}
          search={productSearch}
        >
          {products.isError ? <Text style={styles.error}>{t('sales.errors.productPicker')}</Text> : null}
          {!products.isFetching && !products.isError && products.data?.items.length === 0 ? (
            <Text style={styles.muted}>{t('sales.form.noProducts')}</Text>
          ) : null}
          {products.data?.items.map((product) => (
            <PickerOption
              key={product.id}
              detail={`${product.product_code} · ${formatInr(product.selling_price, i18n.language)}`}
              disabled={draft.items.some((item) => item.productId === product.id)}
              label={product.name}
              onPress={() => addProduct(product)}
              selected={draft.items.some((item) => item.productId === product.id)}
            />
          ))}
        </PickerSection>

        <View style={styles.lines}>
          <Text style={styles.sectionTitle}>{t('sales.form.saleItems')}</Text>
          {draft.items.length === 0 ? (
            <Text style={styles.muted}>{t('sales.form.noItems')}</Text>
          ) : null}
          {draft.items.map((item, index) => (
            <SaleLine
              key={item.productId}
              errorFor={errorFor}
              index={index}
              item={item}
              onRemove={() => setRemovingIndex(index)}
              onUpdate={updateLine}
            />
          ))}
        </View>
        <View style={styles.subtotalRow}>
          <Text style={styles.subtotalLabel}>{t('sales.form.subtotal')}</Text>
          <Text style={styles.subtotalValue}>{formatInr(String(subtotal), i18n.language)}</Text>
        </View>
        <PrimaryButton
          label={actionLabel}
          loading={loading}
          loadingLabel={loadingLabel}
          onPress={() => void submit()}
        />
      </View>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={t('sales.form.removeConfirm')}
        loadingLabel={t('sales.form.removeConfirm')}
        message={t('sales.form.removeMessage')}
        onCancel={() => setRemovingIndex(null)}
        onConfirm={removeLine}
        title={t('sales.form.removeTitle')}
        visible={removingIndex !== null}
      />
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
  children: React.ReactNode;
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

function SaleLine({
  errorFor,
  index,
  item,
  onRemove,
  onUpdate,
}: {
  errorFor: (field: string) => string | undefined;
  index: number;
  item: SaleDraftLine;
  onRemove: () => void;
  onUpdate: (index: number, field: 'quantity' | 'unitPrice', value: string) => void;
}) {
  const { t } = useTranslation();
  const unitKey = productUnitKeys[item.unit as ProductUnit];
  return (
    <View style={styles.line}>
      <View style={styles.lineHeader}>
        <View style={styles.lineNameGroup}>
          <Text style={styles.lineName}>{item.productName}</Text>
          <Text style={styles.muted}>{unitKey ? t(unitKey) : item.unit}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={onRemove} style={styles.removeButton}>
          <Text style={styles.removeText}>{t('sales.form.remove')}</Text>
        </Pressable>
      </View>
      <View style={styles.fieldRow}>
        <View style={styles.field}>
          <FormField
            error={errorFor(`items.${index}.quantity`)}
            keyboardType="decimal-pad"
            label={t('sales.form.quantity')}
            onChangeText={(value) => onUpdate(index, 'quantity', value)}
            value={item.quantity}
          />
        </View>
        <View style={styles.field}>
          <FormField
            error={errorFor(`items.${index}.unit_price`)}
            keyboardType="decimal-pad"
            label={t('sales.form.unitPrice')}
            onChangeText={(value) => onUpdate(index, 'unitPrice', value)}
            value={item.unitPrice}
          />
        </View>
      </View>
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
  options: { gap: spacing.xs, maxHeight: 220 },
  option: {
    borderColor: colors.border,
    borderRadius: radii.sm,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.sm,
  },
  optionSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  optionLabel: { color: colors.text, fontSize: 15, fontWeight: '700' },
  optionLabelSelected: { color: colors.surface },
  optionDetail: { color: colors.textMuted, fontSize: 12 },
  selectedText: { color: colors.success, fontSize: 14, fontWeight: '700' },
  error: { color: colors.danger, fontSize: 13 },
  muted: { color: colors.textMuted, fontSize: 14 },
  lines: { gap: spacing.md },
  line: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    gap: spacing.md,
    padding: spacing.md,
  },
  lineHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  lineNameGroup: { flex: 1, gap: spacing.xs },
  lineName: { color: colors.text, fontSize: 16, fontWeight: '800' },
  removeButton: { padding: spacing.sm },
  removeText: { color: colors.danger, fontSize: 14, fontWeight: '700' },
  fieldRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  field: { flex: 1, minWidth: 180 },
  subtotalRow: {
    alignItems: 'center',
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
  },
  subtotalLabel: { color: colors.textMuted, fontSize: 15, fontWeight: '700' },
  subtotalValue: { color: colors.text, fontSize: 22, fontWeight: '800' },
});
