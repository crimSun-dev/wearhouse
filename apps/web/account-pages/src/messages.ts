import type {ErrorCode} from '@wearhouse/contracts';

import {ApiFailure} from './api.ts';

const MESSAGES: Partial<Record<ErrorCode, string>> = {
  UNAUTHENTICATED: 'Your session ended. Please sign in again.',
  ACCOUNT_SUSPENDED: 'This account is suspended.',
  REAUTHENTICATION_REQUIRED: 'For safety, sign in again right before deleting your account.',
  HANDLE_REQUIRED: 'Choose a handle first.',
  HANDLE_UNAVAILABLE: 'That handle is taken or reserved. Try another one.',
  HANDLE_CHANGE_TOO_SOON: 'You can change your handle once every 7 days.',
  ALREADY_FRIENDS: 'You are already friends.',
  FRIEND_LIMIT_REACHED: 'Friend limit reached (1000).',
  PENDING_LIMIT_REACHED: 'You have too many pending requests. Cancel some first.',
  BLOCK_LIMIT_REACHED: 'Block limit reached (1000).',
  REQUEST_NOT_PENDING: 'That request is no longer pending.',
  RATE_LIMITED: 'Too many attempts. Please wait and try again.',
  NOT_FOUND: 'Not found.',
  VALIDATION_FAILED: 'Please check the highlighted fields.',
  SERVICE_UNAVAILABLE: 'Wearhouse is temporarily unavailable. Try again shortly.',
};

export function describe(err: unknown): string {
  if (err instanceof ApiFailure) {
    let text = MESSAGES[err.code as ErrorCode] ?? err.message;
    if (err.code === 'VALIDATION_FAILED' && err.fieldErrors.length) {
      text += ' ' + err.fieldErrors.map(f => f.message).join(' ');
    }
    if (err.retryAfter && (err.code === 'RATE_LIMITED' || err.code === 'HANDLE_CHANGE_TOO_SOON')) {
      const hours = Math.ceil(err.retryAfter / 3600);
      text += hours > 1 ? ` (in about ${hours} hours)` : ` (in about ${Math.ceil(err.retryAfter / 60)} minutes)`;
    }
    return `${text} [${err.code}]`;
  }
  return err instanceof Error ? err.message : 'Something went wrong.';
}
