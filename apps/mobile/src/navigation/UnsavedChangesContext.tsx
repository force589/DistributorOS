import { useFocusEffect, useNavigation, useRouter } from 'expo-router';
import { usePreventRemove } from 'expo-router/react-navigation';
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { BackHandler, Platform } from 'react-native';
import { useTranslation } from 'react-i18next';

import { ConfirmationDialog } from '@/components/ConfirmationDialog';

interface UnsavedChangesContextValue {
  guardNavigation: (action: () => void) => void;
  setFocusedScreenDirty: (dirty: boolean, prepareDiscard?: () => void) => void;
}

const UnsavedChangesContext = createContext<UnsavedChangesContextValue | null>(null);

export function UnsavedChangesProvider({ children }: PropsWithChildren) {
  const { t } = useTranslation();
  const [dirty, setDirty] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const prepareDiscard = useRef<(() => void) | null>(null);

  const guardNavigation = useCallback((action: () => void) => {
    if (!dirty) {
      action();
      return;
    }
    setPendingAction(() => action);
  }, [dirty]);

  const setFocusedScreenDirty = useCallback(
    (nextDirty: boolean, nextPrepareDiscard?: () => void) => {
      setDirty(nextDirty);
      prepareDiscard.current = nextDirty ? nextPrepareDiscard ?? null : null;
    },
    [],
  );

  const value = useMemo<UnsavedChangesContextValue>(() => ({
    guardNavigation,
    setFocusedScreenDirty,
  }), [guardNavigation, setFocusedScreenDirty]);

  return (
    <UnsavedChangesContext.Provider value={value}>
      {children}
      <ConfirmationDialog
        cancelLabel={t('unsavedChanges.keepEditing')}
        confirmLabel={t('unsavedChanges.discard')}
        loadingLabel={t('unsavedChanges.discard')}
        message={t('unsavedChanges.message')}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => {
          const action = pendingAction;
          prepareDiscard.current?.();
          setPendingAction(null);
          setDirty(false);
          setTimeout(() => action?.(), 0);
        }}
        title={t('unsavedChanges.title')}
        visible={pendingAction !== null}
      />
    </UnsavedChangesContext.Provider>
  );
}

export function useUnsavedChanges() {
  const context = useContext(UnsavedChangesContext);
  if (!context) throw new Error('useUnsavedChanges must be used inside UnsavedChangesProvider.');
  return context;
}

export function useDirtyFormGuard(dirty: boolean): (action: () => void) => void {
  const navigation = useNavigation();
  const router = useRouter();
  const { guardNavigation, setFocusedScreenDirty } = useUnsavedChanges();
  const [allowRemove, setAllowRemove] = useState(false);
  const effectiveDirty = dirty && !allowRemove;
  const prepareDiscard = useCallback(() => setAllowRemove(true), []);

  useEffect(() => {
    if (dirty) return;
    const reset = setTimeout(() => setAllowRemove(false), 0);
    return () => clearTimeout(reset);
  }, [dirty]);

  usePreventRemove(effectiveDirty, ({ data }) => {
    guardNavigation(() => navigation.dispatch(data.action));
  });

  useFocusEffect(useCallback(() => {
    setFocusedScreenDirty(effectiveDirty, prepareDiscard);
    navigation.setOptions({ gestureEnabled: !effectiveDirty });

    const back = Platform.OS === 'web'
      ? null
      : BackHandler.addEventListener('hardwareBackPress', () => {
          if (!effectiveDirty) return false;
          guardNavigation(() => router.back());
          return true;
        });
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!effectiveDirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    if (Platform.OS === 'web') window.addEventListener('beforeunload', beforeUnload);

    return () => {
      setFocusedScreenDirty(false);
      navigation.setOptions({ gestureEnabled: true });
      back?.remove();
      if (Platform.OS === 'web') window.removeEventListener('beforeunload', beforeUnload);
    };
  }, [effectiveDirty, guardNavigation, navigation, prepareDiscard, router, setFocusedScreenDirty]));

  return useCallback((action: () => void) => {
    setAllowRemove(true);
    setFocusedScreenDirty(false);
    setTimeout(action, 0);
  }, [setFocusedScreenDirty]);
}
