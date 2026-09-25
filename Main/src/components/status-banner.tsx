import { StatusPanel } from '@/components/system/feedback';

type StatusBannerProps = {
  tone?: 'info' | 'danger' | 'success';
  title: string;
  message?: string;
  testID?: string;
};

export function StatusBanner({ tone = 'info', title, message, testID }: StatusBannerProps) {
  return <StatusPanel tone={tone} title={title} message={message} testID={testID} />;
}
