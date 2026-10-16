import pytest

from linecat.cdms import _decode_q_token


@pytest.mark.parametrize(
    "token, expected",
    [("00", 0), ("07", 7), ("99", 99), ("-3", -3), ("A0", 100), ("B5", 115), ("a0", -10), ("c7", -37)],
)
def test_decode_q_token(token, expected):
    assert _decode_q_token(token) == expected
