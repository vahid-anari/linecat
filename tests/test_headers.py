from linecat.headers import TABLE_FORMATS, filter_label, pretty_header, table_alignment, table_background


def test_pretty_header():
    assert pretty_header("Frequency (MHz)") == "Frequency<br>(MHz)"
    assert pretty_header("tau (s)") == "&tau;<br>(s)"
    assert pretty_header("U-S E (cm^-1)") == "U-S<br>Energy (cm<sup>-1</sup>)"
    assert pretty_header("L-S K_a") == "L-S<br>K<sub>a</sub>"
    assert pretty_header("U-S J") == "U-S<br>J"
    assert pretty_header("QNFMT") == "QNFMT"


def test_filter_label_and_background():
    assert filter_label("Omega") == r"\Omega"
    assert filter_label("J") == "J"
    assert table_background("U-S J") == "tan"
    assert table_background("L-S E (K)") == "lightskyblue"
    assert table_background("Species") is None
    assert table_alignment("Species") == "center"
    assert table_alignment("U-S Sym") == "center"
    assert table_alignment("L-S Parity") == "center"
    assert table_alignment("U-S J") == "right"
    assert table_alignment("Degrees of Freedom (DR)") == "right"


def test_table_formats_accept_strings():
    assert TABLE_FORMATS["Frequency (MHz)"]("1371.38") == "1,371.380"
    assert TABLE_FORMATS["tau (s)"]("1.246e11") == "1.246×10<sup>11</sup>"
