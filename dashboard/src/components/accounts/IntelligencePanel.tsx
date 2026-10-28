'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { getLocatedBase, getProfile, joinArmyGroup, leaveArmyGroup, locateBases, refreshArmyGroups, refreshProfile } from '@/lib/api/intel';
import { useArmies, useArmyGroups, useMapObjects, useSkins } from '@/lib/hooks/useIntel';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { VehiclesSection } from '@/components/accounts/VehiclesSection';
import type { MainbasePosition, ProfileInfo } from '@/lib/api/types';

const inputClass =
  'w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50';

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <details className="group border-b border-border py-3 last:border-0" open>
      <summary className="cursor-pointer list-none">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}

function EmptyRow({ children }: { children: React.ReactNode }) {
  return <p className="py-2 text-xs text-muted-foreground">{children}</p>;
}

function ArmiesSection({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { armies, isLoading } = useArmies(accountId, connected);
  if (!connected) return <EmptyRow>Connect the account to see armies.</EmptyRow>;
  if (isLoading && armies.length === 0) return <EmptyRow>Loading…</EmptyRow>;
  if (armies.length === 0) return <EmptyRow>No army data yet — use Refresh.</EmptyRow>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="pb-1 pr-3">Slot</th>
            <th className="pb-1 pr-3">Equipped</th>
            <th className="pb-1 pr-3">Reserves</th>
            <th className="pb-1">AG</th>
          </tr>
        </thead>
        <tbody>
          {armies.map((a) => (
            <tr key={a.army_id} className="border-t border-border">
              <td className="py-1 pr-3 text-foreground">{a.army_id}</td>
              <td className="py-1 pr-3 text-foreground">{a.equipment_id > 0 ? 'Yes' : 'Empty'}</td>
              <td className="py-1 pr-3 text-foreground">{a.reserves}</td>
              <td className="py-1 text-foreground">{a.group_unique_id || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArmyGroupsSection({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { armyGroups, isLoading, refresh } = useArmyGroups(accountId, connected);
  // Same SWR key as ArmiesSection's own useArmies call below, so this shares
  // its cache rather than double-fetching — needed here to know which AG (if
  // any) this account's own armies are actually in, which is what decides
  // whether a row should offer "Join" or show it's already joined. A live
  // test showed a join succeed server-side (the AG's army_count went up)
  // while this row kept showing "Join" forever, because nothing here ever
  // checked real membership — it just always rendered the same button.
  const { armies, refresh: refreshArmies } = useArmies(accountId, connected);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [armyIds, setArmyIds] = useState('auto');
  const [leaveArmyId, setLeaveArmyId] = useState('');

  async function handleRefresh() {
    setError(null);
    try {
      await refreshArmyGroups(accountId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Refresh failed.');
    }
  }

  async function handleJoin(agId: number) {
    setPending(true);
    setError(null);
    try {
      await joinArmyGroup(accountId, agId, { army_ids: armyIds || 'auto' });
      await Promise.all([refresh(), refreshArmies()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Join failed.');
    } finally {
      setPending(false);
    }
  }

  async function handleLeave() {
    if (!leaveArmyId) return;
    setPending(true);
    setError(null);
    try {
      await leaveArmyGroup(accountId, Number(leaveArmyId));
      await Promise.all([refresh(), refreshArmies()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Leave failed.');
    } finally {
      setPending(false);
    }
  }

  if (!connected) return <EmptyRow>Connect the account to manage Army Groups.</EmptyRow>;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={handleRefresh}>Refresh AG list</Button>
        <input
          className={`${inputClass} w-32`}
          placeholder="Army slots"
          value={armyIds}
          onChange={(e) => setArmyIds(e.target.value)}
          aria-label="Army slots to join with"
        />
        <input
          className={`${inputClass} w-24`}
          placeholder="Army ID"
          value={leaveArmyId}
          onChange={(e) => setLeaveArmyId(e.target.value)}
          aria-label="Army slot to leave with"
        />
        <Button size="sm" variant="outline" disabled={!leaveArmyId || pending} onClick={handleLeave}>Leave AG</Button>
      </div>
      {isLoading && armyGroups.length === 0 && <EmptyRow>Loading…</EmptyRow>}
      {armyGroups.length === 0 && !isLoading && <EmptyRow>No AGs loaded — refresh.</EmptyRow>}
      {armyGroups.map((g) => {
        const memberArmyIds = armies.filter((a) => a.group_unique_id === g.unique_id).map((a) => a.army_id);
        const isMember = memberArmyIds.length > 0;
        return (
          <div key={g.unique_id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-xs">
            <div>
              <span className="font-medium text-foreground">AG {g.unique_id}</span>{' '}
              <span className="text-muted-foreground">
                type {g.group_type} · {g.army_count}/{g.max_num || '?'} armies · by {g.creator_name || g.creator_uid}
              </span>
            </div>
            {isMember ? (
              <span className="text-muted-foreground" title={`Joined with slot ${memberArmyIds.join(', ')} — use Leave AG above to leave`}>
                Joined (slot {memberArmyIds.join(', ')})
              </span>
            ) : (
              <Button size="sm" variant="secondary" disabled={pending} onClick={() => handleJoin(g.unique_id)}>Join</Button>
            )}
          </div>
        );
      })}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

function ProfileSection({ accountId, allowed }: { accountId: string; allowed: boolean }) {
  const [uid, setUid] = useState('');
  const [profile, setProfile] = useState<ProfileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleLookup() {
    if (!uid) return;
    setPending(true);
    setError(null);
    setProfile(null);
    try {
      await refreshProfile(accountId, Number(uid));
      await new Promise((resolve) => setTimeout(resolve, 800));
      const result = await getProfile(accountId, Number(uid));
      setProfile(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Profile lookup failed.');
    } finally {
      setPending(false);
    }
  }

  if (!allowed) {
    return <EmptyRow>Player Scout is restricted. A site administrator must grant access to this account.</EmptyRow>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <input className={`${inputClass} w-32`} placeholder="Player UID" value={uid} onChange={(e) => setUid(e.target.value)} aria-label="Player UID" />
        <Button size="sm" variant="secondary" loading={pending} disabled={!uid} onClick={handleLookup}>Look up</Button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      {profile && (
        <div className="rounded-lg border border-border px-3 py-2 text-xs text-foreground">
          <p className="font-medium">{profile.name} (UID {profile.uid})</p>
          <p className="text-muted-foreground">
            Power {profile.power} · Guild {profile.guild_name || '—'} · Skin points {profile.skin_point}
          </p>
        </div>
      )}
    </div>
  );
}

function SkinsSection({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { skins, isLoading } = useSkins(accountId, connected);
  const categories = Object.keys(skins);
  if (!connected) return <EmptyRow>Connect the account to see skins.</EmptyRow>;
  if (isLoading && categories.length === 0) return <EmptyRow>Loading…</EmptyRow>;
  if (categories.length === 0) return <EmptyRow>No skin data yet — use Refresh.</EmptyRow>;
  return (
    <div className="space-y-2">
      {categories.map((category) => (
        <div key={category}>
          <p className="text-xs font-medium text-foreground">{category.replace(/_/g, ' ')}</p>
          <p className="text-xs text-muted-foreground">{skins[category].length} item(s)</p>
        </div>
      ))}
    </div>
  );
}

function MapSection({ accountId, connected, canPlayerScout }: { accountId: string; connected: boolean; canPlayerScout: boolean }) {
  const { mapObjects, isLoading } = useMapObjects(accountId, connected);
  const [locateUid, setLocateUid] = useState('');
  const [position, setPosition] = useState<MainbasePosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const mainbases = mapObjects.filter((o) => o.is_mainbase);

  async function handleLocate() {
    setPending(true);
    setError(null);
    setPosition(null);
    try {
      await locateBases(accountId, locateUid ? Number(locateUid) : undefined);
      if (locateUid) {
        await new Promise((resolve) => setTimeout(resolve, 800));
        setPosition(await getLocatedBase(accountId, Number(locateUid)));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Locate failed.');
    } finally {
      setPending(false);
    }
  }

  if (!connected) return <EmptyRow>Connect the account to see the map.</EmptyRow>;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {canPlayerScout && (
          <input
            className={`${inputClass} w-32`}
            placeholder="Player UID"
            value={locateUid}
            onChange={(e) => setLocateUid(e.target.value)}
            aria-label="Player UID to locate"
          />
        )}
        <Button size="sm" variant="secondary" loading={pending} onClick={handleLocate}>
          {canPlayerScout ? 'Locate player / scan nearby' : 'Refresh nearby bases'}
        </Button>
      </div>
      {!canPlayerScout && (
        <p className="text-xs text-muted-foreground">Exact player locating is restricted to approved Player Scout users.</p>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
      {position && (
        <p className="text-xs text-foreground">
          Player {position.player_id} main base at ({position.x}, {position.y})
        </p>
      )}
      {isLoading && mainbases.length === 0 && <EmptyRow>Loading…</EmptyRow>}
      <p className="text-xs text-muted-foreground">{mainbases.length} known main base(s) cached from map scans.</p>
    </div>
  );
}

/** Section 22's "INTELLIGENCE" card: Vehicles, Armies, Army Groups, Profile,
 * Skins, Map — all reading data WarpathConnection already collects, plus
 * the Army Group join/leave and locate-bases mutations (real protocol,
 * verified against the vendored schema — see service/app/api/intel.py). */
export function IntelligencePanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { user } = useAuthSession();
  const canPlayerScout = Boolean(user?.role === 'admin' || user?.player_scout_access);

  return (
    <Card>
      <CardHeader title="Intelligence" description="Vehicles, armies, Army Groups, profile lookup, skins, and map data." />
      <CardContent>
        <Section title="Vehicles" description="Farm trucks and their current state.">
          <VehiclesSection accountId={accountId} connected={connected} />
        </Section>
        <Section title="Armies" description="Equipped army slots and their Army Group assignment.">
          <ArmiesSection accountId={accountId} connected={connected} />
        </Section>
        <Section title="Army Groups" description="Alliance AGs — join or leave with a specific army slot.">
          <ArmyGroupsSection accountId={accountId} connected={connected} />
        </Section>
        <Section title="Player Scout" description="Privileged player profile lookup by UID.">
          <ProfileSection accountId={accountId} allowed={canPlayerScout} />
        </Section>
        <Section title="Skins" description="Collected skin categories (view only).">
          <SkinsSection accountId={accountId} connected={connected} />
        </Section>
        <Section title="Map" description="Cached map objects; exact player locate requires Player Scout access.">
          <MapSection accountId={accountId} connected={connected} canPlayerScout={canPlayerScout} />
        </Section>
      </CardContent>
    </Card>
  );
}
