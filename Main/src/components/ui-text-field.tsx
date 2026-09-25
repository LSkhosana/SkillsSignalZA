import { TextField } from '@/components/system/fields';

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

export function UiTextField(props: UiTextFieldProps) {
  return <TextField {...props} />;
}
