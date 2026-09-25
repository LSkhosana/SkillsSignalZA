import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';

import { AppFrame } from '@/components/system/app-frame';
import { Providers } from '@/components/providers';
import { Palette } from '@/theme/tokens';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  useEffect(() => {
    void SplashScreen.hideAsync();
  }, []);

  return (
    <Providers>
      <AppFrame>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: Palette.paper },
          }}
        >
          <Stack.Screen name="index" options={{ title: 'SkillSignalZA', headerShown: false }} />
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
          <Stack.Screen name="(app)" options={{ headerShown: false }} />
          <Stack.Screen name="assessment" options={{ headerShown: false }} />
          <Stack.Screen name="+not-found" options={{ title: 'Not found', headerShown: false }} />
        </Stack>
      </AppFrame>
    </Providers>
  );
}
