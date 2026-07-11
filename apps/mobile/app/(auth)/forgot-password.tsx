import { Link } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { useTheme } from '@/design/theme';
import { spacing } from '@/design/tokens';
import { AuthScreenLayout } from '@/features/auth/AuthScreenLayout';
import { useAuth } from '@/features/auth/AuthContext';
import { getErrorTranslationKey } from '@/features/auth/errorMessages';
import { validateEmail, type LoginValidationErrors } from '@/features/auth/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function ForgotPasswordScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<LoginValidationErrors>({});
  const [feedback, setFeedback] = useState<{ tone: 'error' | 'success'; message: string } | null>(null);
  const { pending, run } = useSingleFlightAction();

  const submit = async () => {
    const validationErrors = validateEmail(email);
    setErrors(validationErrors);
    setFeedback(null);
    if (validationErrors.email) return;
    await run(async () => {
      try {
        await forgotPassword({ email: email.trim() });
        setFeedback({ tone: 'success', message: t('password.forgotSuccess') });
      } catch (error) {
        setFeedback({ tone: 'error', message: t(getErrorTranslationKey(error)) });
      }
    });
  };

  return (
    <AuthScreenLayout subtitle={t('password.forgotSubtitle')} title={t('password.forgotTitle')}>
      {feedback ? <FeedbackBanner message={feedback.message} tone={feedback.tone} /> : null}
      <FormField
        autoCapitalize="none"
        autoComplete="email"
        error={errors.email ? t(errors.email) : undefined}
        keyboardType="email-address"
        label={t('login.emailLabel')}
        onChangeText={(value) => { setEmail(value); setErrors({}); setFeedback(null); }}
        placeholder={t('login.emailPlaceholder')}
        value={email}
      />
      <PrimaryButton
        label={t('password.forgotAction')}
        loading={pending}
        loadingLabel={t('password.forgotLoading')}
        onPress={() => void submit()}
      />
      <Link asChild href="/(auth)/login">
        <Pressable accessibilityRole="link" style={styles.linkButton}>
          <Text style={[styles.link, { color: theme.colors.primary }]}>{t('password.backToLogin')}</Text>
        </Pressable>
      </Link>
    </AuthScreenLayout>
  );
}

const styles = StyleSheet.create({
  link: { fontSize: 14, fontWeight: '700' },
  linkButton: { alignItems: 'center', justifyContent: 'center', minHeight: 48, padding: spacing.sm },
});
