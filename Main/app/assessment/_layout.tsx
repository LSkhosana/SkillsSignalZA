import { Stack } from 'expo-router';

export default function AssessmentLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="new" options={{ title: 'New assessment' }} />
      <Stack.Screen name="[assessmentId]/preview" options={{ title: 'Preview' }} />
      <Stack.Screen name="[assessmentId]/payment" options={{ title: 'Payment' }} />
      <Stack.Screen name="[assessmentId]/report" options={{ title: 'Readiness Report' }} />
    </Stack>
  );
}
