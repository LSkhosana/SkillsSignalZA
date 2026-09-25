import { Stack } from 'expo-router';

import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState } from '@/components/system/feedback';
import { Routes } from '@/lib/routes';

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'Not found', headerShown: false }} />
      <ScreenShell title="Screen not found" testID="not-found-screen">
        <PageState
          tone="warning"
          happened="This address is not part of SkillSignalZA."
          meaning="Nothing was opened, scored, or changed."
          consequence="Nothing was charged and no assessment was lost."
          action={<Button label="Go to start" href={Routes.home} />}
          testID="not-found-state"
        />
      </ScreenShell>
    </>
  );
}
