"""The part sequence must resume, settle, and never double-send an answer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import loopx.extensions.lark.manager_reply_parts as parts_module
from loopx.extensions.lark.manager_reply_parts import (
    PART_DELIVERY_COMPLETE_KEY,
    PART_DELIVERY_COMPLETION_UNVERIFIED,
    PART_DELIVERY_INCOMPLETE,
    PART_DELIVERY_VERIFIED_KEY,
    completed_part_delivery_receipt,
    deliver_manager_reply_parts,
    part_delivery_incomplete_reason,
    plan_manager_reply_parts,
)


BODY = "\n".join(f"- 条目 {index} " + "x" * 60 for index in range(1, 200))


@pytest.fixture
def delivery(tmp_path: Path):
    """A fake provider boundary plus the durable state a retry would reload."""

    state: dict = {}
    writes: list[dict] = []
    sends: list[str] = []

    def install(*, fail_at: int | None = None, verified: bool = True):
        def fake_reply(**kwargs):
            sends.append(kwargs["text"])
            if fail_at is not None and len(sends) == fail_at:
                return {"ok": False, "status": "reply_failed", "idempotency_key": None}
            return {
                "ok": True,
                "status": "sent_verified",
                "idempotency_key": f"sha256:part-{len(sends)}",
                "content_format": kwargs.get("content_format", "text"),
                "external_write_performed": True,
                "verification_performed": True,
                "reply_verified": verified,
            }

        return fake_reply

    def deliver(parts: list[str]):
        return deliver_manager_reply_parts(
            parts=parts,
            delivery_state=state,
            delivery_path=tmp_path / "delivery.json",
            write_delivery=lambda path, payload: writes.append(
                json.loads(json.dumps(payload))
            ),
            reply_runner=object(),
            root=tmp_path,
            config_path=tmp_path / "config.json",
            message_id="om_fixture",
            content_format="text",
        )

    return {
        "state": state,
        "writes": writes,
        "sends": sends,
        "install": install,
        "deliver": deliver,
    }


def test_a_partially_accepted_sequence_resumes_at_the_first_unsent_part(
    monkeypatch, delivery
):
    parts, _ = plan_manager_reply_parts(BODY)
    assert len(parts) > 3

    monkeypatch.setattr(
        parts_module, "reply_lark_event_inbox", delivery["install"](fail_at=3)
    )
    assert delivery["deliver"](parts) is None
    assert delivery["state"]["delivery_parts_sent"] == 2

    accepted = list(delivery["sends"])
    monkeypatch.setattr(parts_module, "reply_lark_event_inbox", delivery["install"]())
    assert delivery["deliver"](parts)["ok"] is True

    # The retry starts at the first part the provider never accepted and never
    # repeats a part the reader already has.
    assert delivery["sends"][len(accepted) :][0] == parts[2]
    assert delivery["state"]["delivery_parts_sent"] == len(parts)
    assert delivery["state"][PART_DELIVERY_COMPLETE_KEY] is True
    assert delivery["state"][PART_DELIVERY_VERIFIED_KEY] is True
    assert delivery["state"]["reply_idempotency_key"].startswith("sha256:")


def test_an_already_delivered_sequence_settles_from_the_record(monkeypatch, delivery):
    parts, _ = plan_manager_reply_parts(BODY)
    delivery["state"].update(
        delivery_part_count=len(parts),
        delivery_parts_sent=len(parts),
        reply_idempotency_key="sha256:last-part",
        **{
            PART_DELIVERY_COMPLETE_KEY: True,
            PART_DELIVERY_VERIFIED_KEY: True,
        },
    )
    # The provider must not be asked to send anything again.
    monkeypatch.setattr(parts_module, "reply_lark_event_inbox", delivery["install"]())

    receipt = delivery["deliver"](parts)

    assert delivery["sends"] == []
    assert receipt == {
        "ok": True,
        "status": "sent_verified",
        "idempotency_key": "sha256:last-part",
        "content_format": "text",
        "external_write_performed": True,
        "verification_performed": True,
        "reply_verified": True,
        "part_delivery_reused": True,
    }


def test_a_complete_but_unverified_record_reports_its_own_reason(monkeypatch, delivery):
    parts, _ = plan_manager_reply_parts(BODY)
    delivery["state"].update(
        delivery_part_count=len(parts),
        delivery_parts_sent=len(parts),
        reply_idempotency_key="sha256:last-part",
        **{PART_DELIVERY_COMPLETE_KEY: True},
    )
    monkeypatch.setattr(parts_module, "reply_lark_event_inbox", delivery["install"]())

    assert delivery["deliver"](parts) is None
    # Nothing is re-sent, and the reason says why the record cannot settle.
    assert delivery["sends"] == []
    assert (
        part_delivery_incomplete_reason(delivery["state"])
        == PART_DELIVERY_COMPLETION_UNVERIFIED
    )


def test_a_changed_split_restarts_instead_of_resuming_mid_answer(monkeypatch, delivery):
    parts, _ = plan_manager_reply_parts(BODY)
    delivery["state"].update(
        delivery_part_count=len(parts) + 1,
        delivery_parts_sent=len(parts) + 1,
        reply_idempotency_key="sha256:another-split",
        **{
            PART_DELIVERY_COMPLETE_KEY: True,
            PART_DELIVERY_VERIFIED_KEY: True,
        },
    )
    monkeypatch.setattr(parts_module, "reply_lark_event_inbox", delivery["install"]())

    assert delivery["deliver"](parts)["ok"] is True

    assert delivery["sends"][0] == parts[0]
    assert delivery["state"]["delivery_part_count"] == len(parts)
    assert delivery["state"]["delivery_parts_sent"] == len(parts)


def test_an_unkeyed_or_unfinished_record_never_claims_verification():
    assert (
        completed_part_delivery_receipt(
            {
                PART_DELIVERY_COMPLETE_KEY: True,
                PART_DELIVERY_VERIFIED_KEY: True,
                "reply_idempotency_key": "reply-fixture",
            }
        )
        is None
    )
    assert (
        completed_part_delivery_receipt(
            {PART_DELIVERY_COMPLETE_KEY: True, "reply_idempotency_key": "sha256:x"}
        )
        is None
    )
    assert part_delivery_incomplete_reason({}) == PART_DELIVERY_INCOMPLETE


def test_a_verified_part_with_pending_cleanup_is_never_sent_twice(monkeypatch, delivery):
    """``ok`` also requires the reaction cleanup, which must not re-send a part.

    A part the provider already read back is on the channel; stopping the
    sequence on a pending cleanup makes the retry post the same text again.
    """

    parts, _ = plan_manager_reply_parts(BODY)

    def cleanup_pending_then_ok(**kwargs):
        delivery["sends"].append(kwargs["text"])
        index = len(delivery["sends"])
        facts = {
            "external_write_performed": True,
            "verification_performed": True,
            "reply_verified": True,
        }
        if index == 1:
            return {
                "ok": False,
                "status": "sent_verified_cleanup_pending",
                "idempotency_key": "sha256:part-1",
                **facts,
            }
        return {
            "ok": True,
            "status": "sent_verified",
            "idempotency_key": f"sha256:part-{index}",
            **facts,
        }

    monkeypatch.setattr(
        parts_module, "reply_lark_event_inbox", cleanup_pending_then_ok
    )

    receipt = delivery["deliver"](parts)

    assert receipt["ok"] is True
    assert delivery["sends"].count(parts[0]) == 1
    assert delivery["sends"][1] == parts[1]
    assert delivery["state"]["delivery_parts_sent"] == len(parts)
