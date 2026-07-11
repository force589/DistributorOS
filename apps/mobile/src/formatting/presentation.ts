import type { CurrencyCode, LanguageCode } from '@distributoros/api-client';

let activeCurrency: CurrencyCode = 'INR';
let activeLanguage: LanguageCode = 'en';
let activeTimezone = 'Asia/Kolkata';

export function setPresentationPreferences(
  currency: CurrencyCode,
  language: LanguageCode,
  timezone = 'Asia/Kolkata',
): void {
  activeCurrency = currency;
  activeLanguage = language;
  activeTimezone = timezone;
}

export function getActiveCurrency(): CurrencyCode {
  return activeCurrency;
}

export function getActiveTimezone(): string {
  return activeTimezone;
}

export function localeForLanguage(language: LanguageCode | string): string {
  return language === 'ml' ? 'ml-IN' : 'en-IN';
}

export function formatCurrency(
  value: string | number | null | undefined,
  currency: CurrencyCode | string = activeCurrency,
  language: LanguageCode | string = activeLanguage,
): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat(localeForLanguage(language), {
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: 'currency',
  }).format(Number.isFinite(amount) ? amount : 0);
}

export function formatNumber(
  value: string | number | null | undefined,
  language: LanguageCode | string = activeLanguage,
  maximumFractionDigits = 3,
): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat(localeForLanguage(language), {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export function formatLocalizedDate(
  value: string | null | undefined,
  language: LanguageCode | string = activeLanguage,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' },
): string {
  if (!value) return '-';
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = new Date(dateOnly ? `${value}T00:00:00Z` : value);
  return new Intl.DateTimeFormat(localeForLanguage(language), {
    ...options,
    timeZone: dateOnly ? 'UTC' : activeTimezone,
  }).format(date);
}

export function businessDateIso(value = new Date(), timezone = activeTimezone): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    day: '2-digit',
    month: '2-digit',
    timeZone: timezone,
    year: 'numeric',
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((candidate) => candidate.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}
