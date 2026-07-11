import { Link, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FormField } from '@/components/FormField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { useTheme } from '@/design/theme';
import { spacing } from '@/design/tokens';
import { AuthScreenLayout } from '@/features/auth/AuthScreenLayout';
import { useAuth } from '@/features/auth/AuthContext';
import {
  getErrorTranslationKey,
  getLoginValidationErrors,
} from '@/features/auth/errorMessages';
import { validateLogin, type LoginValidationErrors } from '@/features/auth/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function LoginScreen() {
  const { t } = useTranslation();
  const params = useLocalSearchParams<{ notice?: string }>();
  const theme = useTheme();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<LoginValidationErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();

  const submit = async () => {
    const validationErrors = validateLogin(email, password);
    setErrors(validationErrors);
    setRequestError(null);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }
    await run(async () => {
      try {
        await login({ email: email.trim(), password });
      } catch (error) {
        const serverErrors = getLoginValidationErrors(error);
        if (Object.keys(serverErrors).length > 0) setErrors(serverErrors);
        else setRequestError(t(getErrorTranslationKey(error)));
      }
    });
  };

  return (
    <AuthScreenLayout subtitle={t('login.subtitle')} title={t('login.title')}>
      {params.notice ? <FeedbackBanner message={t('login.passwordChanged')} tone="success" /> : null}
      {requestError ? <FeedbackBanner message={requestError} /> : null}
      <View style={styles.fields}>
        <FormField
          autoCapitalize="none"
          autoComplete="email"
          error={errors.email ? t(errors.email) : undefined}
          keyboardType="email-address"
          label={t('login.emailLabel')}
          onChangeText={setEmail}
          placeholder={t('login.emailPlaceholder')}
          value={email}
        />
        <FormField
          autoComplete="current-password"
          error={errors.password ? t(errors.password) : undefined}
          label={t('login.passwordLabel')}
          maxLength={128}
          onChangeText={setPassword}
          placeholder={t('login.passwordPlaceholder')}
          secureTextEntry
          value={password}
        />
      </View>
      <PrimaryButton
        label={t('login.action')}
        loading={pending}
        loadingLabel={t('login.loading')}
        onPress={() => void submit()}
      />
      <Link asChild href="/(auth)/forgot-password">
        <Pressable accessibilityRole="link" style={styles.centeredLink}>
          <Text style={[styles.link, { color: theme.colors.primary }]}>
            {t('login.forgotPassword')}
          </Text>
        </Pressable>
      </Link>
      <View style={styles.footer}>
        <Text style={[styles.footerText, { color: theme.colors.textMuted }]}>{t('login.noAccount')}</Text>
        <Link asChild href="/(auth)/signup">
          <Pressable accessibilityRole="link">
            <Text style={[styles.link, { color: theme.colors.primary }]}>{t('login.createAccount')}</Text>
          </Pressable>
        </Link>
      </View>
    </AuthScreenLayout>
  );
}

const styles = StyleSheet.create({
  fields: {
    gap: spacing.md,
  },
  footer: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    justifyContent: 'center',
  },
  footerText: {
    fontSize: 14,
  },
  link: {
    fontSize: 14,
    fontWeight: '700',
  },
  centeredLink: {
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
});
