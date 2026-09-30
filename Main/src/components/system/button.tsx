import { useRouter, type Href } from 'expo-router';
import { Platform, Pressable, StyleSheet, Text } from 'react-native';

import { FontFamily, Layout, Palette } from '@/theme/tokens';

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

type ButtonProps = {
  label: string;
  onPress?: () => void;
  href?: Href;
  disabled?: boolean;
  busy?: boolean;
  variant?: ButtonVariant;
  accessibilityHint?: string;
  testID?: string;
};

const webClass: Record<ButtonVariant, string> = {
  primary: 'ss-primary',
  secondary: 'ss-secondary',
  ghost: 'ss-link-button',
};

export function Button({
  label,
  onPress,
  href,
  disabled = false,
  busy = false,
  variant = 'primary',
  accessibilityHint,
  testID,
}: ButtonProps) {
  const router = useRouter();
  const inactive = disabled || busy;

  const activate = () => {
    if (inactive) {
      return;
    }
    if (onPress) {
      onPress();
      return;
    }
    if (href) {
      router.push(href);
    }
  };

  if (Platform.OS === 'web') {
    return (
      <button
        className={webClass[variant]}
        type="button"
        disabled={inactive}
        aria-busy={busy || undefined}
        aria-label={label}
        onClick={activate}
        data-testid={testID}
      >
        {label}
        {variant === 'primary' ? <span aria-hidden="true"> →</span> : null}
      </button>
    );
  }

  const backgroundColor = variant === 'primary' ? (inactive ? '#CBD1CE' : Palette.green) : 'transparent';
  const borderColor = variant === 'ghost' ? 'transparent' : inactive ? '#CBD1CE' : variant === 'primary' ? Palette.green : Palette.ink;
  const color = variant === 'primary' ? (inactive ? '#5D625F' : Palette.onGreen) : inactive ? '#5D625F' : Palette.ink;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy }}
      disabled={inactive}
      onPress={activate}
      testID={testID}
      style={({ pressed }) => [
        styles.button,
        variant === 'ghost' ? styles.ghost : null,
        {
          backgroundColor,
          borderColor,
          opacity: inactive ? 0.48 : pressed ? 0.92 : 1,
        },
      ]}
    >
      <Text style={[styles.label, { color }]}>
        {label}
        {variant === 'primary' ? ' →' : ''}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignSelf: 'flex-start',
    minHeight: Layout.touch,
    minWidth: Layout.touch,
    maxWidth: '100%',
    borderWidth: 1,
    borderRadius: 0,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 17,
    paddingVertical: 11,
  },
  ghost: {
    borderWidth: 0,
    paddingHorizontal: 0,
  },
  label: {
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 0.1,
  },
});
