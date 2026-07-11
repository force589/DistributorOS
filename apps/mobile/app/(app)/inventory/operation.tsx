import {
  ApiError,
  type AdjustmentRequest,
  createIdempotencyKey,
  type InventoryMutationResponse,
  type PositiveStockRequest,
} from '@distributoros/api-client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FullScreenState } from '@/components/FullScreenState';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, spacing } from '@/design/tokens';
import { getInventoryErrorTranslationKey } from '@/features/inventory/errorMessages';
import { formatStockQuantity } from '@/features/inventory/formatting';
import { InventoryOperationForm } from '@/features/inventory/InventoryOperationForm';
import {
  type InventoryField,
  type InventoryOperation,
  isInventoryOperation,
} from '@/features/inventory/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

const operationKeys: Record<InventoryOperation, { title: string; subtitle: string }> = {
  opening: {
    title: 'inventory.operations.openingTitle',
    subtitle: 'inventory.operations.openingSubtitle',
  },
  receipt: {
    title: 'inventory.operations.receiptTitle',
    subtitle: 'inventory.operations.receiptSubtitle',
  },
  adjustment: {
    title: 'inventory.operations.adjustmentTitle',
    subtitle: 'inventory.operations.adjustmentSubtitle',
  },
  customerReturn: {
    title: 'inventory.operations.customerReturnTitle',
    subtitle: 'inventory.operations.customerReturnSubtitle',
  },
  damage: {
    title: 'inventory.operations.damageTitle',
    subtitle: 'inventory.operations.damageSubtitle',
  },
  spoilage: {
    title: 'inventory.operations.spoilageTitle',
    subtitle: 'inventory.operations.spoilageSubtitle',
  },
};

type InventoryRequest = PositiveStockRequest | AdjustmentRequest;

export default function InventoryOperationScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ productCode: string; type: string }>();
  const productCode = Array.isArray(params.productCode)
    ? params.productCode[0]
    : params.productCode;
  const rawType = Array.isArray(params.type) ? params.type[0] : params.type;
  const operation = isInventoryOperation(rawType) ? rawType : null;
  const [request, setRequest] = useState<InventoryRequest | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<InventoryField, string>>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);
  const idempotencyKey = useRef<string | null>(null);
  const { pending, run } = useSingleFlightAction();
  const query = useQuery({
    queryKey: ['inventory', 'operation', productCode],
    queryFn: async ({ signal }) => {
      const product = await apiClient.getProductByCode(productCode, signal);
      const stock = await apiClient.getCurrentStock(product.id, undefined, signal);
      return { product, stock };
    },
    enabled: Boolean(productCode && operation),
  });

  if (!operation) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('inventory.details.errorMessage')}
        onAction={() => router.replace('/inventory')}
        title={t('inventory.details.errorTitle')}
      />
    );
  }
  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('inventory.details.loadingMessage')}
        title={t('inventory.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('inventory.details.errorMessage')}
        onAction={() => router.replace('/inventory')}
        title={t('inventory.details.errorTitle')}
      />
    );
  }
  const { product, stock } = query.data;
  const review = (nextRequest: InventoryRequest) => {
    if (!idempotencyKey.current) idempotencyKey.current = createIdempotencyKey();
    setRequest(nextRequest);
    setConfirming(true);
  };
  const post = async () => {
    if (!request || !idempotencyKey.current) return;
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        let result: InventoryMutationResponse;
        if (operation === 'adjustment') {
          result = await apiClient.createStockAdjustment(
            request as AdjustmentRequest,
            idempotencyKey.current!,
          );
        } else {
          const payload = request as PositiveStockRequest;
          const action = {
            opening: apiClient.createOpeningStock.bind(apiClient),
            receipt: apiClient.createStockReceipt.bind(apiClient),
            customerReturn: apiClient.createCustomerReturn.bind(apiClient),
            damage: apiClient.createDamageEntry.bind(apiClient),
            spoilage: apiClient.createSpoilageEntry.bind(apiClient),
          }[operation];
          result = await action(payload, idempotencyKey.current!);
        }
        idempotencyKey.current = null;
        queryClient.setQueryData(
          ['inventory', 'current', productCode],
          { product, stock: result.stock },
        );
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
          queryClient.invalidateQueries({
            queryKey: ['inventory', 'history', product.id],
          }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.dismissTo({
            pathname: '/inventory/[productCode]',
            params: { productCode, notice: 'created' },
          }));
      } catch (postError) {
        if (postError instanceof ApiError) {
          setFieldErrors({
            quantity: postError.fieldErrors.quantity,
            notes: postError.fieldErrors.reason ?? postError.fieldErrors.remarks,
          });
        }
        setError(t(getInventoryErrorTranslationKey(postError, 'submit')));
        setConfirming(false);
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/inventory/${productCode}`)}
        subtitle={t(operationKeys[operation].subtitle)}
        title={t(operationKeys[operation].title)}
      />
      {error ? <View style={styles.feedback}><FeedbackBanner message={error} /></View> : null}
      <InventoryOperationForm
        currentStock={formatStockQuantity(
          stock.available_quantity,
          stock.unit,
          i18n.language,
          t,
        )}
        loading={pending}
        onDirtyChange={setDirty}
        onFieldChange={() => {
          idempotencyKey.current = null;
          setError(null);
          setFieldErrors({});
        }}
        onSubmit={review}
        operation={operation}
        productId={product.id}
        serverFieldErrors={fieldErrors}
      />
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={t('inventory.operations.confirm')}
        loading={pending}
        loadingLabel={t('inventory.operations.loading')}
        message={t('inventory.operations.confirmMessage')}
        onCancel={() => setConfirming(false)}
        onConfirm={() => void post()}
        title={t('inventory.operations.confirmTitle')}
        visible={confirming}
      />
    </SafeAreaView>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  feedback: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
});
