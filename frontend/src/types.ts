export interface User {
  id: number
  email: string
  name: string
}

export interface Activity {
  id: number
  user_id: number
  name: string
  sport: string
  started_at: string | null
  duration_seconds: number | null
  distance_meters: number | null
  elevation_gain_meters: number | null
  average_heart_rate: number | null
  average_power: number | null
  average_cadence: number | null
  calories: number | null
  original_filename: string | null
  source_format: string
  goal_id: number | null
}

export interface PlannedSessionResultRead {
  id: number
  planned_session_id: number
  revision: number
  is_current: boolean
  supersedes_result_id: number | null
  activity_id: number | null
  status: 'completed' | 'omitted' | 'partial' | 'replaced'
  reason: string | null
  correction_reason: string | null
  notes: string | null
  recorded_at: string
  created_at: string
}

export interface PlannedSessionRead {
  id: number
  date: string
  training_type: string
  title: string
  description: string | null
  planned_duration: number
  planned_distance_meters: number | null
  intensity_metric: string
  target_zone: string
  session_goal: string | null
  position: number
  rationale: string | null
  results?: PlannedSessionResultRead[]
}

export interface WeeklyPlanRead {
  id: number
  active_goal_id: number | null
  start_date: string
  end_date: string
  version: number
  is_active: boolean
  created_at: string
  generation_reason: string | null
  ruleset_version: string
  sessions: PlannedSessionRead[]
  rationale_data: { decisions: string[] }
}

export interface WeeklyPlanHistoryRead {
  id: number
  start_date: string
  end_date: string
  version: number
  is_active: boolean
  created_at: string
  generation_reason: string | null
}

export interface Goal {
  id: number
  user_id: number
  title: string
  goal_type: string
  start_date: string | null
  target_date: string
  sport: string
  priority: string
  target_distance_meters: number | null
  target_elevation_meters: number | null
  success_metric: string
  success_metric_type: string | null
  success_metric_value: number | null
  success_metric_unit: string | null
  details: string | null
  is_active: boolean
  route_original_filename: string | null
  route_size_bytes: number | null
  route_uploaded_at: string | null
  route_distance_meters: number | null
  route_elevation_gain_meters: number | null
  route_start_latitude: number | null
  route_start_longitude: number | null
  route_end_latitude: number | null
  route_end_longitude: number | null
  route_bounds: Record<string, number> | null
  routes: GoalRoute[]
}

export interface GoalRoute {
  id: number
  goal_id: number
  original_filename: string
  uploaded_at: string
  display_order: number
  stage_label: string | null
  size_bytes: number
  distance_meters: number | null
  elevation_gain_meters: number | null
  start_latitude: number | null
  start_longitude: number | null
  end_latitude: number | null
  end_longitude: number | null
  bounds: Record<string, number> | null
}

export interface ComplianceComponentRead {
  id: number
  summary_id: number
  planned_session_id: number
  planned_session_result_id: number | null
  activity_id: number | null
  weight: number
  credit: number | null
  weighted_credit: number | null
  exclusion_or_error_reason: string | null
  planned_duration_snapshot: number
  actual_duration_snapshot: number | null
}

export interface ComplianceSummaryRead {
  id: number
  user_id: number
  scope: 'weekly' | 'goal'
  weekly_plan_id: number | null
  goal_id: number
  from_date: string | null
  to_date: string | null
  revision: number
  status: 'complete' | 'incomplete' | 'not_applicable'
  numerator: number
  denominator: number
  percentage: number | null
  ruleset_version: string
  input_fingerprint: string
  computed_at: string
  is_current: boolean
  components?: ComplianceComponentRead[]
}
