import { useState, useCallback } from 'react';

interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Wraps any hey-api SDK call with loading / error state.
 *
 * Usage:
 *   const { data, isLoading, error, execute } = useApi(listMyUsersApiV1AdminUsersGet);
 *   await execute();          // no args
 *   await execute({ path: { user_id: '123' } });  // with args
 */
export function useApi<TArgs, TData>(
  apiFn: (args: TArgs) => Promise<{ data?: TData; error?: unknown }>
) {
  const [state, setState] = useState<ApiState<TData>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const execute = useCallback(
    async (args: TArgs): Promise<TData | null> => {
      setState((s) => ({ ...s, isLoading: true, error: null }));
      try {
        const result = await apiFn(args);
        if (result.error) {
          const msg = extractErrorMessage(result.error);
          setState({ data: null, isLoading: false, error: msg });
          return null;
        }
        setState({ data: result.data ?? null, isLoading: false, error: null });
        return result.data ?? null;
      } catch (err) {
        const msg = extractErrorMessage(err);
        setState({ data: null, isLoading: false, error: msg });
        return null;
      }
    },
    [apiFn]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}

export function extractErrorMessage(err: unknown): string {
  if (!err) return 'An unknown error occurred';
  if (typeof err === 'string') return err;
  if (typeof err === 'object') {
    const e = err as Record<string, unknown>;
    if (typeof e.detail === 'string') return e.detail;
    if (Array.isArray(e.detail)) {
      return (e.detail as Array<{ msg: string }>)
        .map((d) => d.msg)
        .join(', ');
    }
    if (typeof e.message === 'string') return e.message;
  }
  return 'An unknown error occurred';
}