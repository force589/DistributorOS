import {
  ApiError,
  type CurrencyCode,
  type LanguageCode,
  type ThemePreference,
} from '@distributoros/api-client';
import { useQueryClient } from '@tanstack/react-query';
import { type Href, useRouter } from 'expo-router';
import { Fragment, type ReactNode, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FormField } from '@/components/FormField';
import { ScreenHeader } from '@/components/ScreenHeader';
import { appIcons, type AppIconName } from '@/design/icons';
import { useResponsiveLayout } from '@/design/responsive';
import { usePreferences, useTheme } from '@/design/theme';
import {
  Button,
  Card,
  Divider,
  HeadingText,
  ListItem,
  RadioListItem,
  SectionIcon,
} from '@/design-system';
import { useAuth } from '@/features/auth/AuthContext';
import { getErrorTranslationKey } from '@/features/auth/errorMessages';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

const currencies: CurrencyCode[] = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'SGD', 'MYR'];
const languages: LanguageCode[] = ['en', 'ml'];
const themes: ThemePreference[] = ['light', 'dark', 'system'];

export default function SettingsScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const responsive = useResponsiveLayout();
  const theme = useTheme();
  const { user, updateBusinessSettings, logout } = useAuth();
  const preferences = usePreferences();
  const { clearPreviewPreferences, updatePreferences } = preferences;
  const [businessName, setBusinessName] = useState(user?.business.business_name ?? '');
  const [currency, setCurrency] = useState<CurrencyCode>(preferences.currency);
  const [language, setLanguage] = useState<LanguageCode>(preferences.language);
  const [themePreference, setThemePreference] = useState<ThemePreference>(
    preferences.themePreference,
  );
  const [timezone, setTimezone] = useState(preferences.timezone);
  const [nameError, setNameError] = useState<string | undefined>();
  const [timezoneError, setTimezoneError] = useState<string | undefined>();
  const [feedback, setFeedback] = useState<{
    tone: 'error' | 'success';
    message: string;
  } | null>(null);
  const [confirmingLogout, setConfirmingLogout] = useState(false);
  const { pending: saving, run: runSave } = useSingleFlightAction();
  const { pending: signingOut, run: runLogout } = useSingleFlightAction();

  const normalizedName = businessName.trim();
  const hasChanges =
    normalizedName !== user?.business.business_name ||
    currency !== user?.business.currency ||
    language !== user?.business.language ||
    themePreference !== user?.business.theme ||
    timezone.trim() !== user?.business.timezone;
  useDirtyFormGuard(hasChanges);

  const chooseCurrency = (value: CurrencyCode) => {
    setCurrency(value);
    updatePreferences({ currency: value });
    setFeedback(null);
  };

  const chooseLanguage = (value: LanguageCode) => {
    setLanguage(value);
    updatePreferences({ language: value });
    setFeedback(null);
  };

  const chooseTheme = (value: ThemePreference) => {
    setThemePreference(value);
    updatePreferences({ themePreference: value });
    setFeedback(null);
  };

  const save = async () => {
    if (!normalizedName) {
      setNameError(t('settings.validation.businessNameRequired'));
      return;
    }
    if (normalizedName.length > 120) {
      setNameError(t('settings.validation.businessNameTooLong'));
      return;
    }
    const normalizedTimezone = timezone.trim();
    if (!normalizedTimezone) {
      setTimezoneError(t('settings.validation.timezoneRequired'));
      return;
    }
    setNameError(undefined);
    setTimezoneError(undefined);
    setFeedback(null);
    await runSave(async () => {
      try {
        const updated = await updateBusinessSettings({
          business_name: normalizedName,
          currency,
          language,
          theme: themePreference,
          timezone: normalizedTimezone,
        });
        updatePreferences({
          currency: updated.currency,
          language: updated.language,
          themePreference: updated.theme,
          timezone: updated.timezone,
        });
        clearPreviewPreferences();
        await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
        setFeedback({ tone: 'success', message: t('settings.success') });
      } catch (error) {
        if (error instanceof ApiError && error.fieldErrors.timezone) {
          setTimezoneError(t('settings.validation.timezoneInvalid'));
        }
        setFeedback({ tone: 'error', message: t(getErrorTranslationKey(error)) });
      }
    });
  };

  const confirmLogout = async () => {
    await runLogout(async () => {
      setFeedback(null);
      try {
        await logout();
        setConfirmingLogout(false);
      } catch (error) {
        setConfirmingLogout(false);
        setFeedback({ tone: 'error', message: t(getErrorTranslationKey(error)) });
      }
    });
  };

  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => {
          if (router.canGoBack()) router.back();
          else router.replace('/' as Href);
        }}
        subtitle={t('settings.subtitle')}
        title={t('settings.title')}
      />
      <ScrollView
        contentContainerStyle={{
          alignItems: 'center',
          paddingBottom: theme.spacing.xxxl,
          paddingHorizontal: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
          paddingTop: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
        }}
        keyboardShouldPersistTaps="handled"
      >
        <View
          style={{
            gap: theme.spacing.lg,
            maxWidth: responsive.isDesktop ? 980 : 820,
            width: '100%',
          }}
        >
          {feedback ? <FeedbackBanner message={feedback.message} tone={feedback.tone} /> : null}

          <SettingsSection
            description={t('settings.businessDescription')}
            icon={appIcons.business}
            title={t('settings.businessSection')}
          >
          <FormField
            error={nameError}
            label={t('settings.businessName')}
            maxLength={120}
            onChangeText={(value) => {
              setBusinessName(value);
              setNameError(undefined);
              setFeedback(null);
            }}
            placeholder={t('settings.businessNamePlaceholder')}
            value={businessName}
          />
          <Divider />
          <FormField
            autoCapitalize="none"
            autoCorrect={false}
            error={timezoneError}
            label={t('settings.timezone')}
            maxLength={64}
            onChangeText={(value) => {
              setTimezone(value);
              setTimezoneError(undefined);
              setFeedback(null);
            }}
            placeholder={t('settings.timezonePlaceholder')}
            value={timezone}
          />
          <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
            {t('settings.timezoneHelp')}
          </Text>
          <Divider />
          <View style={{ gap: theme.spacing.xs }}>
            <Text style={[theme.typography.label, { color: theme.colors.text }]}>
              {t('settings.currency')}
            </Text>
            <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
              {t('settings.currencyHelp')}
            </Text>
          </View>
          <RadioOptions>
            {currencies.map((code) => (
              <RadioListItem
                key={code}
                label={code}
                onPress={() => chooseCurrency(code)}
                selected={currency === code}
                testID={`currency-${code}`}
              />
            ))}
          </RadioOptions>
          </SettingsSection>

          <SettingsSection
            description={t('settings.appearanceDescription')}
            icon={appIcons.appearance}
            title={t('settings.appearanceSection')}
          >
          <RadioOptions>
            {themes.map((value) => (
              <RadioListItem
                description={t(`settings.themeOptions.${value}`)}
                key={value}
                label={t(`settings.${value}`)}
                onPress={() => chooseTheme(value)}
                selected={themePreference === value}
                testID={`theme-${value}`}
              />
            ))}
          </RadioOptions>
          </SettingsSection>

          <SettingsSection
            description={t('settings.languageHelp')}
            icon={appIcons.language}
            title={t('settings.languageSection')}
          >
          <RadioOptions>
            {languages.map((code) => (
              <RadioListItem
                description={t(`settings.languageOptions.${code}`)}
                key={code}
                label={t(code === 'en' ? 'settings.english' : 'settings.malayalam')}
                onPress={() => chooseLanguage(code)}
                selected={language === code}
                testID={`language-${code}`}
              />
            ))}
          </RadioOptions>
          </SettingsSection>

          <SettingsSection
            description={t('settings.accountDescription')}
            icon={appIcons.account}
            title={t('settings.accountSection')}
          >
          <ListItem subtitle={user?.email ?? ''} title={t('settings.accountEmail')} />
          <Divider />
          <ListItem
            subtitle={user?.business.business_name ?? ''}
            title={t('settings.accountBusiness')}
          />
          <Divider />
          <ListItem
            accessibilityHint={t('settings.changePasswordHint')}
            onPress={() => router.push('/(app)/change-password' as Href)}
            subtitle={t('settings.changePasswordHint')}
            title={t('settings.changePassword')}
          />
          <Divider />
          <Button
            label={t('home.signOut')}
            onPress={() => setConfirmingLogout(true)}
            variant="destructive"
          />
          </SettingsSection>

          <Button
            disabled={!hasChanges}
            label={saving ? t('settings.saving') : t('settings.save')}
            loading={saving}
            onPress={() => void save()}
            testID="save-settings"
          />
        </View>
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={t('logout.confirm')}
        loading={signingOut}
        loadingLabel={t('logout.loading')}
        message={t('logout.message')}
        onCancel={() => setConfirmingLogout(false)}
        onConfirm={() => void confirmLogout()}
        title={t('logout.title')}
        visible={confirmingLogout}
      />
    </SafeAreaView>
  );
}

function SettingsSection({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description: string;
  icon: AppIconName;
  children: ReactNode;
}) {
  const theme = useTheme();
  return (
    <Card style={{ overflow: 'hidden', padding: 0 }}>
      <View
        style={{
          alignItems: 'center',
          flexDirection: 'row',
          gap: theme.spacing.md,
          padding: theme.spacing.lg,
        }}
      >
        <SectionIcon icon={icon} />
        <View style={{ flex: 1, gap: theme.spacing.xs }}>
          <HeadingText
            level={2}
            style={[theme.typography.heading, { color: theme.colors.text }]}
          >
            {title}
          </HeadingText>
          <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
            {description}
          </Text>
        </View>
      </View>
      <Divider />
      <View style={{ gap: theme.spacing.md, padding: theme.spacing.lg }}>{children}</View>
    </Card>
  );
}

function RadioOptions({ children }: { children: ReactNode[] }) {
  const options = children.filter(Boolean);
  return (
    <View>
      {options.map((option, index) => (
        <Fragment key={index}>
          {option}
          {index < options.length - 1 ? <Divider /> : null}
        </Fragment>
      ))}
    </View>
  );
}
