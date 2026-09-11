"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "./api";

interface Result<T> { key: string; data?: T; error?: ApiError }

/**
 * Fetch `path` and track loading/error state. Pass `null` to skip. Previous data is kept while a
 * reload is in flight so tables do not flash empty.
 */
export function useApi<T>(path: string | null) {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  const key = path ? `${path}#${nonce}` : null;

  useEffect(() => {
    if (!key || !path) return;
    let alive = true;
    api<T>(path).then(
      (data) => alive && setResult({ key, data }),
      (error: ApiError) => alive && setResult({ key, error }),
    );
    return () => {
      alive = false;
    };
  }, [key, path]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const fresh = result?.key === key;
  return {
    data: result?.data,
    error: fresh ? result?.error : undefined,
    loading: key !== null && !fresh,
    reload,
  };
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}
