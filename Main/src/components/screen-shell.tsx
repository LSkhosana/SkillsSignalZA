import type { ReactNode } from 'react';
import { Platform, View } from 'react-native';

import { PageShell } from '@/components/system/page-shell';
import { SectionHeader } from '@/components/system/section-header';

type ScreenShellProps = {
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  children: ReactNode;
  testID?: string;
  concealHeadingOnPrint?: boolean;
};

export function ScreenShell({
  title,
  subtitle,
  headerRight,
  children,
  testID,
  concealHeadingOnPrint = false,
}: ScreenShellProps) {
  return (
    <PageShell testID={testID}>
      <View {...(concealHeadingOnPrint && Platform.OS === 'web' ? { className: 'ss-no-print' } : {})}>
        <SectionHeader title={title} subtitle={subtitle} aside={headerRight} />
      </View>
      {children}
    </PageShell>
  );
}
