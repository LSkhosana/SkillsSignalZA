import { Colors, type ColorSchemeName } from '@/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

export function useTheme() {
  const scheme = useColorScheme();
  const theme: ColorSchemeName = scheme === 'dark' ? 'dark' : 'light';

  return Colors[theme];
}
