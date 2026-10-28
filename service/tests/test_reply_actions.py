"""Synthetic wire replies only; no network or wall-clock sleeps."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from app.core.warpath.connection import WarpathConnection
from app.core.warpath.protobuf import down_pb2
from app.core.warpath.reply_actions import ActionBusy
from tests.fakes import (FakeWarpathSocket, decode_request, with_sequence,
    build_gain_all_produce_reply_frame as collect_frame,
    build_try_gather_mine_reply_frame as gather_frame,
    build_map_search_reply_frame as search_frame,
    build_vehicle_list_reply_frame as list_frame, build_err_info_frame)

@pytest.fixture
def conn(make_credentials):
    c = WarpathConnection(make_credentials('synthetic'))
    c.sock = FakeWarpathSocket()
    c.socket_connected = c.authenticated = True
    c.production_building_ids = {107, 108}
    c.farm_vehicles = [{'id': 9, 'state': 1, 'mine_id': 0, 'x': 42, 'is_locked': False}]
    return c

def deliver(c, frame, seq):
    c.observe_account_data(with_sequence(frame, seq)[5:])

def on_send(c, callback):
    original = c.sock.sendall
    def send(packet):
        original(packet)
        callback(decode_request(packet))
    c.sock.sendall = send

def test_collection_inside_sendall_counted_once(conn):
    def reply(up):
        frame = collect_frame(up.bld_produce_req.gain_all_produce_req.bld_id, 2)
        deliver(conn, frame, up.msg_seq_id)
        deliver(conn, frame, up.msg_seq_id)
    on_send(conn, reply)
    tickets = conn.request_collect_all()
    assert conn.reply_actions.collect_result(tickets, timeout=0) == {
        'status': 'confirmed', 'detail': 'complete', 'buildings_requested': 2,
        'buildings_replied': 2, 'items_gained': 4, 'unconfirmed_building_ids': []}

def test_collection_delayed_out_of_order_wrong_entity_stale(conn):
    first, second = tickets = conn.request_collect_all()
    deliver(conn, collect_frame(108, 90), first.seq)
    deliver(conn, collect_frame(107, 90), 0)
    assert conn.reply_actions.collect_result(tickets, timeout=0)['status'] == 'uncertain'
    assert not conn.account_snapshot.get('last_collection_at')
    with pytest.raises(ActionBusy):
        conn.request_collect_all()
    deliver(conn, collect_frame(108, 3), second.seq)
    partial = conn.reply_actions.collect_result(tickets, timeout=0)
    assert (partial['status'], partial['items_gained'], partial['unconfirmed_building_ids']) == ('partial', 3, [107])
    deliver(conn, collect_frame(107, 2), first.seq)
    assert conn.reply_actions.collect_result(tickets, timeout=0)['items_gained'] == 5
    new = conn.request_collect_all()
    deliver(conn, collect_frame(107, 80), first.seq)
    assert conn.reply_actions.collect_result(new, timeout=0)['items_gained'] == 0

def test_collection_waiter_delayed_reply(conn):
    tickets = conn.request_collect_all()
    with ThreadPoolExecutor(1) as pool:
        result = pool.submit(conn.reply_actions.collect_result, tickets, timeout=2)
        for t in reversed(tickets):
            deliver(conn, collect_frame(t.entity), t.seq)
        assert result.result(timeout=3)['status'] == 'confirmed'

def test_concurrent_collection_sends_one_batch(conn):
    gate = threading.Barrier(2)
    def collect():
        gate.wait(timeout=2)
        try:
            return conn.request_collect_all()
        except ActionBusy:
            return None
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(collect) for _ in range(2)]
        assert sum(f.result(timeout=3) is not None for f in futures) == 1
    assert len(conn.sock.sent) == 2

def test_gather_fast_reply_updates_cache_preserves_fields_blocks_reselection(conn):
    on_send(conn, lambda up: deliver(conn, gather_frame(9, 2, 555), up.msg_seq_id))
    assert conn.send_farm_vehicle(555, 9).status == 'confirmed'
    assert conn.farm_vehicles[0] == {'id': 9, 'state': 2, 'mine_id': 555, 'x': 42, 'is_locked': False}
    assert conn.send_farm_vehicle(556, 9) is None
    assert len(conn.sock.sent) == 1

@pytest.mark.parametrize('seq,vehicle,mine,state', [(0,9,555,3), (999,9,555,3), (None,8,555,3), (None,9,556,3), (None,9,555,1)])
def test_unmatched_gather_never_confirms_or_releases(conn, seq, vehicle, mine, state):
    t = conn.send_farm_vehicle(555, 9)
    deliver(conn, gather_frame(vehicle, state, mine), t.seq if seq is None else seq)
    assert conn.reply_actions.wait([t], timeout=0) == 'timeout'
    assert conn.send_farm_vehicle(555, 9) is None
    assert conn.farm_vehicles[0]['state'] == 1

def test_repeated_vehicle_matching_and_verification_required(conn):
    t = conn.send_farm_vehicle(555, 9)
    down = down_pb2.down_msg()
    down.ParseFromString(gather_frame(88, 3, 444)[5:])
    v = down.mine_reply.try_gather_mine_reply.mine_vehicle.add().mine_vehicle
    v.id, v.state, v.mine_id = 9, 3, 555
    down.msg_seq_id = t.seq
    down.mine_reply.try_gather_mine_reply.need_verify = True
    conn.observe_account_data(down.SerializeToString())
    assert t.status == 'pending'
    down.mine_reply.try_gather_mine_reply.need_verify = False
    conn.observe_account_data(down.SerializeToString())
    assert t.status == 'confirmed'
    assert [v['id'] for v in conn.farm_vehicles] == [9]

def test_old_snapshot_cannot_regress_or_free_truck_fresh_idle_can(conn):
    old = conn.request_vehicle_list()
    t = conn.send_farm_vehicle(555, 9)
    deliver(conn, gather_frame(9, 3, 555), t.seq)
    deliver(conn, list_frame([{'id':9, 'state':1}]), old.seq)
    assert conn.farm_vehicles[0]['state'] == 3
    assert conn.send_farm_vehicle(556, 9) is None
    fresh = conn.request_vehicle_list()
    deliver(conn, list_frame([{'id':9, 'state':1}]), fresh.seq)
    new = conn.send_farm_vehicle(556, 9)
    assert new is not None
    deliver(conn, gather_frame(9, 3, 555), t.seq)
    assert new.status == 'pending'

def test_out_of_order_lists_cannot_free_uncertain_truck(conn):
    conn.send_farm_vehicle(555, 9)
    old, new = conn.request_vehicle_list(), conn.request_vehicle_list()
    deliver(conn, list_frame([{'id':9, 'state':1}]), new.seq)
    deliver(conn, list_frame([{'id':9, 'state':1}]), old.seq)
    assert conn.send_farm_vehicle(555, 9) is None

def test_concurrent_gather_reserves_once(conn):
    barrier = threading.Barrier(2)
    def gather(mine):
        barrier.wait(timeout=2)
        return conn.send_farm_vehicle(mine, 9)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(gather, mine) for mine in (555,556)]
        assert sum(f.result(timeout=3) is not None for f in futures) == 1
    assert len(conn.sock.sent) == 1

@pytest.mark.parametrize('kind', ['collect','gather'])
def test_cancel_disconnect_and_reset(conn, kind):
    tracker = conn.reply_actions
    tickets = conn.request_collect_all() if kind == 'collect' else [conn.send_farm_vehicle(555,9)]
    cancel = threading.Event()
    cancel.set()
    assert tracker.wait(tickets, timeout=2, cancel_event=cancel) == 'cancelled'
    assert all(t.status == 'pending' for t in tickets)
    with ThreadPoolExecutor(1) as pool:
        result = pool.submit(tracker.wait, tickets, timeout=2)
        conn.close()
        assert result.result(timeout=3) == 'disconnected'
    conn.reset_account_data()
    deliver(conn, gather_frame(9,3,555), tickets[0].seq)
    assert conn.farm_vehicles == []

def test_send_failure_ambiguous_after_write_rejected_before_write(conn):
    def broken(_):
        raise OSError('synthetic partial write')
    conn.sock.sendall = broken
    t = conn.send_farm_vehicle(555,9)
    assert conn.reply_actions.wait([t], timeout=0) == 'send_uncertain'
    assert conn.send_farm_vehicle(555,9) is None
    conn.reset_account_data()
    conn.farm_vehicles = [{'id':9,'state':1}]
    conn.socket_connected = False
    assert conn.send_farm_vehicle(555,9).status == 'rejected'
    assert not conn.reply_actions.vehicles

def test_correlated_error_releases_reservation(conn):
    t = conn.send_farm_vehicle(555,9)
    deliver(conn, build_err_info_frame(), t.seq)
    assert t.status == 'rejected'
    assert conn.send_farm_vehicle(555,9) is not None

def test_fast_farm_chain_second_attempt_cannot_duplicate(conn):
    def reply(up):
        frame = search_frame(mine_id=555) if up.HasField('map_request') else gather_frame(9,3,555)
        deliver(conn, frame, up.msg_seq_id)
    on_send(conn, reply)
    assert conn.reply_actions.farm('gold',3,timeout=0)['dispatched'] is True
    assert conn.reply_actions.farm('gold',3,timeout=0)['status'] == 'not_dispatched'
    assert len(conn.sock.sent) == 3

def test_search_timeout_and_concurrent_farm_never_dispatch(conn):
    tracker = conn.reply_actions
    assert tracker.farm('gold',3,timeout=0)['status'] == 'uncertain'
    with pytest.raises(ActionBusy):
        tracker.farm('gold',3,timeout=0)
    assert len(conn.sock.sent) == 1
    with tracker.farm_lock:
        with pytest.raises(ActionBusy):
            tracker.farm('gold',3,timeout=0)

@pytest.mark.parametrize('cancelled', [False, True])
def test_unconfirmed_dispatch_reserves_then_late_confirmation_updates(conn, cancelled):
    cancel = threading.Event()
    def reply(up):
        if up.HasField('map_request'):
            deliver(conn, search_frame(mine_id=555), up.msg_seq_id)
        elif cancelled:
            cancel.set()
    on_send(conn, reply)
    result = conn.reply_actions.farm('gold',3,timeout=0,cancel_event=cancel)
    assert result['status'] == 'uncertain' and not result['dispatched']
    ticket = conn.reply_actions.vehicles[9]
    assert conn.send_farm_vehicle(556,9) is None
    deliver(conn, gather_frame(9,3,555), ticket.seq)
    assert conn.farm_vehicles[0]['state'] == 3
    assert ticket.status == 'confirmed'

def test_cancellation_after_search_before_dispatch(conn):
    cancel = threading.Event()
    def reply(up):
        deliver(conn, search_frame(mine_id=555), up.msg_seq_id)
        cancel.set()
    on_send(conn, reply)
    assert conn.reply_actions.farm('gold',3,timeout=0,cancel_event=cancel)['status'] == 'not_dispatched'
    assert len(conn.sock.sent) == 1

def test_two_trucks_out_of_order_and_duplicate_replies(conn):
    conn.farm_vehicles.append({'id':10,'state':1})
    first, second = conn.send_farm_vehicle(555,9), conn.send_farm_vehicle(556,10)
    deliver(conn, gather_frame(10,2,556), second.seq)
    deliver(conn, gather_frame(9,3,555), first.seq)
    deliver(conn, gather_frame(10,1,0), second.seq)
    assert [(v['id'],v['state']) for v in conn.farm_vehicles] == [(9,3),(10,2)]

def test_missing_mine_in_snapshot_does_not_release_confirmed_vehicle(conn):
    t = conn.send_farm_vehicle(555,9)
    deliver(conn, gather_frame(9,3,555), t.seq)
    refresh = conn.request_vehicle_list()
    down = down_pb2.down_msg()
    down.ParseFromString(list_frame([{'id':9,'state':1}])[5:])
    down.mine_reply.get_vehicle_list_reply.mine_vehicle[0].mine_vehicle.ClearField('mine_id')
    down.msg_seq_id = refresh.seq
    conn.observe_account_data(down.SerializeToString())
    assert conn.send_farm_vehicle(556,9) is None
