from __future__ import annotations

from datetime import UTC, datetime

from orch.db.models import RegressionClassification, WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

PROJECT_ID = "iw-ai-core"
FEATURE_ID = "F-00990"
INCIDENT_ID = "I-00990"


def seed(db) -> None:
    now = datetime.now(UTC)
    incident = db.get(WorkItem, (PROJECT_ID, INCIDENT_ID))

    if incident is None:
        db.add(
            WorkItem(
                project_id=PROJECT_ID,
                id=INCIDENT_ID,
                type=WorkItemType.Issue,
                title="Seed incident classified as regression",
                status=WorkItemStatus.completed,
                phase=WorkItemPhase.done,
                summary="Fixture incident for F-00090 browser verification",
                introduced_by_work_item_id=FEATURE_ID,
                regression_classification=RegressionClassification.regression,
                classified_by="operator:sergiog",
                classified_at=now,
                created_at=now,
            )
        )
        return

    incident.type = WorkItemType.Issue
    incident.status = WorkItemStatus.completed
    incident.phase = WorkItemPhase.done
    incident.introduced_by_work_item_id = FEATURE_ID
    incident.regression_classification = RegressionClassification.regression
    incident.classified_by = "operator:sergiog"
    incident.classified_at = now
