import { StyleSheet, Text, TextInput, View } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { Spacing } from '@/theme';

type UiTextFieldProps = {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  autoComplete?: 'email' | 'password' | 'off' | 'url';
  keyboardType?: 'default' | 'email-address' | 'url';
  secureTextEntry?: boolean;
  editable?: boolean;
  testID?: string;
};

export function UiTextField({
  label,
  value,
  onChangeText,
  placeholder,
  autoCapitalize = 'none',
  autoComplete = 'off',
  keyboardType = 'default',
  secureTextEntry = false,
  editable = true,
  testID,
}: UiTextFieldProps) {
  const theme = useTheme();

  return (
    <View style={styles.field}>
      <Text nativeID={`${testID ?? label}-label`} style={[styles.label, { color: theme.text }]}>
        {label}
      </Text>
      <TextInput
        accessibilityLabel={label}
        autoCapitalize={autoCapitalize}
        autoComplete={autoComplete}
        autoCorrect={false}
        editable={editable}
        keyboardType={keyboardType}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={theme.muted}
        secureTextEntry={secureTextEntry}
        style={[
          styles.input,
          {
            color: theme.text,
            borderColor: theme.border,
            backgroundColor: theme.background,
          },
        ]}
        testID={testID}
        value={value}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: Spacing.sm,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: Spacing.md,
    fontSize: 16,
  },
});
