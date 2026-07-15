from unittest.mock import MagicMock

from api.site_look_config_api import ConfigUpsert, upsert_config


def test_advanced_colour_parameters_are_forwarded_to_persistence_service():
    service = MagicMock()
    service.upsert_config.return_value = {"neutral_kelvin": 6200}
    payload = ConfigUpsert(
        level="global",
        neutral_kelvin=6200,
        warm_lab_threshold=18,
        cool_lab_threshold=-12,
        warm_kelvin_multiplier=45,
        cool_kelvin_multiplier=75,
        kelvin_min=2600,
        kelvin_max=9800,
    )

    result = upsert_config(payload, service=service)

    assert result == {"neutral_kelvin": 6200}
    service.upsert_config.assert_called_once()
    kwargs = service.upsert_config.call_args.kwargs
    assert kwargs["neutral_kelvin"] == 6200
    assert kwargs["warm_lab_threshold"] == 18
    assert kwargs["cool_kelvin_multiplier"] == 75
    assert kwargs["kelvin_min"] == 2600
    assert kwargs["kelvin_max"] == 9800
