import { useState, type ReactNode } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { FontFamily, Layout, Palette } from '@/theme/tokens';

export function InlineFieldError({ message, testID }: { message?: string; testID?: string }) {
  if (!message) {
    return null;
  }

  const body = (
    <Text accessibilityRole="alert" style={styles.error} testID={testID}>
      {message}
    </Text>
  );

  if (Platform.OS === 'web') {
    return <span className="ss-field-error">{message}</span>;
  }

  return body;
}

type TextFieldProps = {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  autoComplete?: 'email' | 'password' | 'off' | 'url';
  keyboardType?: 'default' | 'email-address' | 'url';
  secureTextEntry?: boolean;
  editable?: boolean;
  error?: string;
  hint?: string;
  testID?: string;
};

export function TextField({
  label,
  value,
  onChangeText,
  placeholder,
  autoCapitalize = 'none',
  autoComplete = 'off',
  keyboardType = 'default',
  secureTextEntry = false,
  editable = true,
  error,
  hint,
  testID,
}: TextFieldProps) {
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.field} {...(Platform.OS === 'web' ? { className: 'ss-field' } : {})}>
      <Text nativeID={`${testID ?? label}-label`} style={styles.label}>
        {label}
      </Text>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      <TextInput
        accessibilityLabel={label}
        accessibilityHint={error ?? hint}
        autoCapitalize={autoCapitalize}
        autoComplete={autoComplete}
        autoCorrect={false}
        editable={editable}
        keyboardType={keyboardType}
        onBlur={() => setFocused(false)}
        onChangeText={onChangeText}
        onFocus={() => setFocused(true)}
        placeholder={placeholder}
        placeholderTextColor={Palette.muted}
        secureTextEntry={secureTextEntry}
        style={[
          styles.input,
          focused ? styles.inputFocused : null,
          error ? styles.inputError : null,
          !editable ? styles.locked : null,
        ]}
        testID={testID}
        value={value}
      />
      <InlineFieldError message={error} testID={error && testID ? `${testID}-error` : undefined} />
    </View>
  );
}

type UrlFieldProps = Omit<TextFieldProps, 'keyboardType' | 'autoComplete' | 'autoCapitalize'>;

export function UrlField(props: UrlFieldProps) {
  return <TextField {...props} autoCapitalize="none" autoComplete="url" keyboardType="url" />;
}

type SelectOption<T extends string> = {
  value: T;
  label: string;
  description?: string;
};

export function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
  hint,
  error,
  disabled = false,
  testID,
}: {
  label: string;
  value: T;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  hint?: string;
  error?: string;
  disabled?: boolean;
  testID?: string;
}) {
  return (
    <View accessibilityRole="radiogroup" style={styles.field} testID={testID}>
      <Text style={styles.label}>{label}</Text>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="radio"
            accessibilityLabel={option.label}
            accessibilityState={{ selected, disabled }}
            disabled={disabled}
            onPress={() => {
              if (!disabled) {
                onChange(option.value);
              }
            }}
            style={[styles.option, selected ? styles.optionSelected : null, disabled ? styles.locked : null]}
            testID={testID ? `${testID}-${option.value}` : undefined}
          >
            <Text style={styles.optionLabel}>
              {selected ? 'Selected: ' : ''}
              {option.label}
            </Text>
            {option.description ? <Text style={styles.hint}>{option.description}</Text> : null}
          </Pressable>
        );
      })}
      <InlineFieldError message={error} />
    </View>
  );
}

export function UploadDropzone({
  label,
  hint,
  fileName,
  onPress,
  disabled = false,
  error,
  action,
  testID,
}: {
  label: string;
  hint?: string;
  fileName?: string | null;
  onPress: () => void;
  disabled?: boolean;
  error?: string;
  action?: ReactNode;
  testID?: string;
}) {
  return (
    <View style={styles.field}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint={hint}
        accessibilityState={{ disabled }}
        disabled={disabled}
        onPress={onPress}
        testID={testID}
        style={[styles.dropzone, fileName ? styles.optionSelected : null, disabled ? styles.locked : null]}
      >
        <Text style={styles.eyebrow}>File</Text>
        <Text style={styles.dropTitle}>{label}</Text>
        <Text style={styles.hint}>{fileName || hint}</Text>
      </Pressable>
      {action}
      <InlineFieldError message={error} />
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: 8,
    minWidth: 0,
  },
  label: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 12,
    fontWeight: '700',
  },
  hint: {
    color: Palette.muted,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    lineHeight: 18,
  },
  input: {
    minHeight: Layout.touch,
    borderWidth: 1,
    borderColor: Palette.divider,
    borderRadius: 0,
    backgroundColor: Palette.surface,
    color: Palette.ink,
    paddingHorizontal: 13,
    fontFamily: FontFamily.sans,
    fontSize: 16,
  },
  inputFocused: {
    borderColor: Palette.green,
  },
  inputError: {
    borderColor: Palette.failureRule,
    backgroundColor: Palette.failureSurface,
  },
  locked: {
    opacity: 0.6,
  },
  error: {
    color: Palette.failure,
    fontFamily: FontFamily.sans,
    fontSize: 13,
    lineHeight: 18,
  },
  option: {
    minHeight: Layout.touch,
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Palette.divider,
    borderRadius: 0,
    backgroundColor: Palette.surface,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 4,
  },
  optionSelected: {
    borderColor: Palette.green,
    backgroundColor: Palette.paleGreen,
  },
  optionLabel: {
    color: Palette.ink,
    fontFamily: FontFamily.sans,
    fontSize: 15,
    fontWeight: '700',
  },
  dropzone: {
    minHeight: 96,
    justifyContent: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: Palette.ink,
    borderRadius: 0,
    backgroundColor: Palette.surface,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  eyebrow: {
    color: Palette.green,
    fontFamily: FontFamily.sans,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  dropTitle: {
    color: Palette.ink,
    fontFamily: FontFamily.serif,
    fontSize: 22,
  },
});
