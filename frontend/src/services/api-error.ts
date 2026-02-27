import axios, { type AxiosError } from 'axios';

export type ApiErrorKind =
  | 'validation'
  | 'conflict'
  | 'not_found'
  | 'rate_limit'
  | 'network'
  | 'server'
  | 'unknown';

export type ApiFieldError = {
  field: string;
  message: string;
};

type NipeApiErrorPayload = {
  kind: ApiErrorKind;
  message: string;
  status: number | null;
  detail: string;
  fieldErrors: ApiFieldError[];
  retryable: boolean;
  cause?: unknown;
};

export class NipeApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly detail: string;
  readonly fieldErrors: ApiFieldError[];
  readonly retryable: boolean;

  constructor(payload: NipeApiErrorPayload) {
    super(payload.message, payload.cause !== undefined ? { cause: payload.cause } : undefined);
    this.name = 'NipeApiError';
    this.kind = payload.kind;
    this.status = payload.status;
    this.detail = payload.detail;
    this.fieldErrors = payload.fieldErrors;
    this.retryable = payload.retryable;
  }
}

function normalizeFieldErrors(error: AxiosError): ApiFieldError[] {
  const fieldErrorsRaw = error.response?.data?.field_errors;
  if (!Array.isArray(fieldErrorsRaw)) {
    return [];
  }
  return fieldErrorsRaw
    .map((entry) => ({
      field: typeof entry?.field === 'string' ? entry.field.trim() : '',
      message: typeof entry?.message === 'string' ? entry.message.trim() : '',
    }))
    .filter((entry) => entry.field.length > 0 && entry.message.length > 0);
}

function summarizeFieldErrors(fieldErrors: ApiFieldError[]): string {
  return fieldErrors
    .slice(0, 4)
    .map((entry) => `${entry.field}: ${entry.message}`)
    .join(' | ');
}

function resolveDetail(error: AxiosError): string {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail.trim();
  }
  if (typeof error.response?.data === 'string' && error.response.data.trim().length > 0) {
    return error.response.data.trim();
  }
  if (typeof error.message === 'string' && error.message.trim().length > 0) {
    return error.message.trim();
  }
  return 'Request failed.';
}

function buildValidationMessage(detail: string, fieldErrors: ApiFieldError[]): string {
  if (fieldErrors.length === 0) {
    return detail.length > 0 ? detail : 'Validation failed.';
  }
  const prefix = detail.length > 0 ? detail : 'Validation failed.';
  return `${prefix} ${summarizeFieldErrors(fieldErrors)}`;
}

function buildCategorizedError({
  kind,
  status,
  detail,
  fieldErrors = [],
  retryable,
  cause,
}: {
  kind: ApiErrorKind;
  status: number | null;
  detail: string;
  fieldErrors?: ApiFieldError[];
  retryable: boolean;
  cause: unknown;
}): NipeApiError {
  let message = detail;
  if (kind === 'validation') {
    message = buildValidationMessage(detail, fieldErrors);
  } else if (kind === 'conflict' && message.length === 0) {
    message = 'Request conflicts with current resource state.';
  } else if (kind === 'not_found' && message.length === 0) {
    message = 'Requested resource was not found.';
  } else if (kind === 'rate_limit' && message.length === 0) {
    message = 'Rate limit reached. Please retry later.';
  } else if (kind === 'network' && message.length === 0) {
    message = 'Network error. Check backend availability and your connection.';
  } else if (kind === 'server' && message.length === 0) {
    message = 'Server error. Please retry.';
  } else if (kind === 'unknown' && message.length === 0) {
    message = 'Unknown request error';
  }

  return new NipeApiError({
    kind,
    message,
    status,
    detail,
    fieldErrors,
    retryable,
    cause,
  });
}

export function normalizeHttpError(error: unknown): NipeApiError {
  if (error instanceof NipeApiError) {
    return error;
  }

  if (axios.isAxiosError(error)) {
    if (error.response === undefined) {
      const detail =
        typeof error.message === 'string' && error.message.trim().length > 0
          ? error.message.trim()
          : 'Network error. Check backend availability and your connection.';
      return buildCategorizedError({
        kind: 'network',
        status: null,
        detail,
        retryable: true,
        cause: error,
      });
    }

    const status = typeof error.response.status === 'number' ? error.response.status : null;
    const detail = resolveDetail(error);
    const fieldErrors = normalizeFieldErrors(error);

    if (status === 400 || status === 422) {
      return buildCategorizedError({
        kind: 'validation',
        status,
        detail,
        fieldErrors,
        retryable: false,
        cause: error,
      });
    }
    if (status === 404) {
      return buildCategorizedError({
        kind: 'not_found',
        status,
        detail,
        retryable: false,
        cause: error,
      });
    }
    if (status === 409) {
      return buildCategorizedError({
        kind: 'conflict',
        status,
        detail,
        retryable: false,
        cause: error,
      });
    }
    if (status === 429) {
      return buildCategorizedError({
        kind: 'rate_limit',
        status,
        detail,
        retryable: true,
        cause: error,
      });
    }
    if (status !== null && status >= 500) {
      return buildCategorizedError({
        kind: 'server',
        status,
        detail,
        retryable: true,
        cause: error,
      });
    }

    return buildCategorizedError({
      kind: 'unknown',
      status,
      detail,
      retryable: false,
      cause: error,
    });
  }

  if (error instanceof Error) {
    const detail = error.message.trim().length > 0 ? error.message.trim() : 'Unknown request error';
    return buildCategorizedError({
      kind: 'unknown',
      status: null,
      detail,
      retryable: false,
      cause: error,
    });
  }

  return buildCategorizedError({
    kind: 'unknown',
    status: null,
    detail: 'Unknown request error',
    retryable: false,
    cause: error,
  });
}
