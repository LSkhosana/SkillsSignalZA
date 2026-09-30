import type { ReactNode } from 'react';
import { Platform, View } from 'react-native';

type RevealProps = {
  children: ReactNode;
  delay?: 0 | 1 | 2 | 3;
};

export function Reveal({ children, delay = 0 }: RevealProps) {
  if (Platform.OS !== 'web') {
    return <View>{children}</View>;
  }

  return (
    <div className="ss-reveal" data-delay={delay === 0 ? undefined : String(delay)}>
      {children}
    </div>
  );
}
