def test_config_exposes_rotation_and_gradient_constants():
    import config

    assert config.ROTATION in ("0", "90CW", "180", "90CCW")
    # Each gradient endpoint is a 3-tuple of ints in 0..255.
    for endpoint in (config.SCORE_GRADIENT_START, config.SCORE_GRADIENT_END):
        assert isinstance(endpoint, tuple)
        assert len(endpoint) == 3
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in endpoint)


def test_config_exposes_ble_ota_flags():
    import config

    assert isinstance(config.BLE_OTA_ENABLED, bool)
    assert isinstance(config.BLE_LISTEN_SECONDS, int) and config.BLE_LISTEN_SECONDS >= 0
    assert isinstance(config.BLE_DEVICE_NAME, str) and config.BLE_DEVICE_NAME
