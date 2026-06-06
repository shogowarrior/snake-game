def test_config_exposes_rotation():
    import config

    assert config.ROTATION in (0, 90, 180, 270)
