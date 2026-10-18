import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from jarvis import db
from jarvis.config import setting

TEST_WORDS = re.compile(r"\b(exam|test|midterm)\b|\bfinal\b(?!\s+(project|paper|essay|draft|portfolio|presentation))", re.IGNORECASE)
QUIZ_WORDS = re.compile(r"\bquiz", re.IGNORECASE)
DONE_STATES = {"submitted", "graded", "pending_review"}


class CanvasError(Exception):
    pass


def credentials():
    return setting("CANVAS_URL", "").rstrip("/"), setting("CANVAS_TOKEN", "")


def is_configured():
    return all(credentials())


def _get_all(session, url, token, params=None):
    results = []
    while url:
        response = session.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30)
        if response.status_code == 401:
            raise CanvasError("Canvas rejected the token. Create a new access token in Canvas → Account → Settings.")
        if not response.ok:
            raise CanvasError(f"Canvas returned {response.status_code}: {response.text[:200]}")
        results.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None
    return results


def classify(assignment):
    name = assignment.get("name", "")
    types = assignment.get("submission_types") or []
    if assignment.get("is_quiz_assignment") or "online_quiz" in types or QUIZ_WORDS.search(name):
        return "Quiz"
    if TEST_WORDS.search(name):
        return "Test"
    if "discussion_topic" in types:
        return "Discussion"
    return "Assignment"


def local_due_date(due_at):
    zone = ZoneInfo(setting("JARVIS_TZ", "America/Los_Angeles"))
    return datetime.fromisoformat(due_at.replace("Z", "+00:00")).astimezone(zone).date().isoformat()


def priority_for(kind):
    return {"Test": "High", "Quiz": "High"}.get(kind, "Medium")


def course_label(course):
    return course.get("course_code") or course.get("name") or f"Course {course.get('id')}"


def sync(session=None, base_url=None, token=None):
    configured_url, configured_token = credentials()
    base_url, token = (base_url or configured_url).rstrip("/"), token or configured_token
    if not base_url or not token:
        raise CanvasError("Add CANVAS_URL and CANVAS_TOKEN to your secrets first.")
    session = session or requests.Session()
    courses = _get_all(session, f"{base_url}/api/v1/courses", token, {"enrollment_state": "active", "per_page": 100})
    summary = {"added": 0, "updated": 0, "skipped": 0, "courses": 0}
    for course in courses:
        if course.get("access_restricted_by_date"):
            continue
        summary["courses"] += 1
        assignments = _get_all(
            session,
            f"{base_url}/api/v1/courses/{course['id']}/assignments",
            token,
            {"include[]": "submission", "per_page": 100, "order_by": "due_at"},
        )
        for assignment in assignments:
            if not assignment.get("due_at") or not assignment.get("published", True):
                summary["skipped"] += 1
                continue
            kind = classify(assignment)
            submitted = (assignment.get("submission") or {}).get("workflow_state") in DONE_STATES
            outcome = db.upsert_canvas_item(
                f"{course['id']}:{assignment['id']}",
                course=course_label(course),
                title=assignment["name"],
                kind=kind,
                due_date=local_due_date(assignment["due_at"]),
                priority=priority_for(kind),
                url=assignment.get("html_url", ""),
                **({"done": 1} if submitted else {}),
            )
            summary[outcome] += 1
    db.set_setting("canvas_last_sync", db.local_now().isoformat(timespec="minutes"))
    return summary
