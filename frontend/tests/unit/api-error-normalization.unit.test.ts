import { describe, expect, it } from 'vitest';

import { NipeApiError, normalizeHttpError } from '@/services/api-error';

function axiosLikeError(payload: {
  status?: number;
  data?: unknown;
  message?: string;
}): unknown {
  return {
    isAxiosError: true,
    message: payload.message ?? 'Request failed',
    response:
      payload.status !== undefined
        ? {
            status: payload.status,
            data: payload.data,
          }
        : undefined,
  };
}

describe('normalizeHttpError', () => {
  it('classifies validation errors and preserves field-level details', () => {
    const parsed = normalizeHttpError(
      axiosLikeError({
        status: 422,
        data: {
          detail: 'Validation failed.',
          field_errors: [
            { field: 'title', message: 'is required' },
            { field: 'mode', message: 'is invalid' },
          ],
        },
      }),
    );

    expect(parsed).toBeInstanceOf(NipeApiError);
    expect(parsed.kind).toBe('validation');
    expect(parsed.status).toBe(422);
    expect(parsed.retryable).toBe(false);
    expect(parsed.fieldErrors).toEqual([
      { field: 'title', message: 'is required' },
      { field: 'mode', message: 'is invalid' },
    ]);
    expect(parsed.message).toContain('title: is required');
    expect(parsed.message).toContain('mode: is invalid');
  });

  it('classifies conflict errors', () => {
    const parsed = normalizeHttpError(
      axiosLikeError({
        status: 409,
        data: { detail: 'Project is archived and cannot be modified.' },
      }),
    );

    expect(parsed.kind).toBe('conflict');
    expect(parsed.status).toBe(409);
    expect(parsed.retryable).toBe(false);
    expect(parsed.message).toContain('Project is archived');
  });

  it('classifies not-found errors', () => {
    const parsed = normalizeHttpError(
      axiosLikeError({
        status: 404,
        data: { detail: 'Project not found.' },
      }),
    );

    expect(parsed.kind).toBe('not_found');
    expect(parsed.status).toBe(404);
    expect(parsed.retryable).toBe(false);
  });

  it('classifies rate-limit errors as retryable', () => {
    const parsed = normalizeHttpError(
      axiosLikeError({
        status: 429,
        data: { detail: 'Rate limit exceeded.' },
      }),
    );

    expect(parsed.kind).toBe('rate_limit');
    expect(parsed.status).toBe(429);
    expect(parsed.retryable).toBe(true);
  });

  it('classifies network errors when no response exists', () => {
    const parsed = normalizeHttpError(
      axiosLikeError({
        message: 'Network Error',
      }),
    );

    expect(parsed.kind).toBe('network');
    expect(parsed.status).toBeNull();
    expect(parsed.retryable).toBe(true);
  });

  it('classifies plain errors as unknown', () => {
    const parsed = normalizeHttpError(new Error('Something unexpected happened.'));

    expect(parsed.kind).toBe('unknown');
    expect(parsed.status).toBeNull();
    expect(parsed.retryable).toBe(false);
    expect(parsed.message).toContain('Something unexpected happened.');
  });
});
