import { ApiError } from '@distributoros/api-client';
import { type Href, useRouter } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FormField } from '@/components/FormField';
import { ScreenHeader } from '@/components/ScreenHeader';
import { useResponsiveLayout } from '@/design/responsive';
import { useTheme } from '@/design/theme';
import { Button, Card } from '@/design-system';
import { useAuth } from '@/features/auth/AuthContext';
import { getErrorTranslationKey } from '@/features/auth/errorMessages';
import { validateNewPasswords, type PasswordValidationErrors } from '@/features/auth/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function ChangePasswordScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const responsive = useResponsiveLayout();
  const theme = useTheme();
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<PasswordValidationErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();
  useDirtyFormGuard(Boolean(currentPassword || newPassword || confirmPassword));

  const submit = async () => {
    const validationErrors = validateNewPasswords(
      newPassword,
      confirmPassword,
      currentPassword,
    );
    setErrors(validationErrors);
    setRequestError(null);
    if (Object.keys(validationErrors).length > 0) return;
    await run(async () => {
      try {
        await changePassword({
          current_password: currentPassword,
          new_password: newPassword,
        });
        router.replace('/(auth)/login?notice=password-changed' as Href);
      } catch (error) {
        if (error instanceof ApiError && error.fieldErrors.current_password) {
          setErrors((current) => ({
            ...current,
            currentPassword: 'validation.currentPasswordIncorrect',
          }));
        }
        setRequestError(t(getErrorTranslationKey(error)));
      }
    });
  };

  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => {
          if (router.canGoBack()) router.back();
          else router.replace('/(app)/settings' as Href);
        }}
        subtitle={t('password.changeSubtitle')}
        title={t('password.changeTitle')}
      />
      <ScrollView
        contentContainerStyle={{
          alignItems: 'center',
          padding: responsive.isPhone ? theme.spacing.md : theme.spacing.xl,
        }}
        keyboardShouldPersistTaps="handled"
      >
        <Card style={{ gap: theme.spacing.lg, maxWidth: 640, width: '100%' }}>
          {requestError ? <FeedbackBanner message={requestError} /> : null}
          <View style={{ gap: theme.spacing.md }}>
            <FormField
              autoComplete="current-password"
              error={errors.currentPassword ? t(errors.currentPassword) : undefined}
              label={t('password.currentPassword')}
              maxLength={128}
              onChangeText={setCurrentPassword}
              secureTextEntry
              value={currentPassword}
            />
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
          <Button
            label={pending ? t('password.changeLoading') : t('password.changeAction')}
            loading={pending}
            onPress={() => void submit()}
          />
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}
