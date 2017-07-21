import email.message
import email.utils
import os

from gidgethub import routing


router = routing.Router()

ALLOWED_BRANCHES = ["2.7", "3.5", "3.6", "master"]
SENDER = os.environ.get("SENDER_EMAIL", "sender@example.com")
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", "recipient@example.com")


def get_diff_stat(commit):
    files = {
        "A": commit["added"],
        "D": commit["removed"],
        "M": commit["modified"],
    }
    result = []
    for key, file_list in files.items():
        if file_list:
            result.append("\n".join(f"{key} {f}" for f in file_list))
    return "\n".join(result)


def build_message(commit, **kwargs):
    branch = kwargs.get("branch")
    diff_stat = kwargs.get("diff_stat")
    unified_diff = kwargs.get("unified_diff")
    template = f"""\
{commit["url"]}
commit: {commit["id"]}
branch: {branch}
author: {commit["author"]["name"]} <{commit["author"]["email"]}>
committer: {commit["committer"]["name"]} <{commit["committer"]["email"]}>
date: {commit["timestamp"]}
summary:
{commit["message"]}
files:
{diff_stat}
{unified_diff}
"""
    msg = email.message.EmailMessage()
    # TODO: Use committer name if it"s not GitHub as sender name
    msg["From"] = email.utils.formataddr((commit["committer"]["name"], SENDER))
    msg["To"] = RECIPIENT
    msg["Subject"] = commit["message"].split("\n")[0]
    msg.set_content(template)
    return msg


@router.register("push")
async def send_email(event, gh, *args, **kwargs):
    if "commits" not in event.data and len(event.data["commits"]) == 0:
        return
    branch_name = event.data["ref"].split("/").pop()
    if branch_name not in ALLOWED_BRANCHES:
        return
    commit = event.data["commits"][0]
    unified_diff = await gh.getitem(f"commit['url'].diff")
    diff_stat = get_diff_stat(commit)
    mail = build_message(commit, branch=branch_name, diff_stat=diff_stat,
                         unified_diff=unified_diff)
    # TODO: Send email.
    return "Ok"
