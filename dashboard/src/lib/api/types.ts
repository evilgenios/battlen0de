/**
 * Typed mirrors of the FastAPI backend's Pydantic schemas
 * (service/app/schemas/accounts.py, sessions.py, actions.py) and repository
 * DTOs (service/app/db/repository.py: AccountRecord, AccountEventRecord).
 *
 * Deliberately excludes app_token/device_id everywhere — the backend never
 * returns them (see AccountResponse in the Python source), so there is no
 * field here for a secret to accidentally end up in.
 */

export type AccountStatus = 'active' | 'disabled' | 'needs_reauth' | 'restricted';

/** Mirrors app/schemas/accounts.py: DeviceMetadata. Every field optional on
 * input (the backend fills defaults); always present on output. */
export interface DeviceMetadata {
  app_id: string;
  pack_name: string;
  channel_id: string;
  device_model: string;
  os_type: string;
  os_version: string;
  os_language: string;
  pack_language: string;
  timezone: number;
  app_version: string;
  package_version: string;
  env_id: string;
  net_route_type: number;
  net_route_info: string;
  client_ip: string;
  game_id: string;
  server_ip: string;
  server_port: number;
  login_timeout: number;
}

export type DeviceMetadataInput = Partial<DeviceMetadata>;

/** Mirrors app/schemas/accounts.py: AccountCreateRequest. */
export interface AccountCreateRequest {
  label: string;
  linked_email?: string | null;
  app_uid: string;
  /** Write-only: sent to the backend, never returned by any endpoint. */
  app_token: string;
  /** Write-only: sent to the backend, never returned by any endpoint. */
  device_id: string;
  profile_uid?: number | null;
  platform?: number;
  device_metadata?: DeviceMetadataInput;
  status?: AccountStatus;
}

/** Mirrors app/schemas/accounts.py: AccountResponse / db/repository.py:
 * AccountRecord. No app_token/device_id field exists here on purpose. */
export interface Account {
  id: string;
  owner_user_id: string;
  label: string;
  linked_email: string | null;
  app_uid: string;
  profile_uid: number | null;
  platform: number;
  device_metadata: DeviceMetadata;
  linked_at: string | null;
  last_connected_at: string | null;
  status: AccountStatus;
  created_at: string;
  updated_at: string;
}

/** Mirrors app/core/account_session.py: SessionState. */
export type SessionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'stopped'
  | 'failed'
  | 'restricted';

/** Mirrors app/schemas/sessions.py: LiveSessionStatus. */
export interface LiveSessionStatus {
  account_id: string;
  label: string;
  state: SessionState;
  authenticated: boolean;
  connection_state: string;
  last_error: string | null;
  last_connected_at: number | null;
  started_at: number | null;
  retry_count: number;
  auth_failure_count: number;
}

/** Mirrors app/schemas/sessions.py: SessionStatusResponse. `live` is null
 * when this worker process has no registered AccountSession for the
 * account yet (e.g. created but never connected since the worker last
 * started). */
export interface SessionStatus {
  account_id: string;
  db_status: AccountStatus;
  live: LiveSessionStatus | null;
}

export interface PilotActivationStatus {
  mode: 'off' | 'observe';
  reason: 'not_activated' | 'expired' | 'operator_grant' | 'customer_mode';
  instance_id: string;
  issued_by: string | null;
  issued_at: number | null;
  expires_at: number | null;
  automatic_actions: false;
  game_actions: false;
  upstream_evidence: 'unverified';
  restart_policy: 'off' | 'auto';
}

export interface AccountOverviewResponse {
  account: Account;
  status: SessionStatus;
}

/** Mirrors app/schemas/actions.py: ActionResponse. */
export interface ActionResult {
  detail: string;
}

export type FarmResource = 'gold' | 'metal' | 'oil';

/** Mirrors app/schemas/actions.py request bodies. */
export interface ScanParams {
  center_x?: number | null;
  center_y?: number | null;
}
export interface FarmParams {
  resource: FarmResource;
  level: number;
}
export interface RecallParams {
  vehicle_id: number;
}
export interface ScoutParams {
  plane_id: number;
}

/** Mirrors app/schemas/actions.py: CollectResponse — the real per-building
 * outcome, not just "requested" (collect() waits for a reply per known
 * production building). */
export interface CollectResult {
  status: 'confirmed' | 'partial' | 'uncertain' | 'rejected';
  detail: string;
  unconfirmed_building_ids: number[];
  buildings_requested: number;
  buildings_replied: number;
  items_gained: number;
}

/** Mirrors app/schemas/actions.py: FarmResponse. dispatched=false with a
 * mine_id but no vehicle_id can mean no idle vehicle was available. Read
 * status/detail: uncertain replies never establish whether a send executed. */
export interface FarmResult {
  status: 'confirmed' | 'uncertain' | 'rejected' | 'not_dispatched';
  dispatched: boolean;
  detail: string;
  mine_id: number | null;
  vehicle_id: number | null;
}

/** Mirrors app/schemas/actions.py: RecallResponse — the vehicle's real
 * post-recall state, read back from the server's own reply. */
export interface RecallResult {
  vehicle_id: number;
  state: number;
}

/** Mirrors app/schemas/accounts.py: AccountEventResponse. `detail` is
 * whatever safe (non-secret) metadata the backend attached — see
 * db/repository.py's add_event and app/main.py's on_event bridge. */
export interface AccountEvent {
  id: number;
  account_id: string | null;
  actor: string;
  event_type: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AccountEventWithLabelResponse {
  event: AccountEvent;
  account_label: string | null;
}

/** Mirrors GET /health's success body. */
export interface HealthStatus {
  status: 'ok';
  database: 'ok';
  auth_required: boolean;
}

/** Mirrors app/schemas/link.py: LinkRequestBody. */
export interface LinkRequestParams {
  account_id?: string;
  challenge_id?: string;
  email: string;
}

/** Mirrors app/schemas/link.py: LinkRequestResponse. Never contains a
 * credential — just enough to let the browser ask for the code again or
 * submit it. */
export interface LinkRequestResult {
  challenge_id: string;
  email: string;
  expires_in_seconds: number;
}

/** Mirrors app/schemas/link.py: LinkVerifyBody. */
export interface LinkVerifyParams {
  challenge_id: string;
  code: string;
  label?: string;
}

/** Mirrors app/schemas/mass_deploy.py: MassDeployRequest. */
export interface MassDeployParams {
  account_ids: string[];
  ag_id: string;
  player_uid: string;
  army_ids?: string;
  group_type?: 'auto' | 'land' | 'navy';
  execute?: boolean;
}

/** Mirrors app/schemas/mass_deploy.py: MassDeployAccountResult. */
export interface MassDeployAccountResult {
  account_id: string;
  label: string;
  teleport: string;
  ag: string;
  error: string | null;
}

/** Mirrors app/schemas/auth.py: DashboardUserInfo (login response). */
export interface DashboardUserInfo {
  email: string;
  role: string;
  csrf_token: string;
}

/** Mirrors app/schemas/auth.py: MeResponse. */
export interface MeResponse {
  user_id: string;
  session_key: string;
  email: string;
  role: string;
  active_sessions: number;
  /** Optional only during rolling deploy against an older Phase 6 backend. */
  plan?: 'individual' | 'alliance';
  max_accounts?: number;
  max_sessions?: number;
  max_active_accounts?: number;
  /** Privileged Player Scout / exact player locate entitlement. */
  player_scout_access?: boolean;
  mfa_enabled?: boolean;
}

export interface LoginParams {
  email: string;
  password: string;
  mfa_code?: string;
}

/** Mirrors app/schemas/mass_deploy.py: MassDeployResponse. */
export interface MassDeployResult {
  execute: boolean;
  ag_id: string;
  player_uid: string;
  army_ids: string;
  group_type: string;
  results: MassDeployAccountResult[];
  complete_count: number;
  total_count: number;
}

export interface MassCancelResult {
  cancelled: boolean;
  detail: string;
}

/** Mirrors app/schemas/intel.py: AccountSummary. */
export interface AccountSummaryInfo {
  name: string | null;
  uid: number | null;
  account_level: number | null;
  mainbase_level: number | null;
  base_state: string;
  base_x: number | null;
  base_y: number | null;
  current_map_id: number;
  vehicle_count: number;
  scout_plane_count: number;
  map_object_count: number;
  army_count: number;
}

/** Mirrors app/schemas/intel.py: DailyMissionTaskInfo. */
export interface DailyMissionTaskInfo {
  id: number;
  status: number;
  status_label: string;
  num: number;
  only_id: number;
  village_obj_id: number;
  finish_timestamp: number;
  source: string;
  updated_at: number;
}

/** Mirrors app/schemas/intel.py: DailyMissionRewardInfo. */
export interface DailyMissionRewardInfo {
  award_index: number;
  award_status: number;
  award_status_label: string;
}

export interface DailyMissionSupplyCaseInfo {
  key: string;
  value: number;
}

/** Mirrors app/schemas/intel.py: DailyMissionObserverResponse. */
export interface DailyMissionObserverResponse {
  observed: boolean;
  state_source: 'none' | 'live' | 'persisted' | string;
  observed_at: number | null;
  activition_point: number;
  refresh_time: number;
  tasks: DailyMissionTaskInfo[];
  daily_awards: DailyMissionRewardInfo[];
  supply_cases: DailyMissionSupplyCaseInfo[];
  supply_case_last_reply: Record<string, unknown> | null;
  task_updated_at: number | null;
  activation_updated_at: number | null;
  supply_case_updated_at: number | null;
  activation_source: string | null;
  limitation: string;
}

export interface DailyMissionMapperBaselineResult {
  baseline_set: boolean;
  captured_at: number;
  task_count: number;
  activition_point: number;
}

export interface DailyMissionTaskChange {
  id: number;
  kind: 'added' | 'removed' | 'changed' | string;
  changed_fields: string[];
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export interface DailyMissionRewardChange {
  award_index: number;
  before_status: number | null;
  after_status: number | null;
}

export interface DailyMissionInventoryChange {
  item_id: string;
  before_quantity: number;
  after_quantity: number;
  delta: number;
}

export interface DailyMissionSupplyCaseChange {
  key: string;
  before_value: number;
  after_value: number;
  delta: number;
}

export interface DailyMissionMapperDiffResult {
  baseline_captured_at: number | null;
  current_captured_at: number | null;
  task_changes: DailyMissionTaskChange[];
  activation: { before: number; after: number; delta: number };
  reward_changes: DailyMissionRewardChange[];
  inventory_observed: { before: boolean; after: boolean };
  inventory_changes: DailyMissionInventoryChange[];
  supply_case_observed: { before: boolean; after: boolean };
  supply_case_changes: DailyMissionSupplyCaseChange[];
  has_changes: boolean;
}

export interface DailyMissionMappingResult {
  objective_key: string;
  label: string;
  task_id: number;
  only_id: number;
  mapped_at: number;
  evidence: Record<string, unknown>;
}

export interface DailyMissionMappingClearResult {
  objective_key: string;
  cleared: boolean;
}

export interface DailyMissionPlanObjective {
  key: string;
  label: string;
  requested_goal: string;
  automation_state: 'guarded_primitive' | 'observer_only' | string;
  schema_known: boolean;
  server_confirmation_known: boolean;
  execution_exposed: boolean;
  combat: boolean;
  blockers: string[];
  mapping_state: 'unmapped' | 'mapped_missing' | 'pending' | 'complete' | 'unknown' | string;
  complete: boolean;
  task_id: number | null;
  only_id: number | null;
  task_status: number | null;
  task_status_label: string | null;
  num: number | null;
  mapped_at: number | null;
}

export interface DailyMissionPlanResponse {
  observed: boolean;
  state_source: string;
  observed_at: number | null;
  mapped_count: number;
  complete_count: number;
  total_count: number;
  objectives: DailyMissionPlanObjective[];
  limitation: string;
}

export interface VehicleInfo {
  id: number;
  state: number;
  state_label: string;
  mine_id: number;
  map_vehicle_id: number;
  type_id: number;
  map_id: number;
  is_locked: boolean;
  x: number;
  y: number;
  start_time: number;
  end_time: number;
  max_gather_num: number;
  target_x: number;
  target_y: number;
}

/** Mirrors app/schemas/intel.py: ActiveActionInfo. Fields not meaningful
 * for a given activity_type are undefined rather than 0 — see that
 * schema's docstring for why. */
/** Mirrors app/schemas/intel.py: ProductionLineInfo — the complete,
 * unfiltered production picture (unlike ActiveActionInfo's production
 * entries, which only include cells with a real end_time). */
export interface ProductionLineInfo {
  building_id: number;
  line_id: number;
  item_type_id?: string | null;
  quantity?: number | null;
  start_time?: number | null;
  end_time?: number | null;
  status: string;
}

export interface ActiveActionInfo {
  activity_type: string;
  status: string;
  vehicle_id?: number | null;
  mine_id?: number | null;
  building_id?: number | null;
  line_id?: number | null;
  map_id?: number | null;
  x?: number | null;
  y?: number | null;
  target_x?: number | null;
  target_y?: number | null;
  item_type_id?: string | null;
  quantity?: number | null;
  start_time?: number | null;
  end_time?: number | null;
  task_id?: string | null;
  task_status?: number | null;
  detail?: string | null;
}

export interface ArmyInfo {
  army_id: number;
  equipment_id: number;
  reserves: number;
  master_obj_id: number;
  group_unique_id: number;
}

export interface ArmyGroupInfo {
  unique_id: number;
  group_type: number;
  map_id: number;
  city_id: number;
  creator_uid: number;
  creator_name: string;
  announcement: string;
  state: number;
  army_count: number;
  max_num: number;
}

/** Mirrors app/schemas/intel.py: JoinArmyGroupResponse — real post-join
 * state read back from connection.armies, not just "requested". */
export interface JoinArmyGroupResult {
  ag_id: number;
  joined_army_ids: number[];
  unconfirmed_army_ids: number[];
}

/** Mirrors app/schemas/intel.py: LeaveArmyGroupResponse. */
export interface LeaveArmyGroupResult {
  army_id: number;
  left: boolean;
}

export interface ProfileInfo {
  uid: number;
  name: string;
  guild_id: number;
  guild_name: string;
  power: number;
  skin_point: number;
  commander_skin: number;
  title_skin: number;
}

export interface MapObjectInfo {
  unique_id: number;
  owner_id: number;
  x: number;
  y: number;
  object_type: number;
  map_id: number;
  is_mainbase: boolean;
  is_monster: boolean;
  monster_id: number | null;
  monster_target_uid: number | null;
  monster_group_id: number | null;
  monster_group_type: number | null;
  battlefield_id: number | null;
}

export interface MainbasePosition {
  player_id: number;
  x: number;
  y: number;
}

export interface RefreshResult {
  requested: string[];
  failures: string[];
}

export interface SkinsResult {
  categories: Record<string, Array<Record<string, unknown>>>;
}

export interface ConquestGuardStatus {
  enabled: boolean;
  armed_uid: number;
  connected_uid: number | null;
  in_progress: boolean;
  attempts: number;
  last_attack: Record<string, unknown> | null;
  last_result: Record<string, unknown> | null;
}

export interface RawSnapshotResult {
  snapshot: Record<string, unknown>;
}

export interface DebugCaptureStartResult {
  started: boolean;
  log_path: string | null;
}

export interface DebugCaptureStopResult {
  message_count: number;
  log_path: string | null;
}

/** Allowlisted, read-only observations from the current game connection. */
export interface CommandObservation {
  operation_id: string;
  kind: 'collect' | 'gather' | 'search' | 'vehicles';
  status: 'awaiting_reply' | 'uncertain' | 'confirmed' | 'rejected';
  reason: 'waiting_for_reply' | 'timeout' | 'cancelled' | 'disconnected' | 'send_uncertain'
    | 'confirmed_reply' | 'explicit_rejection' | 'not_sent' | 'awaiting_idle_observation' | 'idle_observed';
  reservation: 'truck' | 'building' | 'search' | 'none';
  created_at: number;
  age_seconds: number;
  building_id: number | null;
  vehicle_id: number | null;
  mine_id: number | null;
}

export interface CommandStatus {
  history_scope: 'current_connection_only';
  history_complete: false;
  upstream_evidence: 'unverified';
  observation_id: string | null;
  tracking_started_at: number | null;
  connected: boolean;
  active: CommandObservation[];
  recent: CommandObservation[];
  recent_dropped: number;
  tracked_requests: number;
  tracking_limit: number;
}


export interface AdminSummary {
  users_total: number;
  users_active: number;
  users_disabled: number;
  accounts_total: number;
  accounts_connected: number;
  active_web_sessions: number;
  alliance_users: number;
  individual_users: number;
}

export interface AdminUser {
  id: string;
  email: string;
  role: string | null;
  status: string;
  plan: 'individual' | 'alliance';
  max_accounts: number;
  max_sessions: number;
  max_active_accounts: number;
  player_scout_access: boolean;
  mfa_enabled: boolean;
  account_count: number;
  active_sessions: number;
  created_at: string;
  updated_at: string;
}

export interface AdminAccount {
  id: string;
  owner_user_id: string;
  owner_email: string;
  label: string;
  app_uid: string;
  linked_email: string | null;
  status: string;
  live_state: string | null;
  authenticated: boolean;
  last_connected_at: string | null;
}

export interface AdminAuditEvent {
  id: number;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  outcome: string;
  peer_ip: string | null;
  user_agent: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AdminAccountEvent {
  id: number;
  account_id: string | null;
  account_label: string | null;
  owner_email: string | null;
  actor: string;
  event_type: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AdminUserPolicyPatch {
  status: 'active' | 'disabled';
  max_accounts: number;
  max_sessions: number;
  max_active_accounts: number;
  player_scout_access?: boolean;
}

export interface MfaStatus {
  enabled: boolean;
  setup_pending: boolean;
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
}


export interface DailyMissionAssistObjective extends DailyMissionPlanObjective {
  assist_state:
    | 'ready'
    | 'complete'
    | 'mapping_required'
    | 'evidence_required'
    | 'input_required'
    | 'validation_required'
    | 'combat_disabled'
    | 'blocked'
    | string;
  action_key: string | null;
  requires_confirmation: boolean;
  resolved_parameters: Record<string, unknown>;
  assist_reason: string;
}

export interface DailyMissionAssistResponse {
  observed: boolean;
  state_source: string;
  observed_at: number | null;
  ready_count: number;
  complete_count: number;
  total_count: number;
  objectives: DailyMissionAssistObjective[];
  mode: 'assist' | string;
  automatic_execution: false;
  limitation: string;
}

export interface DailyUnitCouponAssistResult {
  status: 'confirmed';
  objective_key: 'use_1_unit_coupon';
  item_id: string;
  quantity: 1;
  detail: string;
}

export interface DailyObservedOfficerOption {
  officer_id: string;
  exp: number;
  level: number;
  power: number;
}

export interface DailyObservedMissionOption {
  task_id: string;
  status: number;
  start_time: number;
  end_time: number;
  officer_ids: string[];
}

export interface DailyOfficerExpAssistResult {
  status: 'confirmed';
  objective_key: 'use_3_officer_exp';
  officer_id: string;
  item_id: string;
  quantity: 3;
  detail: string;
}

export interface DailyOfficerMissionAssistResult {
  status: 'confirmed';
  objective_key: 'launch_officer_mission';
  task_id: string;
  officer_ids: string[];
  detail: string;
}

export interface BattleReportPlayerInfo {
  uid: number;
  name: string;
  guild_name: string;
  power: number;
}

export interface BattleReportSummaryInfo {
  id: number;
  mail_template_id: string;
  mail_box_type: number;
  title: string;
  from_name: string;
  create_time: number;
  read: boolean;
  kind: string;
  players: BattleReportPlayerInfo[];
  battle_type: number;
  attacker_dead: number;
  defender_dead: number;
  attacker_damage: number;
  kill_point: number;
  join_kill: number;
  join_player_num: number;
  group_kill_num: number;
  group_be_kill_num: number;
  group_mainbase_kill_num: number;
  group_battle_time: number;
}

export interface BattleReportAnalyzerResponse {
  observed: boolean;
  updated_at: number | null;
  report_count: number;
  total_attacker_damage: number;
  total_attacker_dead: number;
  total_defender_dead: number;
  total_kill_points: number;
  reports: BattleReportSummaryInfo[];
}

export interface ArmyPresetOfficerInfo {
  index: number;
  officer_id: string;
  officer_equip_id: number;
}

export interface ArmyPresetArmyInfo {
  army_id: number;
  card_id: string;
  officers: ArmyPresetOfficerInfo[];
}

export interface ArmyPresetInfo {
  preset_id: number;
  play_type: number;
  name: string;
  is_auto_train: boolean;
  auto_train_list: number[];
  is_only_use_officer: boolean;
  armies: ArmyPresetArmyInfo[];
  apply_time: number;
}

export interface ArmyPresetListResponse {
  presets: ArmyPresetInfo[];
  observed: boolean;
}

export interface ArmyPresetRenameResult {
  preset_id: number;
  play_type: number;
  name: string;
  confirmed: true;
}

export interface SupplyCaseStateInfo {
  key: string;
  value: number;
}

export interface SupplyCaseOverviewResponse {
  observed: boolean;
  updated_at: number | null;
  cases: SupplyCaseStateInfo[];
  last_reply: Record<string, unknown> | null;
  campaign_mapping_state: string;
  campaign_task_id: number | null;
  campaign_num: number | null;
  limitation: string;
}
