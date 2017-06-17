import enum


@enum.unique
class StatusState(enum.Enum):
    SUCCESS = 'success'
    ERROR = 'error'
    FAILURE = 'failure'


def create_status(context, state, *, description=None, target_url=None):
    """Create the data for a status.

    The argument order is such that you can use functools.partial() to set the
    context to avoid repeatedly specifying it throughout a module.
    """
    status = {
        'context': context,
        'state': state.value,
    }
    if description is not None:
        status['description'] = description
    if target_url is not None:
        status['target_url'] = target_url

    return status


def is_trivial(issue):
    """See if an issue is labeled as trivial."""
    return any(label_data['name'] == 'trivial' for label_data in issue['labels'])
