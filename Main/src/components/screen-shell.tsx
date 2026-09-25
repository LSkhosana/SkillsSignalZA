import type { ReactNode } from 'react';

import { PageShell } from '@/components/system/page-shell';
import { SectionHeader } from '@/components/system/section-header';

type ScreenShellProps = {
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  children: ReactNode;
  testID?: string;
};

export function ScreenShell({ title, subtitle, headerRight, children, testID }: ScreenShellProps) {
  return (
    <PageShell testID={testID}>
      <SectionHeader title={title} subtitle={subtitle} aside={headerRight} />
      {children}
    </PageShell>
  );
}
