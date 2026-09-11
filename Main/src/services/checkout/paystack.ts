import * as WebBrowser from 'expo-web-browser';
import { Linking, Platform } from 'react-native';

export type CheckoutOpenResult = 'opened' | 'blocked' | 'returned' | 'failed';

export async function openPaystackCheckout(authorizationUrl: string): Promise<CheckoutOpenResult> {
  if (!authorizationUrl.startsWith('https://')) {
    return 'failed';
  }

  if (Platform.OS === 'web') {
    try {
      const opened = window.open(authorizationUrl, '_blank', 'noopener,noreferrer');
      return opened ? 'opened' : 'blocked';
    } catch {
      return 'blocked';
    }
  }

  try {
    await WebBrowser.openBrowserAsync(authorizationUrl);
    return 'returned';
  } catch {
    const canOpen = await Linking.canOpenURL(authorizationUrl);
    if (!canOpen) {
      return 'failed';
    }
    await Linking.openURL(authorizationUrl);
    return 'returned';
  }
}
