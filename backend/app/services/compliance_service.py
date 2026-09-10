"""Domain service for calculating and persisting determinist training compliance (duration-v1)."""

import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import (
    ComplianceComponent,
    ComplianceSummary,
    PlannedSession,
    PlannedSessionResult,
    WeeklyPlan,
)

COMPLIANCE_RULESET_VERSION = "duration-v1"


class ComplianceDomainException(Exception):
    """Base exception for compliance domain errors."""

    pass


class PlanNotFoundException(ComplianceDomainException):
    pass


class GoalNotFoundException(ComplianceDomainException):
    pass


def canonical_fingerprint(data: dict[str, Any]) -> str:
    """Serialize input data canonically and return its SHA256 fingerprint."""

    def default_serializer(obj: Any) -> str:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Type {type(obj)} is not serializable")

    serialized = json.dumps(data, sort_keys=True, default=default_serializer)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ComplianceDomainService:
    @classmethod
    def calculate_session_component(
        cls, session: PlannedSession, result: PlannedSessionResult | None
    ) -> dict[str, Any]:
        """Calculate weight, credit, and error/exclusion details for a single session."""
        weight = Decimal(session.planned_duration)
        planned_duration_snap = session.planned_duration

        if not result:
            return {
                "weight": weight,
                "credit": None,
                "weighted_credit": None,
                "exclusion_or_error_reason": "Sesión pendiente de realizar (sin resultado registrado).",
                "planned_duration_snapshot": planned_duration_snap,
                "actual_duration_snapshot": None,
                "activity_id": None,
                "result_id": None,
            }

        status = result.status.lower()
        activity = result.activity

        if status == "completed":
            return {
                "weight": weight,
                "credit": Decimal("1.0000"),
                "weighted_credit": weight * Decimal("1.0000"),
                "exclusion_or_error_reason": None,
                "planned_duration_snapshot": planned_duration_snap,
                "actual_duration_snapshot": activity.duration_seconds if activity else None,
                "activity_id": activity.id if activity else None,
                "result_id": result.id,
            }

        if status == "omitted":
            return {
                "weight": weight,
                "credit": Decimal("0.0000"),
                "weighted_credit": Decimal("0.0000"),
                "exclusion_or_error_reason": None,
                "planned_duration_snapshot": planned_duration_snap,
                "actual_duration_snapshot": None,
                "activity_id": None,
                "result_id": result.id,
            }

        # For partial or replaced, we must check duration
        if not activity or activity.duration_seconds is None:
            return {
                "weight": weight,
                "credit": None,
                "weighted_credit": None,
                "exclusion_or_error_reason": f"Falta duración de la actividad real en estado '{status}'.",
                "planned_duration_snapshot": planned_duration_snap,
                "actual_duration_snapshot": None,
                "activity_id": activity.id if activity else None,
                "result_id": result.id,
            }

        if activity.duration_seconds <= 0:
            return {
                "weight": weight,
                "credit": None,
                "weighted_credit": None,
                "exclusion_or_error_reason": f"La duración de la actividad vinculada debe ser estrictamente positiva en estado '{status}'.",
                "planned_duration_snapshot": planned_duration_snap,
                "actual_duration_snapshot": activity.duration_seconds,
                "activity_id": activity.id,
                "result_id": result.id,
            }

        planned_seconds = Decimal(session.planned_duration * 60)
        actual_seconds = Decimal(activity.duration_seconds)

        credit = min(actual_seconds / planned_seconds, Decimal("1.0000"))
        # Ensure credit precision is constrained to scale=4 in the DB, but do not round weighted_credit prematuraly
        credit = credit.quantize(Decimal("0.0001"))

        return {
            "weight": weight,
            "credit": credit,
            "weighted_credit": weight * credit,
            "exclusion_or_error_reason": None,
            "planned_duration_snapshot": planned_duration_snap,
            "actual_duration_snapshot": activity.duration_seconds,
            "activity_id": activity.id,
            "result_id": result.id,
        }

    @classmethod
    def calculate_weekly_fingerprint(cls, plan: WeeklyPlan, sessions: list[PlannedSession]) -> str:
        """Generate canonical fingerprint for a weekly plan and its current results."""
        sess_data = []
        for s in sorted(sessions, key=lambda x: x.id):
            # Find current result
            res = next((r for r in s.results if r.is_current), None)
            res_dict = None
            if res:
                res_dict = {
                    "id": res.id,
                    "revision": res.revision,
                    "status": res.status,
                    "activity_id": res.activity_id,
                    "activity_duration": res.activity.duration_seconds if res.activity else None,
                }
            sess_data.append(
                {
                    "id": s.id,
                    "planned_duration": s.planned_duration,
                    "position": s.position,
                    "result": res_dict,
                }
            )

        input_data = {
            "ruleset_version": COMPLIANCE_RULESET_VERSION,
            "plan_id": plan.id,
            "plan_version": plan.version,
            "sessions": sess_data,
        }
        return canonical_fingerprint(input_data)

    @classmethod
    def calculate_goal_fingerprint(
        cls, goal_id: int, from_date: date, to_date: date, plans: list[WeeklyPlan]
    ) -> str:
        """Generate canonical fingerprint for goal-level compliance within a timeframe."""
        plans_data = []
        # Sort plans to ensure stable fingerprint
        for p in sorted(plans, key=lambda x: x.id):
            sess_data = []
            for s in sorted(p.sessions, key=lambda x: x.id):
                res = next((r for r in s.results if r.is_current), None)
                res_dict = None
                if res:
                    res_dict = {
                        "id": res.id,
                        "revision": res.revision,
                        "status": res.status,
                        "activity_id": res.activity_id,
                        "activity_duration": res.activity.duration_seconds
                        if res.activity
                        else None,
                    }
                sess_data.append(
                    {
                        "id": s.id,
                        "planned_duration": s.planned_duration,
                        "position": s.position,
                        "result": res_dict,
                    }
                )
            plans_data.append(
                {
                    "plan_id": p.id,
                    "plan_version": p.version,
                    "sessions": sess_data,
                }
            )

        input_data = {
            "ruleset_version": COMPLIANCE_RULESET_VERSION,
            "goal_id": goal_id,
            "from_date": from_date,
            "to_date": to_date,
            "plans": plans_data,
        }
        return canonical_fingerprint(input_data)

    @classmethod
    def calculate_and_persist_weekly(
        cls, db: Session, plan_id: int, user_id: int
    ) -> ComplianceSummary:
        """Atomic calculations and persistence for weekly compliance summary."""
        # 1. Fetch the plan and verify ownership
        plan = db.scalar(
            select(WeeklyPlan).where(and_(WeeklyPlan.id == plan_id, WeeklyPlan.user_id == user_id))
        )
        if not plan:
            raise PlanNotFoundException("Plan semanal no encontrado.")

        # Grab all sessions of this plan
        sessions = plan.sessions

        # 2. Check fingerprint for idempotency
        fingerprint = cls.calculate_weekly_fingerprint(plan, sessions)

        # Retrieve current active summary
        current_summary = db.scalar(
            select(ComplianceSummary).where(
                and_(
                    ComplianceSummary.user_id == user_id,
                    ComplianceSummary.weekly_plan_id == plan_id,
                    ComplianceSummary.scope == "weekly",
                    ComplianceSummary.is_current.is_(True),
                )
            )
        )

        if current_summary and current_summary.input_fingerprint == fingerprint:
            # Idempotent match: return current summary
            return current_summary

        # 3. Calculate components
        comps_data = []
        has_incomplete = False
        tot_weight = Decimal("0.0000")
        tot_weighted_credit = Decimal("0.0000")

        for s in sessions:
            res = next((r for r in s.results if r.is_current), None)
            comp = cls.calculate_session_component(s, res)
            comps_data.append(comp)

            # If any component lacks credit/weighted credit, it is incomplete/exclusion
            if comp["credit"] is None:
                has_incomplete = True
            else:
                tot_weight += comp["weight"]
                tot_weighted_credit += comp["weighted_credit"]

        # If has_incomplete is True, the status is incomplete, percentage is None
        if has_incomplete:
            status = "incomplete"
            percentage = None
            numerator = tot_weighted_credit
            denominator = sum(c["weight"] for c in comps_data)
        elif tot_weight == 0:
            status = "not_applicable"
            percentage = None
            numerator = Decimal("0.0000")
            denominator = Decimal("0.0000")
        else:
            status = "complete"
            numerator = tot_weighted_credit
            denominator = tot_weight
            # Percentage: 100 * numerator / denominator
            percentage = (Decimal("100") * numerator / denominator).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # 4. Save revision atomically
        if current_summary:
            current_summary.is_current = False
            db.add(current_summary)
            db.flush()

        next_revision = current_summary.revision + 1 if current_summary else 1
        supersedes_id = current_summary.id if current_summary else None

        summary = ComplianceSummary(
            user_id=user_id,
            scope="weekly",
            weekly_plan_id=plan_id,
            goal_id=plan.active_goal_id,
            revision=next_revision,
            status=status,
            numerator=numerator,
            denominator=denominator,
            percentage=percentage,
            ruleset_version=COMPLIANCE_RULESET_VERSION,
            input_fingerprint=fingerprint,
            computed_at=datetime.utcnow(),
            supersedes_summary_id=supersedes_id,
            is_current=True,
        )
        db.add(summary)
        db.flush()

        # Save components
        for i, s in enumerate(sessions):
            comp_val = comps_data[i]
            comp_model = ComplianceComponent(
                summary_id=summary.id,
                planned_session_id=s.id,
                planned_session_result_id=comp_val["result_id"],
                activity_id=comp_val["activity_id"],
                weight=comp_val["weight"],
                credit=comp_val["credit"],
                weighted_credit=comp_val["weighted_credit"],
                exclusion_or_error_reason=comp_val["exclusion_or_error_reason"],
                planned_duration_snapshot=comp_val["planned_duration_snapshot"],
                actual_duration_snapshot=comp_val["actual_duration_snapshot"],
            )
            db.add(comp_model)

        db.commit()
        db.refresh(summary)
        return summary

    @classmethod
    def calculate_and_persist_goal(
        cls, db: Session, goal_id: int, user_id: int, from_date: date, to_date: date
    ) -> ComplianceSummary:
        """Atomic calculations and persistence for goal-level compliance summary."""
        # 1. Find all active (vigente) plans in that range
        plans = list(
            db.scalars(
                select(WeeklyPlan)
                .where(
                    and_(
                        WeeklyPlan.user_id == user_id,
                        WeeklyPlan.active_goal_id == goal_id,
                        WeeklyPlan.start_date >= from_date,
                        WeeklyPlan.end_date <= to_date,
                        WeeklyPlan.is_active.is_(True),
                    )
                )
                .order_by(WeeklyPlan.start_date.asc())
            )
        )

        # 2. Get fingerprint
        fingerprint = cls.calculate_goal_fingerprint(goal_id, from_date, to_date, plans)

        # Retrieve current active summary
        current_summary = db.scalar(
            select(ComplianceSummary).where(
                and_(
                    ComplianceSummary.user_id == user_id,
                    ComplianceSummary.goal_id == goal_id,
                    ComplianceSummary.scope == "goal",
                    ComplianceSummary.from_date == from_date,
                    ComplianceSummary.to_date == to_date,
                    ComplianceSummary.is_current.is_(True),
                )
            )
        )

        if current_summary and current_summary.input_fingerprint == fingerprint:
            return current_summary

        # 3. Calculate components of all sessions across all plans
        has_incomplete = False
        tot_weight = Decimal("0.0000")
        tot_weighted_credit = Decimal("0.0000")

        all_sessions: list[tuple[PlannedSession, dict[str, Any]]] = []

        for p in plans:
            for s in p.sessions:
                res = next((r for r in s.results if r.is_current), None)
                comp = cls.calculate_session_component(s, res)
                all_sessions.append((s, comp))

                if comp["credit"] is None:
                    has_incomplete = True
                else:
                    tot_weight += comp["weight"]
                    tot_weighted_credit += comp["weighted_credit"]

        if not all_sessions:
            # Denominator is zero since there are no sessions planned at all
            status = "not_applicable"
            percentage = None
            numerator = Decimal("0.0000")
            denominator = Decimal("0.0000")
        elif has_incomplete:
            status = "incomplete"
            percentage = None
            numerator = tot_weighted_credit
            denominator = sum(c[1]["weight"] for c in all_sessions)
        elif tot_weight == 0:
            status = "not_applicable"
            percentage = None
            numerator = Decimal("0.0000")
            denominator = Decimal("0.0000")
        else:
            status = "complete"
            numerator = tot_weighted_credit
            denominator = tot_weight
            percentage = (Decimal("100") * numerator / denominator).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # 4. Save summary atomically
        if current_summary:
            current_summary.is_current = False
            db.add(current_summary)
            db.flush()

        next_revision = current_summary.revision + 1 if current_summary else 1
        supersedes_id = current_summary.id if current_summary else None

        summary = ComplianceSummary(
            user_id=user_id,
            scope="goal",
            weekly_plan_id=None,
            goal_id=goal_id,
            from_date=from_date,
            to_date=to_date,
            revision=next_revision,
            status=status,
            numerator=numerator,
            denominator=denominator,
            percentage=percentage,
            ruleset_version=COMPLIANCE_RULESET_VERSION,
            input_fingerprint=fingerprint,
            computed_at=datetime.utcnow(),
            supersedes_summary_id=supersedes_id,
            is_current=True,
        )
        db.add(summary)
        db.flush()

        # Save components
        for s, comp_val in all_sessions:
            comp_model = ComplianceComponent(
                summary_id=summary.id,
                planned_session_id=s.id,
                planned_session_result_id=comp_val["result_id"],
                activity_id=comp_val["activity_id"],
                weight=comp_val["weight"],
                credit=comp_val["credit"],
                weighted_credit=comp_val["weighted_credit"],
                exclusion_or_error_reason=comp_val["exclusion_or_error_reason"],
                planned_duration_snapshot=comp_val["planned_duration_snapshot"],
                actual_duration_snapshot=comp_val["actual_duration_snapshot"],
            )
            db.add(comp_model)

        db.commit()
        db.refresh(summary)
        return summary
