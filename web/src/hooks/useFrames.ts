import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import type { Frame } from '../lib/types';

const POLL_INTERVAL = 30_000; // 30 seconds

export function useFrames(date: string) {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFrames = useCallback(() => {
    if (!date) return;
    api.frames
      .list(date)
      .then(setFrames)
      .catch(console.error);
  }, [date]);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.frames
      .list(date)
      .then(setFrames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [date]);

  // Poll for new data
  useEffect(() => {
    if (!date) return;
    const isToday = date === todayStr();
    if (!isToday) return;

    const id = setInterval(fetchFrames, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [date, fetchFrames]);

  return { frames, loading };
}
