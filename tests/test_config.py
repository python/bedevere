import pytest

from bedevere import config


@pytest.fixture(autouse=True)
def reset_logged_repos(monkeypatch):
    monkeypatch.setattr(config, "_logged_unknown_repos", set())


def test_cpython_gets_every_feature():
    assert config.features_for("python/cpython") == config.ALL_FEATURES


def test_unknown_python_repo_gets_policy_only():
    assert config.features_for("python/devguide") == {"policy"}


@pytest.mark.parametrize("repo", ["mariatta/devguide", "pythonista/cpython"])
def test_repo_outside_python_org_gets_nothing(repo):
    assert config.features_for(repo) == frozenset()


def test_lookup_ignores_case():
    assert config.features_for("Python/CPython") == config.ALL_FEATURES
    assert config.features_for("Python/DevGuide") == {"policy"}


def test_unknown_repo_logged_once(capfd):
    config.features_for("python/devguide")
    config.features_for("python/devguide")
    out, err = capfd.readouterr()
    assert err.count("python/devguide has no feature config") == 1


def test_repo_outside_python_org_logged_as_running_nothing(capfd):
    config.features_for("mariatta/devguide")
    out, err = capfd.readouterr()
    assert "mariatta/devguide has no feature config, running only: nothing" in err
