import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import type { Summary } from '../lib/types';

const POLL_INTERVAL = 30_000;

export function useSummaries(date: string, scale?: string) {
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSummaries = useCallback(() => {
    if (!date) return;
    api.summaries
      .list(date, scale)
      .then(setSummaries)
      .catch(console.error);
  }, [date, scale]);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.summaries
      .list(date, scale)
      .then(setSummaries)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [date, scale]);

  useEffect(() => {
    if (!date) return;
    const isToday = date === todayStr();
    if (!isToday) return;

    const id = setInterval(fetchSummaries, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [date, fetchSummaries]);

  return { summaries, loading };
}
