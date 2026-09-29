import { LegalDocument } from '@/components/legal-document';
import { SUPPORT_COPY } from '@/lib/legal-copy';

export default function SupportScreen() {
  return <LegalDocument copy={SUPPORT_COPY} testID="support-screen" />;
}
