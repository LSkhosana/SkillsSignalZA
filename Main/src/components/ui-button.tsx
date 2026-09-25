import { Button } from '@/components/system/button';

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
  return (
    <Button
      label={label}
      onPress={onPress}
      disabled={disabled}
      variant={variant}
      accessibilityHint={accessibilityHint}
      testID={testID}
    />
  );
}
