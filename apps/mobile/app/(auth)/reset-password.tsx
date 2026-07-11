import { type Href, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { spacing } from '@/design/tokens';
import { AuthScreenLayout } from '@/features/auth/AuthScreenLayout';
import { useAuth } from '@/features/auth/AuthContext';
import { getErrorTranslationKey } from '@/features/auth/errorMessages';
import { validateNewPasswords, type PasswordValidationErrors } from '@/features/auth/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function ResetPasswordScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const { token = '' } = useLocalSearchParams<{ token?: string }>();
  const { resetPassword } = useAuth();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<PasswordValidationErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();

  const submit = async () => {
    const validationErrors = validateNewPasswords(newPassword, confirmPassword);
    setErrors(validationErrors);
    setRequestError(null);
    if (Object.keys(validationErrors).length > 0) return;
    await run(async () => {
      try {
        await resetPassword({ token, new_password: newPassword });
        router.replace('/(auth)/login?notice=password-reset' as Href);
      } catch (error) {
        setRequestError(t(getErrorTranslationKey(error)));
      }
    });
  };

  return (
    <AuthScreenLayout subtitle={t('password.resetSubtitle')} title={t('password.resetTitle')}>
      {requestError ? <FeedbackBanner message={requestError} /> : null}
      <View style={{ gap: spacing.md }}>
        <FormField
          autoComplete="new-password"
          error={errors.newPassword ? t(errors.newPassword) : undefined}
          label={t('password.newPassword')}
          maxLength={128}
          onChangeText={setNewPassword}
          secureTextEntry
          value={newPassword}
        />
        <FormField
          autoComplete="new-password"
          error={errors.confirmPassword ? t(errors.confirmPassword) : undefined}
          label={t('password.confirmPassword')}
          maxLength={128}
          onChangeText={setConfirmPassword}
          secureTextEntry
          value={confirmPassword}
        />
      </View>
      <PrimaryButton
        label={t('password.resetAction')}
        loading={pending}
        loadingLabel={t('password.resetLoading')}
        onPress={() => void submit()}
      />
    </AuthScreenLayout>
  );
}
