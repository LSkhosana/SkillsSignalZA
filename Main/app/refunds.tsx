import { LegalDocument } from '@/components/legal-document';
import { REFUNDS_COPY } from '@/lib/legal-copy';

export default function RefundsScreen() {
  return <LegalDocument copy={REFUNDS_COPY} testID="refunds-screen" />;
}
