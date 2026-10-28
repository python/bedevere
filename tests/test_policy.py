from copy import deepcopy

import pytest
from gidgethub import sansio

from bedevere import __main__ as main
from bedevere import policy

APP_ID = 123
ISSUE_URL = "https://api.github.com/repos/python/cpython/issues/42"
PR_URL = "https://api.github.com/repos/python/cpython/pulls/42"
COMMENTS_URL = f"{ISSUE_URL}/comments"
LABELS_URL = f"{ISSUE_URL}/labels{{/name}}"


def make_event(kind, label, *, action="labeled", state="open", sender_type="User"):
    target = {
        "number": 42,
        "state": state,
        "labels": [{"name": label}],
        "comments_url": COMMENTS_URL,
    }
    data = {
        "action": action,
        "label": {"name": label},
        "sender": {"login": "triager", "type": sender_type},
    }
    if kind == "pull_request":
        data["pull_request"] = {**target, "url": PR_URL, "issue_url": ISSUE_URL}
    else:
        data["issue"] = {**target, "url": ISSUE_URL}
    return sansio.Event(data, event=kind, delivery_id="policy-label-delivery")


class FakeGH:
    def __init__(self, label):
        self.issue = {
            "state": "open",
            "labels": [{"name": label}],
            "comments_url": COMMENTS_URL,
            "labels_url": LABELS_URL,
        }
        self.comments = []
        self.calls = []
        self.post_error = None
        self.patch_error = None
        self.remove_label_after_post = False

    async def getitem(self, url):
        self.calls.append(("get", url))
        return deepcopy(self.issue)

    async def delete(self, url, url_vars):
        self.calls.append(("delete", sansio.format_url(url, url_vars)))
        self.issue["labels"] = [
            label for label in self.issue["labels"] if label["name"] != url_vars["name"]
        ]

    async def getiter(self, url):
        self.calls.append(("getiter", url))
        for comment in self.comments:
            yield comment

    async def post(self, url, *, data):
        self.calls.append(("post", url, data))
        if self.post_error:
            raise self.post_error
        self.comments.append(
            {"body": data["body"], "performed_via_github_app": {"id": APP_ID}}
        )
        if self.remove_label_after_post:
            self.issue["labels"] = []

    async def patch(self, url, *, data):
        self.calls.append(("patch", url, data))
        if self.patch_error:
            raise self.patch_error
        self.issue.update(data)


@pytest.fixture(autouse=True)
def app_id(monkeypatch):
    monkeypatch.setenv("GH_APP_ID", str(APP_ID))


@pytest.mark.parametrize(
    "kind, label, message",
    [
        ("issues", policy.COMMENT_LABEL, policy.ISSUE_COMMENT_MESSAGE),
        ("issues", policy.CLOSE_LABEL, policy.ISSUE_CLOSE_MESSAGE),
        ("pull_request", policy.COMMENT_LABEL, policy.PR_COMMENT_MESSAGE),
        ("pull_request", policy.CLOSE_LABEL, policy.PR_CLOSE_MESSAGE),
    ],
)
async def test_policy_action_through_main_router(kind, label, message):
    event = make_event(kind, label)
    gh = FakeGH(label)

    await main.router.dispatch(event, gh)

    assert gh.calls[0] == ("get", ISSUE_URL)
    assert gh.calls[1] == ("getiter", COMMENTS_URL)
    assert gh.comments[0]["body"] == f"{message}\n\n<!-- bedevere: {label} -->"
    assert gh.calls[2] == ("post", COMMENTS_URL, {"body": gh.comments[0]["body"]})
    if label == policy.CLOSE_LABEL:
        close_url = PR_URL if kind == "pull_request" else ISSUE_URL
        data = {"state": "closed"}
        if kind == "issues":
            data["state_reason"] = "not_planned"
        assert gh.calls[3:] == [("get", ISSUE_URL), ("patch", close_url, data)]
    else:
        assert len(gh.calls) == 3
        assert gh.issue["state"] == "open"


async def test_unrelated_label():
    gh = FakeGH("type-bug")
    await policy.router.dispatch(make_event("issues", "type-bug"), gh)
    assert not gh.calls


@pytest.mark.parametrize("action", ["opened", "reopened", "synchronize", "unlabeled"])
async def test_other_actions_do_not_trigger_closure(action):
    gh = FakeGH(policy.CLOSE_LABEL)
    event = make_event("pull_request", policy.CLOSE_LABEL, action=action)
    await policy.router.dispatch(event, gh)
    assert not gh.calls


async def test_bot_applied_label():
    gh = FakeGH(policy.CLOSE_LABEL)
    event = make_event("issues", policy.CLOSE_LABEL, sender_type="Bot")
    await policy.router.dispatch(event, gh)
    assert not gh.calls


@pytest.mark.parametrize("kind", ["issues", "pull_request"])
async def test_already_closed_at_labeling(kind):
    gh = FakeGH(policy.CLOSE_LABEL)
    event = make_event(kind, policy.CLOSE_LABEL, state="closed")
    await policy.router.dispatch(event, gh)
    assert not gh.calls


@pytest.mark.parametrize("state", ["open", "closed"])
async def test_removed_label_or_closed_target(state):
    gh = FakeGH(policy.CLOSE_LABEL)
    gh.issue["state"] = state
    if state == "open":
        gh.issue["labels"] = []
    await policy.router.dispatch(make_event("issues", policy.CLOSE_LABEL), gh)
    assert gh.calls == [("get", ISSUE_URL)]


async def test_removed_label_during_comment():
    gh = FakeGH(policy.CLOSE_LABEL)
    gh.remove_label_after_post = True
    await policy.router.dispatch(make_event("issues", policy.CLOSE_LABEL), gh)
    assert len(gh.comments) == 1
    assert gh.issue["state"] == "open"
    assert not any(call[0] == "patch" for call in gh.calls)


@pytest.mark.parametrize("label", [policy.COMMENT_LABEL, policy.CLOSE_LABEL])
async def test_repeated_delivery(label):
    event = make_event("issues", label)
    gh = FakeGH(label)
    await policy.router.dispatch(event, gh)
    await policy.router.dispatch(event, gh)
    assert len(gh.comments) == 1
    assert sum(call[0] == "patch" for call in gh.calls) == (label == policy.CLOSE_LABEL)


@pytest.mark.parametrize("kind", ["issues", "pull_request"])
async def test_retry_after_close_failed(kind):
    event = make_event(kind, policy.CLOSE_LABEL)
    gh = FakeGH(policy.CLOSE_LABEL)
    gh.patch_error = RuntimeError("closure failed")
    with pytest.raises(RuntimeError, match="closure failed"):
        await policy.router.dispatch(event, gh)

    gh.patch_error = None
    await policy.router.dispatch(event, gh)
    assert len(gh.comments) == 1
    assert gh.issue["state"] == "closed"


async def test_comment_failure_does_not_close():
    gh = FakeGH(policy.CLOSE_LABEL)
    gh.post_error = RuntimeError("comment failed")
    with pytest.raises(RuntimeError, match="comment failed"):
        await policy.router.dispatch(make_event("issues", policy.CLOSE_LABEL), gh)
    assert gh.issue["state"] == "open"
    assert not any(call[0] == "patch" for call in gh.calls)


@pytest.mark.parametrize("app", [None, {"id": APP_ID + 1}])
async def test_other_authors_cannot_suppress_message(app):
    gh = FakeGH(policy.COMMENT_LABEL)
    gh.comments.append(
        {
            "body": f"<!-- bedevere: {policy.COMMENT_LABEL} -->",
            "performed_via_github_app": app,
        }
    )
    await policy.router.dispatch(make_event("issues", policy.COMMENT_LABEL), gh)
    assert len(gh.comments) == 2
    assert policy.ISSUE_COMMENT_MESSAGE in gh.comments[-1]["body"]


async def test_comment_then_close():
    gh = FakeGH(policy.COMMENT_LABEL)
    await policy.router.dispatch(make_event("issues", policy.COMMENT_LABEL), gh)
    assert not any(call[0] == "delete" for call in gh.calls)
    gh.issue["labels"].append({"name": policy.CLOSE_LABEL})
    await policy.router.dispatch(make_event("issues", policy.CLOSE_LABEL), gh)
    assert len(gh.comments) == 2
    assert policy.ISSUE_COMMENT_MESSAGE in gh.comments[0]["body"]
    assert policy.ISSUE_CLOSE_MESSAGE in gh.comments[1]["body"]
    assert gh.issue["state"] == "closed"
    assert gh.issue["labels"] == [{"name": policy.CLOSE_LABEL}]


@pytest.mark.parametrize("kind", ["issues", "pull_request"])
async def test_close_label_replaces_comment_label(kind):
    gh = FakeGH(policy.COMMENT_LABEL)
    gh.issue["labels"].append({"name": policy.CLOSE_LABEL})
    await policy.router.dispatch(make_event(kind, policy.CLOSE_LABEL), gh)

    removed_url = f"{ISSUE_URL}/labels/{policy.COMMENT_LABEL}"
    assert gh.calls[:2] == [("get", ISSUE_URL), ("delete", removed_url)]
    assert gh.issue["labels"] == [{"name": policy.CLOSE_LABEL}]
    assert gh.issue["state"] == "closed"
    assert len(gh.comments) == 1
    assert gh.comments[0]["body"].endswith(f"<!-- bedevere: {policy.CLOSE_LABEL} -->")


@pytest.mark.parametrize("kind", ["issues", "pull_request"])
async def test_comment_label_defers_to_close_label(kind):
    gh = FakeGH(policy.CLOSE_LABEL)
    gh.issue["labels"].append({"name": policy.COMMENT_LABEL})
    await policy.router.dispatch(make_event(kind, policy.COMMENT_LABEL), gh)

    assert gh.calls == [("get", ISSUE_URL)]
    assert not gh.comments
    assert gh.issue["state"] == "open"
    assert len(gh.issue["labels"]) == 2


@pytest.mark.parametrize("kind", ["issues", "pull_request"])
@pytest.mark.parametrize("first", [policy.COMMENT_LABEL, policy.CLOSE_LABEL])
async def test_both_labels_added_together(kind, first):
    gh = FakeGH(policy.COMMENT_LABEL)
    gh.issue["labels"].append({"name": policy.CLOSE_LABEL})
    second = policy.CLOSE_LABEL if first == policy.COMMENT_LABEL else policy.COMMENT_LABEL
    await policy.router.dispatch(make_event(kind, first), gh)
    await policy.router.dispatch(make_event(kind, second), gh)

    assert gh.issue["labels"] == [{"name": policy.CLOSE_LABEL}]
    assert gh.issue["state"] == "closed"
    assert len(gh.comments) == 1
    assert gh.comments[0]["body"].endswith(f"<!-- bedevere: {policy.CLOSE_LABEL} -->")
    assert sum(call[0] == "delete" for call in gh.calls) == 1


async def test_only_the_other_policy_label_is_removed():
    gh = FakeGH("type-bug")
    gh.issue["labels"].append({"name": policy.COMMENT_LABEL})
    await policy.router.dispatch(make_event("issues", policy.COMMENT_LABEL), gh)
    assert not any(call[0] == "delete" for call in gh.calls)
    assert gh.issue["labels"] == [{"name": "type-bug"}, {"name": policy.COMMENT_LABEL}]
