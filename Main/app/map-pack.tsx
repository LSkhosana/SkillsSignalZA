import { ScreenShell } from '@/components/screen-shell';
import { Button } from '@/components/system/button';
import { PageState } from '@/components/system/feedback';
import { Routes } from '@/lib/routes';

export default function MapPackScreen() {
  return (
    <ScreenShell
      title="Career Map Pack"
      subtitle="Market-informed lanes and project guidance for entry-level Software Engineering and Data Analytics."
      testID="map-pack-screen"
    >
      <PageState
        tone="info"
        happened="Career Map Pack checkout is not part of this release."
        meaning="You can read what the pack contains on the public landing page. Purchase and download are not available yet."
        consequence="Nothing was charged by opening this page."
        action={<Button label="Back to start" href={Routes.home} testID="map-pack-home" />}
        testID="map-pack-placeholder"
      />
    </ScreenShell>
  );
}
