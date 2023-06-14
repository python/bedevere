import pytest


from tests.fixtures import tmp_webhook, tmp_event_name, tmp_job_id


@pytest.mark.parametrize('tmp_event_name', ["created"], indirect=True)
async def test_success(tmp_webhook, tmp_event_name, tmp_job_id, monkeypatch):
    from bedevere import __main__ as main

    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    event_payload = {"action": "created"}
    await main.main(event_payload)


async def test_failure(tmp_webhook):
    from bedevere import __main__ as main
    """Actions will have exit code in case of errors."""

    # Missing GitHub environment variables
    event_payload = {}
    with pytest.raises(SystemExit) as exc:
        await main.main(event_payload)
    assert exc.value.code == 1
