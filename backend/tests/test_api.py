import csv
import io
import json
import zipfile
from datetime import date, timedelta

import pytest

from .conftest import SAMPLE_IDS, sample_text


def create(client, sid="startup-standup", **kw):
    body = {"title": "Test meeting", "date": "2026-03-11", "transcript": sample_text(sid), "attendees": "Priya, Marcus <marcus@x.io>, Dana, Leo", **kw}
    r = client.post("/api/meetings", json=body)
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_health_reports_demo_provider(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["llm"]["provider"] == "demo" and h["whisper"]["model"] == "base"
    assert "Nothing leaves" in h["privacy"]


@pytest.mark.parametrize("sid", SAMPLE_IDS)
def test_end_to_end_each_sample(client, sid):
    mid = create(client, sid)
    m = client.get(f"/api/meetings/{mid}").json()
    assert m["status"] == "done", m.get("error")
    assert m["provider"] == "demo" and m["tasks"] and m["emails"] and m["decisions"]
    assert m["emails"][0]["kind"] == "recap"
    owners = {t["owner"] for t in m["tasks"] if t["owner"]}
    assert {e["recipient"] for e in m["emails"] if e["kind"] == "owner"} == owners
    assert all(t["verified"] for t in m["tasks"])
    assert m["segments"][0]["speaker"]  # speaker prefixes parsed


def test_deadlines_resolved_against_meeting_date(client):
    m = client.get(f"/api/meetings/{create(client)}").json()
    by = {t["title"]: t for t in m["tasks"]}
    safari = by["Fix Safari password-field focus bug"]
    assert safari["deadline_raw"] == "by tomorrow" and safari["deadline_resolved"] == "2026-03-12"
    legal = by["Send refund wording to legal and chase for review"]
    assert legal["deadline_resolved"] == "2026-03-13"
    readme = by["Update the out-of-date README"]
    assert readme["needs_clarification"] and "No owner stated" in readme["clarification_reasons"]


def test_validation_and_errors(client):
    r = client.post("/api/meetings", json={"transcript": "too short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "transcript_too_short"
    assert client.post("/api/meetings", json={}).json()["error"]["code"] == "validation_error"
    assert client.get("/api/meetings/nope").json()["error"]["code"] == "meeting_not_found"
    assert client.get("/api/health").status_code == 200


def test_upload_validation(client):
    r = client.post("/api/meetings/audio", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file_type"
    r = client.post("/api/meetings/audio", files={"file": ("a.mp3", b"", "audio/mpeg")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "empty_file"


def test_upload_too_large(client, monkeypatch):
    from app import config

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    config.reset_settings()
    r = client.post("/api/meetings/audio", files={"file": ("a.wav", b"0" * (1024 * 1024 + 10), "audio/wav")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_corrupt_audio_fails_gracefully_and_cleans_up(client):
    r = client.post("/api/meetings/audio", files={"file": ("a.mp3", b"this is not audio" * 100, "audio/mpeg")})
    assert r.status_code == 202
    m = client.get(f"/api/meetings/{r.json()['id']}").json()
    assert m["status"] == "error" and m["error"]


def test_kanban_move_persists_and_edit(client):
    m = client.get(f"/api/meetings/{create(client)}").json()
    t = m["tasks"][0]
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["position"] == 0
    r = client.patch(f"/api/tasks/{t['id']}", json={"owner": "Zed", "priority": "low", "deadline_resolved": "2026-04-01", "title": "Renamed"})
    j = r.json()
    assert (j["owner"], j["priority"], j["deadline_resolved"], j["title"]) == ("Zed", "low", "2026-04-01", "Renamed")
    again = client.get(f"/api/meetings/{m['id']}").json()
    assert next(x for x in again["tasks"] if x["id"] == t["id"])["status"] == "in_progress"
    r = client.patch(f"/api/tasks/{t['id']}", json={"clear_owner": True, "clear_deadline": True})
    assert r.json()["owner"] is None and r.json()["needs_clarification"]
    assert client.patch(f"/api/tasks/{t['id']}", json={"priority": "urgent"}).status_code == 422


def test_task_create_delete_and_reorder(client):
    mid = create(client)
    r = client.post("/api/tasks", json={"meeting_id": mid, "title": "Manual card", "owner": "Leo", "deadline_resolved": "2026-03-20"})
    assert r.status_code == 201 and r.json()["manual"] and not r.json()["needs_clarification"]
    tid = r.json()["id"]
    r = client.patch(f"/api/tasks/{tid}", json={"position": 0})
    assert r.json()["position"] == 0
    todo = [t for t in client.get(f"/api/meetings/{mid}").json()["tasks"] if t["status"] == "todo"]
    assert sorted(t["position"] for t in todo) == list(range(len(todo)))
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.delete(f"/api/tasks/{tid}").status_code == 404
    assert client.post("/api/tasks", json={"meeting_id": "zzz", "title": "x"}).status_code == 404


def test_history_rename_delete_dashboard(client):
    a, b = create(client), create(client, "project-retro")
    lst = client.get("/api/meetings").json()
    assert {x["id"] for x in lst} == {a, b}
    assert client.patch(f"/api/meetings/{a}", json={"title": "Renamed!"}).json()["title"] == "Renamed!"
    d = client.get("/api/dashboard").json()
    assert d["meetings"] == 2 and d["open_tasks"] >= 8 and "Unassigned" in d["workload"]
    t = client.get(f"/api/meetings/{a}").json()["tasks"][0]
    client.patch(f"/api/tasks/{t['id']}", json={"status": "done"})
    assert client.get("/api/dashboard").json()["open_tasks"] == d["open_tasks"] - 1
    assert client.delete(f"/api/meetings/{a}").status_code == 204
    assert client.get(f"/api/meetings/{a}").status_code == 404
    assert client.get("/api/dashboard").json()["meetings"] == 1


def test_overdue_counted(client):
    mid = create(client)
    before = client.get("/api/dashboard").json()["overdue_tasks"]  # sample dates are in 2026-03, so some are already overdue
    client.post("/api/tasks", json={"meeting_id": mid, "title": "Late", "deadline_resolved": (date.today() - timedelta(days=3)).isoformat()})
    assert client.get("/api/dashboard").json()["overdue_tasks"] == before + 1


def test_emails_tone_regenerate_edit(client):
    mid = create(client)
    emails = client.post(f"/api/meetings/{mid}/emails?tone=concise").json()
    recap = next(e for e in emails if e["kind"] == "recap")
    assert recap["tone"] == "concise" and "Meeting recap:" in recap["body_text"] and "<table" in recap["body_html"]
    marcus = next(e for e in emails if e["recipient"] == "Marcus")
    assert marcus["to_addr"] == "marcus@x.io" and "Safari" in marcus["body_text"] and "README" not in marcus["body_text"]
    r = client.patch(f"/api/emails/{marcus['id']}", json={"subject": "Hi <b>", "body_text": "Edited <script>x</script>"}).json()
    assert r["edited"] and "<script>" not in r["body_html"]
    r = client.post(f"/api/emails/{marcus['id']}/regenerate?tone=professional").json()
    assert not r["edited"] and r["tone"] == "professional" and r["body_text"].startswith("Hello Marcus,")
    assert client.post(f"/api/meetings/{mid}/emails?tone=rude").status_code == 422


def test_exports_all_formats(client):
    mid = create(client)
    base = f"/api/meetings/{mid}/export"
    md = client.get(f"{base}/md")
    assert md.status_code == 200 and "## Action items" in md.text and "attachment" in md.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(client.get(f"{base}/csv").text)))
    assert len(rows) == 6 and rows[0]["deadline"] == "2026-03-12"
    ics = client.get(f"{base}/ics").text
    assert ics.startswith("BEGIN:VCALENDAR") and ics.count("BEGIN:VEVENT") == sum(1 for r in rows if r["deadline"])
    assert "DTSTART;VALUE=DATE:20260312" in ics and "\r\n" in ics
    assert "*" in client.get(f"{base}/slack").text
    assert json.loads(client.get(f"{base}/json").text)["title"] == "Test meeting"
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{base}/zip").content))
    assert len(z.namelist()) == 7
    assert client.get(f"{base}/pdf").status_code == 404
    page = client.get(f"/m/{mid}")
    assert page.status_code == 200 and "Safari" in page.text and "default-src 'none'" in page.headers["content-security-policy"]


def test_xss_escaped_in_shared_report_and_csv_injection(client):
    mid = create(client, title="<img src=x onerror=alert(1)>")
    client.post("/api/tasks", json={"meeting_id": mid, "title": "=HYPERLINK(\"http://evil\")<script>alert(1)</script>"})
    page = client.get(f"/m/{mid}").text
    assert "<img src=x" not in page and "<script>alert" not in page
    assert "'=HYPERLINK" in client.get(f"/api/meetings/{mid}/export/csv").text


def test_sse_progress_and_samples(client):
    mid = create(client)
    with client.stream("GET", f"/api/meetings/{mid}/progress") as r:
        body = "".join(r.iter_text())
    assert '"status": "done"' in body
    s = client.get("/api/samples").json()
    assert len(s) == 3
    full = client.get(f"/api/samples/{s[0]['id']}").json()
    assert len(full["transcript"].split()) >= 300
    assert client.get("/api/samples/nope").status_code == 404


def test_attendee_names_with_non_english_text(client):
    r = client.post("/api/meetings", json={"title": "Réunion", "transcript": "Ana: Nous devons envoyer le rapport. Je vais l'envoyer demain.\nLuc: D'accord, merci beaucoup pour la réunion."})
    assert r.status_code == 202
    assert client.get(f"/api/meetings/{r.json()['id']}").json()["status"] == "done"


def test_audio_pipeline_with_mocked_whisper(client, monkeypatch):
    from app.services import pipeline

    def fake(path):
        assert path.exists()
        return {"text": "x", "language": "en", "duration": 9.0, "segments": [
            {"start": 0.0, "end": 4.0, "text": "Okay so Priya will send the refund wording to legal by Friday."},
            {"start": 4.0, "end": 8.0, "text": "We decided to go with Postgres for launch."}]}

    monkeypatch.setattr(pipeline, "transcribe_file", fake)
    r = client.post("/api/meetings/audio", data={"title": "Audio", "date": "2026-03-11"}, files={"file": ("m.mp3", b"fakebytes" * 200, "audio/mpeg")})
    assert r.status_code == 202
    m = client.get(f"/api/meetings/{r.json()['id']}").json()
    assert m["status"] == "done" and m["source"] == "audio" and m["language"] == "en"
    assert m["segments"][0]["start"] == 0.0 and m["segments"][0]["speaker"] is None  # no hallucinated speakers
    assert m["decisions"]
