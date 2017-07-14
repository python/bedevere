from bedevere import util


def test_StatusState():
    assert util.StatusState.SUCCESS.value == 'success'
    assert util.StatusState.ERROR.value == 'error'
    assert util.StatusState.FAILURE.value == 'failure'


class TestCreateStatus:

    def test_simple_case(self):
        expected = {'state': 'success', 'context': 'me'}
        assert util.create_status('me', util.StatusState.SUCCESS) == expected

    def test_with_description(self):
        expected = {'state': 'error', 'context': 'me', 'description': 'desc'}
        status = util.create_status('me', util.StatusState.ERROR,
                                    description='desc')
        assert status == expected

    def test_with_target_url(self):
        expected = {'state': 'failure', 'context': 'me',
                    'target_url': 'https://devguide.python.org'}
        status = util.create_status('me', util.StatusState.FAILURE,
                                    target_url='https://devguide.python.org')
        assert status == expected

    def test_with_everything(self):
        expected = {'state': 'failure', 'context': 'me',
                    'description': 'desc',
                    'target_url': 'https://devguide.python.org'}
        status = util.create_status('me', util.StatusState.FAILURE,
                                    description='desc',
                                    target_url='https://devguide.python.org')
        assert status == expected


def test_skip():
    issue = {'labels': [{'name': 'CLA signed'}, {'name': 'skip something'}]}
    assert util.skip("something", issue)

    issue = {'labels': [{'name': 'CLA signed'}]}
    assert not util.skip("something", issue)
