"""
Fixture: insert ~16 steps for F-00055 so the pipeline strip overflows.
"""
from orch.db.models import StepType, StepStatus


def seed(db):
    pid = "iw-ai-core"
    wid = "F-00055"

    step_specs = [
        ("S00", "Worktree Setup", StepType.implementation, 1),
        ("S01", "Requirements", StepType.implementation, 2),
        ("S02", "Design", StepType.implementation, 3),
        ("S03", "Implementation", StepType.implementation, 4),
        ("S04", "Code Review", StepType.implementation, 5),
        ("S05", "Tests", StepType.implementation, 6),
        ("S06", "Documentation", StepType.implementation, 7),
        ("S07", "QA", StepType.implementation, 8),
        ("S08", "Final Review", StepType.implementation, 9),
        ("S01-R1", "Requirements (fix 1)", StepType.implementation, 10),
        ("S02-R1", "Design (fix 1)", StepType.implementation, 11),
        ("S03-R1", "Implementation (fix 1)", StepType.implementation, 12),
        ("S01-R2", "Requirements (fix 2)", StepType.implementation, 13),
        ("S02-R2", "Design (fix 2)", StepType.implementation, 14),
        ("S01-R3", "Requirements (fix 3)", StepType.implementation, 15),
        ("MERGE", "Squash Merge", StepType("merge"), 16),
    ]

    for step_id_str, label, stype, seq in step_specs:
        existing = db.query(WorkflowStep).filter(
            WorkflowStep.project_id == pid,
            WorkflowStep.work_item_id == wid,
            WorkflowStep.step_id == step_id_str,
        ).first()
        if existing is not None:
            continue
        step = WorkflowStep(
            project_id=pid,
            work_item_id=wid,
            step_number=seq,
            step_id=step_id_str,
            agent_label=label,
            step_type=stype,
            status=StepStatus.pending,
        )
        db.add(step)

    db.commit()
