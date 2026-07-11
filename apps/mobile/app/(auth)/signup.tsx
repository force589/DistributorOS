import { Link } from 'expo-router';
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
  getSignupValidationErrors,
} from '@/features/auth/errorMessages';
import { validateSignup, type SignupValidationErrors } from '@/features/auth/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function SignupScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { signup } = useAuth();
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<SignupValidationErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();

  const submit = async () => {
    const validationErrors = validateSignup(businessName, email, password);
    setErrors(validationErrors);
    setRequestError(null);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }
    await run(async () => {
      try {
        await signup({ business_name: businessName.trim(), email: email.trim(), password });
      } catch (error) {
        const serverErrors = getSignupValidationErrors(error);
        if (Object.keys(serverErrors).length > 0) setErrors(serverErrors);
        else setRequestError(t(getErrorTranslationKey(error)));
      }
    });
  };

  return (
    <AuthScreenLayout subtitle={t('signup.subtitle')} title={t('signup.title')}>
      {requestError ? <FeedbackBanner message={requestError} /> : null}
      <View style={styles.fields}>
        <FormField
          autoCapitalize="words"
          error={errors.businessName ? t(errors.businessName) : undefined}
          label={t('signup.businessNameLabel')}
          maxLength={120}
          onChangeText={setBusinessName}
          placeholder={t('signup.businessNamePlaceholder')}
          value={businessName}
        />
        <FormField
          autoCapitalize="none"
          autoComplete="email"
          error={errors.email ? t(errors.email) : undefined}
          keyboardType="email-address"
          label={t('signup.emailLabel')}
          onChangeText={setEmail}
          placeholder={t('signup.emailPlaceholder')}
          value={email}
        />
        <FormField
          autoComplete="new-password"
          error={errors.password ? t(errors.password) : undefined}
          label={t('signup.passwordLabel')}
          maxLength={128}
          onChangeText={setPassword}
          placeholder={t('signup.passwordPlaceholder')}
          secureTextEntry
          value={password}
        />
      </View>
      <PrimaryButton
        label={t('signup.action')}
        loading={pending}
        loadingLabel={t('signup.loading')}
        onPress={() => void submit()}
      />
      <View style={styles.footer}>
        <Text style={[styles.footerText, { color: theme.colors.textMuted }]}>{t('signup.hasAccount')}</Text>
        <Link asChild href="/(auth)/login">
          <Pressable accessibilityRole="link">
            <Text style={[styles.link, { color: theme.colors.primary }]}>{t('signup.signIn')}</Text>
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
});
