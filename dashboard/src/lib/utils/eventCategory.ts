import type { AccountEvent } from '@/lib/api/types';

export type EventCategory = 'vehicles' | 'production' | 'armies' | 'officer' | 'conquest' | 'system';

export const EVENT_CATEGORIES: { value: EventCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'vehicles', label: 'Vehicles' },
  { value: 'production', label: 'Production' },
  { value: 'armies', label: 'Armies' },
  { value: 'officer', label: 'Officer' },
  { value: 'conquest', label: 'Conquest' },
  { value: 'system', label: 'System' },
];

// Built directly from the real event_type/detail.action values every
// backend endpoint actually writes (see app/api/*.py's repo.add_event
// calls and app/main.py's _SESSION_EVENT_TYPE) — nothing here is
// speculative. 'officer' has no matching action today (officer tasks are
// only ever observed from the login sync, never acted on by any endpoint)
// — its filter legitimately shows nothing rather than a fabricated entry.
const VEHICLE_ACTIONS = new Set(['farm', 'recall', 'recall_all', 'scout']);
const PRODUCTION_ACTIONS = new Set(['collect']);
const ARMY_ACTIONS = new Set(['army_groups_refresh', 'army_group_join', 'army_group_leave', 'mass_deploy_executed']);

export function classifyEvent(event: AccountEvent): EventCategory {
  const { event_type: eventType, detail } = event;
  if (eventType === 'conquest_guard_enabled' || eventType === 'conquest_guard_disabled') return 'conquest';
  if (eventType === 'action_requested' || eventType === 'action_failed' || eventType === 'mass_deploy_executed') {
    const action = typeof detail?.action === 'string' ? detail.action : eventType;
    if (VEHICLE_ACTIONS.has(action)) return 'vehicles';
    if (PRODUCTION_ACTIONS.has(action)) return 'production';
    if (ARMY_ACTIONS.has(action)) return 'armies';
    return 'system';
  }
  return 'system';
}
