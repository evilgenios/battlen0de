"""Conservative farm/collection correlation within one game connection.

Only an echoed request sequence AND matching entity can confirm an action.
The schema exposes msg_seq_id; its live echo behavior remains an integration
validation gate. Missing/unmatched replies never imply success. Ambiguous
sends retain ownership until a matching late reply or a fresh connection.
"""
from collections import deque
from dataclasses import dataclass, field
import threading
import time
import uuid

from .protobuf import up_pb2


class ActionBusy(RuntimeError):
    pass


@dataclass(eq=False)
class Request:
    kind: str
    entity: int = 0
    target: int = 0
    seq: int | None = None
    status: str = 'pending'
    reply: dict = field(default_factory=dict)
    releasable: dict = field(default_factory=dict)
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    started_monotonic: float = field(default_factory=time.monotonic)
    wait_reason: str | None = None


class ReplyActions:
    def __init__(self, connection):
        self.connection = connection
        self.condition = threading.Condition(threading.RLock())
        self.farm_lock = threading.Lock()
        self.requests = {}
        self.collections = {}
        self.vehicles = {}
        self.search = None
        self.closed = False
        self.snapshot_seq = 0
        self.observation_id = str(uuid.uuid4())
        self.tracking_started_at = time.time()
        self.recent = deque(maxlen=50)
        self.history_dropped = 0

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def _send(self, ticket, message):
        def before_send(seq):
            with self.condition:
                if self.closed or seq in self.requests or len(self.requests) >= 1024:
                    raise ActionBusy('reply tracking unavailable; operator reconciliation required')
                ticket.seq = seq
                self.requests[seq] = ticket
                if ticket.kind == 'vehicles':
                    ticket.releasable = {vid: t for vid, t in self.vehicles.items() if t.status == 'confirmed'}
        try:
            self.connection.send_message(message, before_send=before_send)
        except Exception:
            # Once sendall may have run, a partial socket write is ambiguous.
            # Do not release the truck/building or echo a secret-bearing error.
            with self.condition:
                if ticket.status == 'pending':
                    if ticket.seq is None:
                        ticket.status = 'rejected'
                        ticket.wait_reason = 'not_sent'
                        self._release(ticket)
                    else:
                        ticket.wait_reason = 'send_uncertain'
                    ticket.reply = {'send_error': True}
                self.condition.notify_all()
        return ticket

    def _release(self, ticket):
        if ticket.kind != 'vehicles':
            if len(self.recent) == self.recent.maxlen:
                self.history_dropped += 1
            self.recent.append(ticket)
        if ticket.seq is not None:
            self.requests.pop(ticket.seq, None)
        if ticket.kind == 'collect' and self.collections.get(ticket.entity) is ticket:
            self.collections.pop(ticket.entity)
        if ticket.kind == 'search' and self.search is ticket:
            self.search = None
        if ticket.kind == 'gather' and self.vehicles.get(ticket.entity) is ticket:
            self.vehicles.pop(ticket.entity)

    def collection(self):
        with self.condition:
            ids = sorted(self.connection.production_building_ids)
            if self.closed or any(i in self.collections for i in ids):
                raise ActionBusy('collection has unresolved requests; inspect the command report before retrying')
            tickets = [Request('collect', i) for i in ids]
            self.collections.update({t.entity: t for t in tickets})
        for ticket in tickets:
            up = up_pb2.up_msg()
            up.bld_produce_req.gain_all_produce_req.bld_id = ticket.entity
            up.bld_produce_req.gain_all_produce_req.timestamp = int(time.time())
            self._send(ticket, up)
        return tickets

    def search_mine(self, resource, level):
        with self.condition:
            if self.closed or self.search is not None:
                raise ActionBusy('mine search has an unresolved request; inspect the command report before retrying')
            self.search = ticket = Request('search')
        up = up_pb2.up_msg()
        req = up.map_request.find_and_refresh_req
        req.req_type, req.type, req.level, req.flag = 4, resource, int(level), 6
        return self._send(ticket, up)

    def gather(self, mine_id, vehicle_id=None):
        with self.condition:
            if self.closed:
                raise ActionBusy('connection closed')
            vehicle = next((v for v in self.connection.farm_vehicles if v.get('state') == 1
                            and not v.get('is_locked') and v.get('id', 0) > 0
                            and v['id'] not in self.vehicles
                            and (vehicle_id is None or v['id'] == vehicle_id)), None)
            if vehicle is None:
                return None
            ticket = Request('gather', vehicle['id'], int(mine_id))
            self.vehicles[vehicle['id']] = ticket  # reserve BEFORE send
        up = up_pb2.up_msg()
        up.map_mine_req.gather_map_mine_req.mine_id = int(mine_id)
        up.map_mine_req.gather_map_mine_req.vehicle_id = ticket.entity
        return self._send(ticket, up)

    def vehicle_list(self):
        up = up_pb2.up_msg()
        up.map_mine_req.get_vehicle_list_req.SetInParent()
        ticket = self._send(Request('vehicles'), up)
        if ticket.reply.get('send_error'):
            raise ConnectionError('vehicle list request could not be sent reliably')
        return ticket

    def receive(self, seq, kind, reply):
        with self.condition:
            ticket = self.requests.get(seq)
            if self.closed or ticket is None or ticket.kind != kind or ticket.status != 'pending':
                return False
            if kind == 'collect' and reply.get('bld_id') != ticket.entity:
                return False
            if kind == 'gather' and (reply.get('vehicle_id') != ticket.entity
                                    or reply.get('mine_id') != ticket.target
                                    or reply.get('state') not in (2, 3, 9)
                                    or reply.get('need_verify')):
                return False
            if kind == 'gather':
                by_id = {v['id']: dict(v) for v in self.connection.farm_vehicles}
                by_id.setdefault(ticket.entity, {'id': ticket.entity}).update(reply['vehicle'])
                self.connection.farm_vehicles = list(by_id.values())
            ticket.reply = dict(reply)
            ticket.status = 'confirmed'
            ticket.wait_reason = 'confirmed_reply'
            if kind != 'gather':
                self._release(ticket)
            self.condition.notify_all()
            return True

    def reject(self, seq):
        with self.condition:
            ticket = self.requests.get(seq)
            if ticket is not None and ticket.status == 'pending':
                ticket.status = 'rejected'
                ticket.wait_reason = 'explicit_rejection'
                self._release(ticket)
                self.condition.notify_all()

    def snapshot(self, seq, vehicles, idle_ids):
        with self.condition:
            if self.closed:
                return
            ticket = self.requests.get(seq)
            if ticket is not None and ticket.kind == 'vehicles':
                self.requests.pop(seq)
                if seq <= self.snapshot_seq:
                    return
                self.snapshot_seq = seq
                for v in vehicles:
                    reservation = ticket.releasable.get(v['id'])
                    if (reservation is not None and self.vehicles.get(v['id']) is reservation
                            and v['id'] in idle_ids):
                        reservation.wait_reason = 'idle_observed'
                        self._release(reservation)
            elif self.snapshot_seq or ticket is not None:
                # Once correlated snapshots exist, unsolicited/stale lists
                # cannot regress the authoritative cache.
                return
            # A list requested before confirmation cannot roll a reserved
            # truck back to idle. Missing entries also retain their cache row.
            current = {v['id']: v for v in self.connection.farm_vehicles}
            merged = {v['id']: v for v in vehicles}
            for vid, reservation in self.vehicles.items():
                if (ticket is None or ticket.releasable.get(vid) is not reservation
                        or vid not in merged or (merged[vid].get('state') == 1 and vid not in idle_ids)):
                    if vid in current:
                        merged[vid] = current[vid]
            self.connection.farm_vehicles = list(merged.values())

    def wait(self, tickets, *, timeout=8.0, cancel_event=None):
        deadline = time.monotonic() + timeout

        def finish(reason):
            for ticket in tickets:
                if ticket.status == 'pending':
                    ticket.wait_reason = reason
            return reason
        with self.condition:
            while any(t.status == 'pending' for t in tickets):
                if self.closed or self.connection.stop_requested or not self.connection.connected:
                    return finish('disconnected')
                if cancel_event is not None and cancel_event.is_set():
                    return finish('cancelled')
                if any(t.reply.get('send_error') for t in tickets):
                    return finish('send_uncertain')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return finish('timeout')
                self.condition.wait(min(remaining, 0.05))
            return 'complete'

    def operational_status(self):
        """Read-only, bounded, allowlisted view; never sends or releases tickets."""
        with self.condition:
            now = time.monotonic()
            active = {t.operation_id: t for t in self.requests.values()}
            for ticket in [*self.collections.values(), *self.vehicles.values(), self.search]:
                if ticket is not None:
                    active[ticket.operation_id] = ticket

            def row(ticket):
                age = max(0.0, now - ticket.started_monotonic)
                reservation = ('truck' if self.vehicles.get(ticket.entity) is ticket else
                               'building' if self.collections.get(ticket.entity) is ticket else
                               'search' if self.search is ticket else 'none')
                status = ticket.status
                reason = ticket.wait_reason or 'waiting_for_reply'
                if status == 'pending':
                    if self.closed or not self.connection.connected:
                        reason = 'disconnected'
                    elif reason == 'waiting_for_reply' and age >= 8:
                        reason = 'timeout'
                    status = 'awaiting_reply' if reason == 'waiting_for_reply' else 'uncertain'
                elif status == 'confirmed' and reservation == 'truck':
                    reason = 'awaiting_idle_observation'
                return dict(operation_id=ticket.operation_id, kind=ticket.kind,
                            status=status, reason=reason, reservation=reservation,
                            created_at=ticket.created_at, age_seconds=round(age, 1),
                            building_id=ticket.entity if ticket.kind == 'collect' else None,
                            vehicle_id=ticket.entity if ticket.kind == 'gather' else None,
                            mine_id=ticket.target if ticket.kind == 'gather' else None)

            return dict(observation_id=self.observation_id,
                        tracking_started_at=self.tracking_started_at,
                        connected=self.connection.connected and not self.closed,
                        active=[row(t) for t in active.values()],
                        recent=[row(t) for t in reversed(self.recent)],
                        recent_dropped=self.history_dropped,
                        tracked_requests=len(self.requests), tracking_limit=1024)

    def collect_result(self, tickets, *, timeout=8.0, cancel_event=None):
        reason = self.wait(tickets, timeout=timeout, cancel_event=cancel_event)
        with self.condition:
            confirmed = [t for t in tickets if t.status == 'confirmed']
            status = ('confirmed' if len(confirmed) == len(tickets) else 'partial' if confirmed else
                      'rejected' if tickets and all(t.status == 'rejected' for t in tickets) else 'uncertain')
            return dict(status=status, detail=reason, buildings_requested=len(tickets),
                        buildings_replied=len(confirmed), items_gained=sum(t.reply['gained_item_count'] for t in confirmed),
                        unconfirmed_building_ids=[t.entity for t in tickets if t.status != 'confirmed'])

    def farm(self, resource, level, *, timeout=8.0, cancel_event=None):
        if not self.farm_lock.acquire(blocking=False):
            raise ActionBusy('farming is already in progress')
        try:
            search = self.search_mine(resource, level)
            reason = self.wait([search], timeout=timeout, cancel_event=cancel_event)
            if search.status != 'confirmed':
                return dict(dispatched=False, status='uncertain' if search.status == 'pending' else 'rejected',
                            detail=f'mine search not confirmed ({reason}); no truck dispatched')
            mine = search.reply.get('mine_id', 0)
            if search.reply.get('result') != 0 or not mine:
                return dict(dispatched=False, status='not_dispatched', detail='no matching resource mine was found nearby')
            if cancel_event is not None and cancel_event.is_set():
                return dict(dispatched=False, status='not_dispatched', detail='cancelled before dispatch')
            ticket = self.gather(mine)
            if ticket is None:
                return dict(dispatched=False, status='not_dispatched', mine_id=mine,
                            detail='found a mine but no idle farm vehicle is available')
            reason = self.wait([ticket], timeout=timeout, cancel_event=cancel_event)
            with self.condition:
                return dict(dispatched=ticket.status == 'confirmed', status=ticket.status if ticket.status != 'pending' else 'uncertain',
                            detail='vehicle dispatched to gather' if ticket.status == 'confirmed' else
                            f'dispatch not confirmed ({reason}); truck remains reserved unless explicitly rejected',
                            mine_id=mine, vehicle_id=ticket.entity)
        finally:
            self.farm_lock.release()
