import type { Product, ProductCreateRequest, ProductUnit } from '@distributoros/api-client';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';

import { productUnitKeys } from './formatting';
import {
  normalizeProduct,
  type ProductDraft,
  type ProductField,
  type ProductValidationErrors,
  productUnits,
  validateProduct,
} from './validation';

interface ProductFormProps {
  initialProduct?: Product;
  actionLabel: string;
  loadingLabel: string;
  loading: boolean;
  serverFieldErrors?: Partial<Record<ProductField, string>>;
  onFieldChange?: (field: ProductField) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (product: ProductCreateRequest) => Promise<void>;
}

function toDraft(product?: Product): ProductDraft {
  return {
    name: product?.name ?? '',
    sku: product?.sku ?? '',
    barcode: product?.barcode ?? '',
    category: product?.category ?? '',
    description: product?.description ?? '',
    selling_price: product?.selling_price ?? '',
    unit: product?.unit ?? '',
    low_stock_threshold: product?.low_stock_threshold ?? '',
  };
}

export function ProductForm({
  initialProduct,
  actionLabel,
  loadingLabel,
  loading,
  serverFieldErrors = {},
  onFieldChange,
  onDirtyChange,
  onSubmit,
}: ProductFormProps) {
  const { t } = useTranslation();
  const initialDraft = useMemo(() => toDraft(initialProduct), [initialProduct]);
  const [draft, setDraft] = useState<ProductDraft>(initialDraft);
  const [validationErrors, setValidationErrors] = useState<ProductValidationErrors>({});
  const dirty = JSON.stringify(draft) !== JSON.stringify(initialDraft);
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const update = (field: ProductField, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setValidationErrors((current) => ({ ...current, [field]: undefined }));
    onFieldChange?.(field);
  };

  const chooseUnit = (unit: ProductUnit) => {
    setDraft((current) => ({ ...current, unit }));
    setValidationErrors((current) => ({ ...current, unit: undefined }));
    onFieldChange?.('unit');
  };

  const errorFor = (field: ProductField): string | undefined => {
    const key = validationErrors[field];
    return key ? t(key) : serverFieldErrors[field];
  };

  const submit = async () => {
    const errors = validateProduct(draft);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) return;
    await onSubmit(normalizeProduct(draft));
  };

  return (
    <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={styles.form}>
        <FormField
          autoCapitalize="words"
          error={errorFor('name')}
          label={t('products.fields.name')}
          maxLength={161}
          onChangeText={(value) => update('name', value)}
          placeholder={t('products.placeholders.name')}
          value={draft.name}
        />
        <View style={styles.row}>
          <View style={styles.rowField}>
            <FormField
              error={errorFor('selling_price')}
              keyboardType="decimal-pad"
              label={t('products.fields.sellingPrice')}
              onChangeText={(value) => update('selling_price', value)}
              placeholder={t('products.placeholders.sellingPrice')}
              value={draft.selling_price}
            />
          </View>
          <View style={styles.rowField}>
            <FormField
              error={errorFor('low_stock_threshold')}
              keyboardType="decimal-pad"
              label={t('products.fields.lowStockThreshold')}
              onChangeText={(value) => update('low_stock_threshold', value)}
              placeholder={t('products.placeholders.lowStockThreshold')}
              value={draft.low_stock_threshold}
            />
          </View>
        </View>
        <View style={styles.unitGroup}>
          <Text style={styles.unitLabel}>{t('products.fields.unit')}</Text>
          <ScrollView
            contentContainerStyle={styles.unitRow}
            horizontal
            showsHorizontalScrollIndicator={false}
          >
            {productUnits.map((unit) => (
              <Pressable
                key={unit}
                accessibilityRole="button"
                accessibilityState={{ selected: draft.unit === unit }}
                onPress={() => chooseUnit(unit)}
                style={[styles.unitChip, draft.unit === unit && styles.selectedUnitChip]}
              >
                <Text
                  style={[
                    styles.unitChipText,
                    draft.unit === unit && styles.selectedUnitChipText,
                  ]}
                >
                  {t(productUnitKeys[unit])}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
          {errorFor('unit') ? <Text style={styles.error}>{errorFor('unit')}</Text> : null}
        </View>
        <View style={styles.row}>
          <View style={styles.rowField}>
            <FormField
              autoCapitalize="characters"
              error={errorFor('sku')}
              label={t('products.fields.sku')}
              maxLength={101}
              onChangeText={(value) => update('sku', value)}
              placeholder={t('products.placeholders.sku')}
              value={draft.sku}
            />
          </View>
          <View style={styles.rowField}>
            <FormField
              autoCapitalize="none"
              error={errorFor('barcode')}
              label={t('products.fields.barcode')}
              maxLength={129}
              onChangeText={(value) => update('barcode', value)}
              placeholder={t('products.placeholders.barcode')}
              value={draft.barcode}
            />
          </View>
        </View>
        <FormField
          error={errorFor('category')}
          label={t('products.fields.category')}
          maxLength={101}
          onChangeText={(value) => update('category', value)}
          placeholder={t('products.placeholders.category')}
          value={draft.category}
        />
        <FormField
          error={errorFor('description')}
          label={t('products.fields.description')}
          maxLength={2001}
          multiline
          numberOfLines={4}
          onChangeText={(value) => update('description', value)}
          placeholder={t('products.placeholders.description')}
          textAlignVertical="top"
          value={draft.description}
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
  scrollContent: { alignItems: 'center', padding: spacing.lg },
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
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  rowField: { flex: 1, minWidth: 220 },
  unitGroup: { gap: spacing.sm },
  unitLabel: { color: colors.text, fontSize: 14, fontWeight: '600' },
  unitRow: { gap: spacing.sm },
  unitChip: {
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    minHeight: 44,
    paddingVertical: spacing.sm,
  },
  selectedUnitChip: { backgroundColor: colors.primary, borderColor: colors.primary },
  unitChipText: { color: colors.text, fontSize: 14, fontWeight: '600' },
  selectedUnitChipText: { color: colors.surface },
  error: { color: colors.danger, fontSize: 13 },
});
