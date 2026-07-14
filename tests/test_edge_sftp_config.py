from edge.upload.sftp import UploadManager


class DummyDb:
    pass


def _config(sftp: dict) -> dict:
    return {"device": {"device_id": "TL-TEST"}, "sftp": sftp}


def test_incomplete_customer_sftp_is_not_an_upload_target():
    manager = UploadManager(_config({
        "enabled": True,
        "host": "headend.example",
        "username": "",
        "remote_base": "",
        "key_file": "",
        "password": "",
    }), DummyDb())

    assert manager._targets == []


def test_complete_customer_sftp_remains_available():
    manager = UploadManager(_config({
        "enabled": True,
        "host": "sftp.example",
        "username": "camera",
        "remote_base": "/incoming",
        "key_file": "/opt/timelapse/edge/keys/customer",
    }), DummyDb())

    assert len(manager._targets) == 1
    assert manager._targets[0].remote_base == "/incoming"


def test_site_look_optimizer_uses_edge_runtime_import_namespace():
    source = open("edge/ai/autonomous_optimizer.py", encoding="utf-8").read()

    assert "from ai.site_look_config_client import get_config_client" in source
    assert "from edge.ai.site_look_config_client import get_config_client" not in source
