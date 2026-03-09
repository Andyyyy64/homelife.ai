import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { todayStr } from '../lib/date';
import { useToast } from './useToast';
import type { Event } from '../lib/types';

const POLL_INTERVAL = 30_000;

export function useEvents(date: string) {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const { t } = useTranslation();

  const fetchEvents = useCallback(() => {
    if (!date) return;
    api.events
      .list(date)
      .then(setEvents)
      .catch(() => {
        addToast(t('errors.fetchEvents'), 'error');
      });
  }, [date, addToast, t]);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    api.events
      .list(date)
      .then(setEvents)
      .catch(() => {
        addToast(t('errors.fetchEvents'), 'error');
      })
      .finally(() => setLoading(false));
  }, [date, addToast, t]);

  useEffect(() => {
    if (!date) return;
    const isToday = date === todayStr();
    if (!isToday) return;

    const id = setInterval(fetchEvents, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [date, fetchEvents]);

  return { events, loading };
}
