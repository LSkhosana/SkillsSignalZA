import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';

import { useReducedMotion } from '@/hooks/use-reduced-motion';
import { FontFamily, Palette } from '@/theme/tokens';

type StatusTone = 'info' | 'success' | 'warning' | 'danger';

const toneClass: Record<StatusTone, string> = {
  info: 'ss-status',
  success: 'ss-status ss-status-success',
  warning: 'ss-status ss-status-warning',
  danger: 'ss-status ss-status-danger',
};

const toneColor: Record<StatusTone, { borderColor: string; backgroundColor: string; titleColor: string }> = {
  info: { borderColor: Palette.ink, backgroundColor: Palette.surface, titleColor: Palette.ink },
  success: { borderColor: Palette.green, backgroundColor: Palette.paleGreen, titleColor: Palette.greenDark },
  warning: { borderColor: '#D58A1F', backgroundColor: Palette.warningSurface, titleColor: Palette.warning },
  danger: { borderColor: Palette.failureRule, backgroundColor: Palette.failureSurface, titleColor: Palette.failure },
};

export function StatusPanel({
  tone = 'info',
  title,
  message,
  testID,
}: {
  tone?: StatusTone;
  title: string;
  message?: string;
  testID?: string;
}) {
  const colors = toneColor[tone];

  return (
    <View
      accessibilityRole="alert"
      {...(Platform.OS === 'web' ? { className: toneClass[tone] } : {})}
      style={[styles.panel, { backgroundColor: colors.backgroundColor, borderLeftColor: colors.borderColor }]}
      testID={testID}
    >
      <Text style={[styles.panelTitle, { color: colors.titleColor }]}>{title}</Text>
      {message ? <Text style={styles.panelMessage}>{message}</Text> : null}
    </View>
  );
}

export function PageState({
  happened,
  meaning,
  consequence,
  action,
  tone = 'info',
  testID,
}: {
  happened: string;
  meaning: string;
  consequence: string;
  action?: ReactNode;
  tone?: StatusTone;
  testID?: string;
}) {
  return (
    <View style={styles.stack} testID={testID}>
      <View style={styles.answer}>
        <Text style={styles.eyebrow}>What happened</Text>
        <StatusPanel tone={tone} title={happened} />
      </View>
      <View style={styles.answer}>
        <Text style={styles.eyebrow}>What this means</Text>
        <Text style={styles.answerBody}>{meaning}</Text>
      </View>
      <View style={styles.answer}>
        <Text style={styles.eyebrow}>Charged or lost</Text>
        <Text style={styles.answerBody}>{consequence}</Text>
      </View>
      {action ? <View style={styles.action}>{action}</View> : null}
    </View>
  );
}

export function EmptyState({
  title,
  message,
  action,
  testID,
}: {
  title: string;
  message: string;
  action?: ReactNode;
  testID?: string;
}) {
  return (
    <View style={styles.stack} testID={testID}>
      <Text accessibilityRole="header" style={styles.emptyTitle}>
        {title}
      </Text>
      <Text style={styles.panelMessage}>{message}</Text>
      {action}
    </View>
  );
}

type ToastContextValue = {
  showToast: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  const [messages, setMessages] = useState<{ id: number; message: string }[]>([]);
  const timeouts = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timeouts.current;
    return () => {
      pending.forEach((timeout) => clearTimeout(timeout));
    };
  }, []);

  const showToast = useCallback(
    (message: string) => {
      const id = Date.now() + Math.random();
      setMessages((current) => [...current, { id, message }]);
      const timeout = setTimeout(() => {
        setMessages((current) => current.filter((item) => item.id !== id));
      }, reduced ? 5000 : 4200);
      timeouts.current.push(timeout);
    },
    [reduced],
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <View accessibilityLiveRegion="polite" pointerEvents="box-none" style={styles.toastRegion}>
        {messages.map((item) => (
          <View key={item.id} accessibilityRole="alert" style={styles.toast}>
            <Text style={styles.toastText}>{item.message}</Text>
          </View>
        ))}
      </View>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) {
    throw new Error('useToast must be used within ToastProvider.');
  }
  return value;
}

const styles = StyleSheet.create({
  panel: {
    gap: 8,
    borderLeftWidth: 4,
    borderRadius: 0,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  panelTitle: {
    fontFamily: FontFamily.sans,
    fontSize: 16,
    fontWeight: '800',
  },
  panelMessage: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    lineHeight: 22,
  },
  stack: {
    gap: 16,
    minWidth: 0,
  },
  answer: {
    gap: 6,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: Palette.divider,
  },
  eyebrow: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  answerBody: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
    lineHeight: 28,
  },
  action: {
    alignItems: 'flex-start',
  },
  emptyTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 36,
    lineHeight: 40,
    letterSpacing: -0.6,
  },
  toastRegion: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 16,
    gap: 8,
    zIndex: 50,
  },
  toast: {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    backgroundColor: Palette.ink,
    borderLeftWidth: 4,
    borderLeftColor: Palette.green,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  toastText: {
    color: Palette.surface,
    fontFamily: FontFamily.sans,
    fontSize: 14,
    lineHeight: 20,
  },
});
