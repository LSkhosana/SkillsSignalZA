import { Pressable, StyleSheet, Text } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { Spacing } from '@/theme';

type UiButtonProps = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary';
  accessibilityHint?: string;
  testID?: string;
};

export function UiButton({
  label,
  onPress,
  disabled = false,
  variant = 'primary',
  accessibilityHint,
  testID,
}: UiButtonProps) {
  const theme = useTheme();
  const backgroundColor =
    variant === 'primary' ? (disabled ? theme.border : theme.accent) : theme.surface;
  const textColor = variant === 'primary' ? '#FFFFFF' : theme.accent;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor,
          borderColor: theme.accent,
          opacity: pressed && !disabled ? 0.85 : 1,
        },
      ]}
    >
      <Text style={[styles.label, { color: variant === 'primary' ? textColor : theme.accent }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 48,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  label: {
    fontSize: 16,
    fontWeight: '700',
  },
});
