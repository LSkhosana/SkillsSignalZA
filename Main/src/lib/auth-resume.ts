import { toHref } from '@/lib/href';
import { Routes } from '@/lib/routes';
import type { Href } from 'expo-router';

export type AuthResumeNext = 'payment' | 'report' | 'preview' | 'reports';

export function firstSearchParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

export function isAuthResumeNext(value: string | undefined): value is AuthResumeNext {
  return value === 'payment' || value === 'report' || value === 'preview' || value === 'reports';
}

export function authResumeParams(assessmentId?: string, next?: string): Record<string, string> {
  const params: Record<string, string> = {};
  if (assessmentId) {
    params.assessmentId = assessmentId;
  }
  if (isAuthResumeNext(next)) {
    params.next = next;
  }
  return params;
}

export function authResumeHref(assessmentId?: string, next?: string): Href {
  if (next === 'reports') {
    return Routes.reports;
  }
  if (!assessmentId) {
    return Routes.home;
  }
  if (next === 'report') {
    return toHref(`/assessment/${assessmentId}/report`);
  }
  if (next === 'preview') {
    return toHref(`/assessment/${assessmentId}/preview`);
  }
  return toHref(`/assessment/${assessmentId}/payment`);
}

export function authHref(
  pathname: '/sign-in' | '/sign-up' | '/forgot-password' | '/reset-password' | '/session-expired',
  assessmentId?: string,
  next?: string,
): Href {
  const params = authResumeParams(assessmentId, next);
  if (Object.keys(params).length === 0) {
    return pathname as Href;
  }
  return { pathname, params } as Href;
}
