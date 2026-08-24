import { type ReactNode, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  type TextProps,
  View,
  type ViewStyle,
} from 'react-native';

import { Icon } from '@/components/Icon';
import { appIcons, type AppIconName } from '@/design/icons';
import { useTheme } from '@/design/theme';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;

export function HeadingText({
  level = 2,
  ...props
}: TextProps & { level?: HeadingLevel }) {
  return (
    <Text
      accessibilityRole="header"
      {...({ 'aria-level': level } as { 'aria-level': HeadingLevel })}
      {...props}
    />
  );
}

export function Button({
  accessibilityLabel,
  label,
  onPress,
  loading = false,
  disabled = false,
  variant = 'primary',
  accessibilityHint,
  testID,
}: {
  accessibilityLabel?: string;
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: ButtonVariant;
  accessibilityHint?: string;
  testID?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  const unavailable = disabled || loading;
  const background =
    variant === 'primary'
      ? theme.colors.primary
      : variant === 'destructive'
        ? theme.colors.danger
        : variant === 'secondary'
          ? theme.colors.primarySubtle
          : 'transparent';
  const foreground =
    variant === 'primary' || variant === 'destructive'
      ? theme.colors.textInverse
      : theme.colors.primary;
  return (
    <Pressable
      accessibilityHint={accessibilityHint}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      accessibilityState={{ busy: loading, disabled: unavailable }}
      disabled={unavailable}
      hitSlop={4}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => ({
        alignItems: 'center',
        backgroundColor: unavailable ? theme.colors.disabled : background,
        borderColor: focused || variant === 'secondary' ? theme.colors.primary : 'transparent',
        borderRadius: theme.radii.md,
        borderWidth: 2,
        flexDirection: 'row',
        gap: theme.spacing.sm,
        justifyContent: 'center',
        minHeight: 48,
        opacity: pressed ? 0.82 : 1,
        paddingHorizontal: theme.spacing.lg,
        paddingVertical: theme.spacing.sm,
      })}
      testID={testID}
    >
      {loading ? <ActivityIndicator color={foreground} /> : null}
      <Text allowFontScaling style={[theme.typography.label, { color: foreground }]}>
        {label}
      </Text>
    </Pressable>
  );
}

export function Card({
  children,
  style,
}: {
  children: ReactNode;
  style?: ViewStyle | ViewStyle[];
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: theme.colors.surface,
          borderColor: theme.colors.border,
          borderRadius: theme.radii.lg,
          borderWidth: 1,
          padding: theme.spacing.lg,
        },
        theme.elevations.sm,
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function Divider() {
  const theme = useTheme();
  return <View style={{ backgroundColor: theme.colors.border, height: 1, width: '100%' }} />;
}

export function IconButton({
  accessibilityHint,
  accessibilityLabel,
  disabled = false,
  icon,
  onPress,
  size = 48,
  testID,
}: {
  accessibilityHint?: string;
  accessibilityLabel: string;
  disabled?: boolean;
  icon: AppIconName;
  onPress: () => void;
  size?: number;
  testID?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityHint={accessibilityHint}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      hitSlop={6}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => [
        {
          alignItems: 'center',
          backgroundColor: pressed ? theme.colors.primarySubtle : theme.colors.surfaceElevated,
          borderColor: focused ? theme.colors.primary : theme.colors.border,
          borderRadius: theme.radii.full,
          borderWidth: 1,
          height: Math.max(size, 44),
          justifyContent: 'center',
          minHeight: 44,
          minWidth: 44,
          opacity: disabled ? 0.56 : 1,
          width: Math.max(size, 44),
        },
        theme.elevations.md,
      ]}
      testID={testID}
    >
      <Icon color={theme.colors.primary} name={icon} size="lg" />
    </Pressable>
  );
}

export function SectionIcon({ icon }: { icon: AppIconName }) {
  const theme = useTheme();
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no"
      style={{
        alignItems: 'center',
        backgroundColor: theme.colors.primarySubtle,
        borderRadius: theme.radii.md,
        height: 40,
        justifyContent: 'center',
        width: 40,
      }}
    >
      <Icon color={theme.colors.primary} name={icon} size="lg" />
    </View>
  );
}

export function RadioListItem({
  label,
  description,
  selected,
  onPress,
  testID,
}: {
  label: string;
  description?: string;
  selected: boolean;
  onPress: () => void;
  testID?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      aria-checked={selected}
      aria-label={label}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => ({
        alignItems: 'center',
        backgroundColor: selected ? theme.colors.primarySubtle : 'transparent',
        borderColor: focused ? theme.colors.primary : 'transparent',
        borderRadius: theme.radii.md,
        borderWidth: 2,
        flexDirection: 'row',
        gap: theme.spacing.md,
        minHeight: 60,
        opacity: pressed ? 0.76 : 1,
        paddingHorizontal: theme.spacing.md,
        paddingVertical: theme.spacing.sm,
      })}
      testID={testID}
    >
      <View style={{ flex: 1, gap: theme.spacing.xs }}>
        <Text
          style={[
            theme.typography.body,
            { color: selected ? theme.colors.primary : theme.colors.text, fontWeight: '600' },
          ]}
        >
          {label}
        </Text>
        {description ? (
          <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
            {description}
          </Text>
        ) : null}
      </View>
      <View
        style={{
          alignItems: 'center',
          borderColor: selected ? theme.colors.primary : theme.colors.borderStrong,
          borderRadius: theme.radii.full,
          borderWidth: 2,
          height: 22,
          justifyContent: 'center',
          width: 22,
        }}
      >
        {selected ? (
          <View
            style={{
              backgroundColor: theme.colors.primary,
              borderRadius: theme.radii.full,
              height: 10,
              width: 10,
            }}
          />
        ) : null}
      </View>
    </Pressable>
  );
}

export function TextField({ label, error, onBlur, onFocus, ...props }: TextInputProps & {
  label: string;
  error?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ gap: theme.spacing.sm }}>
      <Text style={[theme.typography.label, { color: theme.colors.text }]}>{label}</Text>
      <TextInput
        accessibilityHint={error}
        accessibilityLabel={label}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        placeholderTextColor={theme.colors.textMuted}
        style={[
          theme.typography.body,
          {
            backgroundColor: theme.colors.surface,
            borderColor: error
              ? theme.colors.danger
              : focused
                ? theme.colors.primary
                : theme.colors.border,
            borderRadius: theme.radii.md,
            borderWidth: 1,
            color: theme.colors.text,
            minHeight: 48,
            paddingHorizontal: theme.spacing.md,
          },
        ]}
        {...props}
      />
      {error ? (
        <Text accessibilityLiveRegion="polite" style={[theme.typography.caption, { color: theme.colors.danger }]}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

export function SearchBar(props: Omit<TextInputProps, 'accessibilityRole'> & { label: string }) {
  return <TextField autoCapitalize="none" returnKeyType="search" {...props} />;
}

export function Dialog({
  visible,
  title,
  message,
  children,
  onDismiss,
}: {
  visible: boolean;
  title: string;
  message?: string;
  children: ReactNode;
  onDismiss: () => void;
}) {
  const theme = useTheme();
  return (
    <Modal
      accessibilityViewIsModal
      animationType="fade"
      onRequestClose={onDismiss}
      transparent
      visible={visible}
    >
      <View
        accessibilityViewIsModal
        {...({ 'aria-modal': true, role: 'dialog' } as {
          'aria-modal': boolean;
          role: 'dialog';
        })}
        style={{
          alignItems: 'center',
          backgroundColor: theme.colors.overlay,
          flex: 1,
          justifyContent: 'center',
          padding: theme.spacing.lg,
        }}
      >
        <Card style={{ gap: theme.spacing.md, maxWidth: 480, width: '100%' }}>
          <HeadingText level={1} style={[theme.typography.heading, { color: theme.colors.text }]}>
            {title}
          </HeadingText>
          {message ? <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>{message}</Text> : null}
          {children}
        </Card>
      </View>
    </Modal>
  );
}

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' }) {
  const theme = useTheme();
  const colors =
    tone === 'success'
      ? [theme.colors.successBackground, theme.colors.success]
      : tone === 'warning'
        ? [theme.colors.warningBackground, theme.colors.warning]
        : tone === 'danger'
          ? [theme.colors.dangerBackground, theme.colors.danger]
          : [theme.colors.surfaceSubtle, theme.colors.textMuted];
  return (
    <View style={{ alignSelf: 'flex-start', backgroundColor: colors[0], borderRadius: theme.radii.full, paddingHorizontal: theme.spacing.sm, paddingVertical: theme.spacing.xs }}>
      <Text style={[theme.typography.caption, { color: colors[1], fontWeight: '700' }]}>{label}</Text>
    </View>
  );
}

export function Chip({ label, selected = false, onPress }: { label: string; selected?: boolean; onPress: () => void }) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={{
        backgroundColor: selected ? theme.colors.primarySubtle : theme.colors.surface,
        borderColor: selected || focused ? theme.colors.primary : theme.colors.border,
        borderRadius: theme.radii.full,
        borderWidth: 1,
        minHeight: 44,
        justifyContent: 'center',
        paddingHorizontal: theme.spacing.md,
      }}
    >
      <Text style={[theme.typography.label, { color: selected ? theme.colors.primary : theme.colors.text }]}>{label}</Text>
    </Pressable>
  );
}

function StateLayout({ title, message, children }: { title: string; message: string; children?: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ alignItems: 'center', gap: theme.spacing.md, justifyContent: 'center', minHeight: 220, padding: theme.spacing.xl }}>
      <HeadingText level={1} style={[theme.typography.heading, { color: theme.colors.text, textAlign: 'center' }]}>{title}</HeadingText>
      <Text style={[theme.typography.body, { color: theme.colors.textMuted, textAlign: 'center' }]}>{message}</Text>
      {children}
    </View>
  );
}

export function EmptyState(props: { title: string; message: string; actionLabel?: string; onAction?: () => void }) {
  return <StateLayout title={props.title} message={props.message}>{props.actionLabel && props.onAction ? <Button label={props.actionLabel} onPress={props.onAction} /> : null}</StateLayout>;
}

export function ErrorState(props: { title: string; message: string; retryLabel?: string; onRetry?: () => void }) {
  return <StateLayout title={props.title} message={props.message}>{props.retryLabel && props.onRetry ? <Button label={props.retryLabel} onPress={props.onRetry} variant="secondary" /> : null}</StateLayout>;
}

export function LoadingState({ title, message }: { title: string; message: string }) {
  const theme = useTheme();
  return <StateLayout title={title} message={message}><ActivityIndicator color={theme.colors.primary} size="large" /></StateLayout>;
}

export function SkeletonLoader({
  accessibilityLabel,
  hidden = false,
  width = '100%',
  height = 18,
}: {
  accessibilityLabel?: string;
  hidden?: boolean;
  width?: ViewStyle['width'];
  height?: number;
}) {
  const theme = useTheme();
  return (
    <View
      accessibilityElementsHidden={hidden}
      accessibilityLabel={accessibilityLabel}
      importantForAccessibility={hidden ? 'no-hide-descendants' : undefined}
      {...(hidden ? { 'aria-hidden': true } as { 'aria-hidden': boolean } : {})}
      style={{ backgroundColor: theme.colors.surfaceSubtle, borderRadius: theme.radii.sm, height, width }}
    />
  );
}

export function SkeletonRow({
  lines = 3,
}: {
  lines?: number;
}) {
  const theme = useTheme();
  return (
    <Card style={{ gap: theme.spacing.sm, padding: theme.spacing.md }}>
      <SkeletonLoader hidden height={18} width="48%" />
      {Array.from({ length: lines - 1 }).map((_, index) => (
        <SkeletonLoader
          hidden
          height={14}
          key={index}
          width={index % 2 === 0 ? '72%' : '36%'}
        />
      ))}
    </Card>
  );
}

export function SkeletonCardGrid({
  cards = 6,
  columns = 2,
}: {
  cards?: number;
  columns?: number;
}) {
  const theme = useTheme();
  const width = columns >= 4 ? '23.5%' : columns === 3 ? '31%' : columns === 2 ? '47.5%' : '100%';
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing.md }}>
      {Array.from({ length: cards }).map((_, index) => (
        <Card key={index} style={{ gap: theme.spacing.sm, minHeight: 112, padding: theme.spacing.md, width }}>
          <SkeletonLoader hidden height={16} width="64%" />
          <SkeletonLoader hidden height={28} width="42%" />
        </Card>
      ))}
    </View>
  );
}

export function ListSkeleton({
  accessibilityLabel,
  rows = 5,
}: {
  accessibilityLabel: string;
  rows?: number;
}) {
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="progressbar"
      style={{ gap: theme.spacing.md, padding: theme.spacing.md }}
    >
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonRow key={index} lines={index % 2 === 0 ? 3 : 2} />
      ))}
    </View>
  );
}

export function SectionHeader({ title, actionLabel, onAction, headingLevel = 2 }: { title: string; actionLabel?: string; onAction?: () => void; headingLevel?: HeadingLevel }) {
  const theme = useTheme();
  return (
    <View style={{ alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', minHeight: 44 }}>
      <HeadingText level={headingLevel} style={[theme.typography.heading, { color: theme.colors.text }]}>{title}</HeadingText>
      {actionLabel && onAction ? <Button label={actionLabel} onPress={onAction} variant="ghost" /> : null}
    </View>
  );
}

export function FilterChipGroup({
  label,
  onSelect,
  options,
  selected,
  testIDPrefix,
}: {
  label: string;
  onSelect: (value: string) => void;
  options: { value: string; label: string }[];
  selected: string;
  testIDPrefix?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState<string | null>(null);
  return (
    <View style={{ gap: theme.spacing.xs }}>
      <Text style={[theme.typography.caption, { color: theme.colors.textMuted, fontWeight: '700' }]}>
        {label}
      </Text>
      <ScrollView
        contentContainerStyle={{ gap: theme.spacing.sm }}
        horizontal
        keyboardShouldPersistTaps="handled"
        showsHorizontalScrollIndicator={false}
      >
        {options.map((option) => {
          const active = selected === option.value;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              key={option.value}
              onBlur={() => setFocused((current) => (current === option.value ? null : current))}
              onFocus={() => setFocused(option.value)}
              onPress={() => onSelect(option.value)}
              style={({ pressed }) => ({
                backgroundColor: active ? theme.colors.primary : pressed ? theme.colors.primarySubtle : theme.colors.surface,
                borderColor: focused === option.value || active ? theme.colors.primary : theme.colors.border,
                borderRadius: theme.radii.full,
                borderWidth: 1,
                justifyContent: 'center',
                minHeight: 44,
                opacity: pressed ? 0.82 : 1,
                paddingHorizontal: theme.spacing.md,
                paddingVertical: theme.spacing.xs,
              })}
              testID={testIDPrefix ? `${testIDPrefix}-${option.value}` : undefined}
            >
              <Text
                style={[
                  theme.typography.label,
                  {
                    color: active ? theme.colors.textInverse : theme.colors.text,
                    fontSize: 13,
                    fontWeight: '700',
                  },
                ]}
              >
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

export function ListItem({
  title,
  subtitle,
  trailing,
  onPress,
  accessibilityHint,
}: {
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  onPress?: () => void;
  accessibilityHint?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  const content = (
    <View style={{ alignItems: 'center', flexDirection: 'row', gap: theme.spacing.md, minHeight: 56, paddingVertical: theme.spacing.sm }}>
      <View style={{ flex: 1, gap: theme.spacing.xs }}>
        <Text style={[theme.typography.body, { color: theme.colors.text, fontWeight: '600' }]}>{title}</Text>
        {subtitle ? <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>{subtitle}</Text> : null}
      </View>
      {trailing}
    </View>
  );
  return onPress ? (
    <Pressable
      accessibilityLabel={subtitle ? `${title}. ${subtitle}` : title}
      accessibilityHint={accessibilityHint}
      accessibilityRole="button"
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={{
        borderColor: focused ? theme.colors.primary : 'transparent',
        borderRadius: theme.radii.md,
        borderWidth: 2,
        minHeight: 56,
      }}
    >
      {content}
    </Pressable>
  ) : content;
}

export function ActionCard({
  icon,
  title,
  description,
  onPress,
  style,
  testID,
}: {
  icon: AppIconName;
  title: string;
  description: string;
  onPress: () => void;
  style?: ViewStyle;
  testID?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityHint={description}
      accessibilityLabel={title}
      accessibilityRole="button"
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => [
        {
          backgroundColor: pressed ? theme.colors.primarySubtle : theme.colors.surface,
          borderColor: focused ? theme.colors.primary : theme.colors.border,
          borderRadius: theme.radii.lg,
          borderWidth: focused ? 2 : 1,
          gap: theme.spacing.sm,
          justifyContent: 'space-between',
          minHeight: 132,
          padding: theme.spacing.md,
          transform: [{ scale: pressed ? 0.98 : 1 }],
        },
        theme.elevations.sm,
        style,
      ]}
      testID={testID}
    >
      <Icon color={theme.colors.primary} name={icon} size="xl" />
      <View style={{ gap: theme.spacing.xs }}>
        <Text style={[theme.typography.heading, { color: theme.colors.text }]}>{title}</Text>
        <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
          {description}
        </Text>
      </View>
    </Pressable>
  );
}

export function NavigationListItem({
  icon,
  title,
  subtitle,
  onPress,
  testID,
}: {
  icon: AppIconName;
  title: string;
  subtitle?: string;
  onPress: () => void;
  testID?: string;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityHint={subtitle}
      accessibilityLabel={title}
      accessibilityRole="button"
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => ({
        alignItems: 'center',
        backgroundColor: focused || pressed ? theme.colors.primarySubtle : 'transparent',
        borderColor: focused ? theme.colors.primary : 'transparent',
        borderRadius: theme.radii.md,
        borderWidth: 2,
        flexDirection: 'row',
        gap: theme.spacing.md,
        minHeight: 72,
        paddingHorizontal: theme.spacing.md,
        paddingVertical: theme.spacing.sm,
      })}
      testID={testID}
    >
      <Icon color={theme.colors.primary} name={icon} size="lg" />
      <View style={{ flex: 1, gap: theme.spacing.xs }}>
        <Text style={[theme.typography.body, { color: theme.colors.text, fontWeight: '700' }]}>
          {title}
        </Text>
        {subtitle ? (
          <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      <Icon color={theme.colors.textMuted} name={appIcons.chevronRight} size="md" />
    </Pressable>
  );
}

export function TopBar({ title, subtitle, leading, trailing }: { title: string; subtitle?: string; leading?: ReactNode; trailing?: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ alignItems: 'center', backgroundColor: theme.colors.surface, borderBottomColor: theme.colors.border, borderBottomWidth: 1, flexDirection: 'row', gap: theme.spacing.md, minHeight: 64, paddingHorizontal: theme.spacing.lg, paddingVertical: theme.spacing.sm }}>
      {leading}
      <View style={{ flex: 1 }}>
        <HeadingText level={1} style={[theme.typography.heading, { color: theme.colors.text }]}>{title}</HeadingText>
        {subtitle ? <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>{subtitle}</Text> : null}
      </View>
      {trailing}
    </View>
  );
}

export function BottomNavigation({
  items,
  bottomInset = 0,
}: {
  items: { key: string; icon: AppIconName; label: string; selected?: boolean; onPress: () => void }[];
  bottomInset?: number;
}) {
  const theme = useTheme();
  return (
    <View
      style={{
        backgroundColor: theme.colors.surface,
        borderTopColor: theme.colors.border,
        borderTopWidth: 1,
        paddingBottom: bottomInset,
        width: '100%',
      }}
    >
      <View
        accessibilityRole="tablist"
        style={{ alignSelf: 'center', flexDirection: 'row', minHeight: 66, maxWidth: 760, width: '100%' }}
      >
        {items.map((item) => (
          <BottomNavigationItem
            icon={item.icon}
            key={item.key}
            label={item.label}
            onPress={item.onPress}
            selected={item.selected}
          />
        ))}
      </View>
    </View>
  );
}

function BottomNavigationItem({
  icon,
  label,
  selected = false,
  onPress,
}: {
  icon: AppIconName;
  label: string;
  selected?: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="tab"
      accessibilityState={{ selected }}
      aria-label={label}
      aria-selected={selected}
      onBlur={() => setFocused(false)}
      onFocus={() => setFocused(true)}
      onPress={onPress}
      style={({ pressed }) => ({
        alignItems: 'center',
        backgroundColor: focused || pressed ? theme.colors.primarySubtle : 'transparent',
        borderColor: focused ? theme.colors.primary : 'transparent',
        borderRadius: theme.radii.sm,
        borderWidth: 2,
        flex: 1,
        gap: 2,
        justifyContent: 'center',
        minHeight: 58,
        minWidth: 64,
        paddingHorizontal: theme.spacing.xs,
      })}
    >
      <Icon
        color={selected ? theme.colors.primary : theme.colors.textMuted}
        name={icon}
        size="lg"
      />
      <Text
        numberOfLines={1}
        style={[
          theme.typography.caption,
          {
            color: selected ? theme.colors.primary : theme.colors.textMuted,
            fontWeight: selected ? '700' : '500',
          },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export function FAB({ label, onPress }: { label: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable accessibilityLabel={label} accessibilityRole="button" onPress={onPress} style={({ pressed }) => [{ alignItems: 'center', backgroundColor: theme.colors.primary, borderRadius: theme.radii.full, bottom: theme.spacing.lg, justifyContent: 'center', minHeight: 56, minWidth: 56, paddingHorizontal: theme.spacing.lg, position: 'absolute', right: theme.spacing.lg, opacity: pressed ? 0.84 : 1 }, theme.elevations.lg]}>
      <Text style={[theme.typography.label, { color: theme.colors.textInverse }]}>{label}</Text>
    </Pressable>
  );
}

export function StatusTag({ label, status }: { label: string; status: 'success' | 'warning' | 'danger' | 'neutral' }) {
  return <Badge label={label} tone={status} />;
}

export { Icon, StyleSheet };
export type { AppIconName };
