from apps.desktop import desktop_window_title


def test_cinema_preview_has_short_identifiable_title():
    assert desktop_window_title(
        'PTTI-Video-First-R4-Preview.exe', 'long legacy title', 'ae802c253cb4ca10'
    ) == 'PTTI Cinema · ae802c253c'


def test_cinema_preview_unknown_build_is_explicit():
    assert desktop_window_title(
        'PTTI-Video-First-R4-Preview.exe', 'long legacy title', None
    ) == 'PTTI Cinema · Preview'


def test_stable_window_identity_is_preserved():
    assert desktop_window_title('PTTI.exe', 'stable title', '1234') == 'stable title'
