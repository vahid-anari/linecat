"""Frequency-range selector with unit conversion."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout

from sciwidgets.params import NumericLineEdit

from linecat.widgets import GROUPBOX_MARGIN, create_button, create_combo, create_label


class FrequencyRange:
    """
    Widget for selecting and converting frequency ranges across multiple units.

    Maintains an internal frequency range in MHz, updates the UI inputs when
    units change, and converts values to and from MHz for display and callbacks.

    Parameters
    ----------
    callback_func : callable
        Function to invoke with the updated frequency range [min_MHz, max_MHz].

    Attributes
    ----------
    range_value : list of float
        Current frequency range in MHz: [min, max].
    units_dict : dict of str → float
        Mapping of unit labels to their conversion factors into MHz.
    unit : str
        Last valid unit label (used to revert the combo on invalid input).
    from_value : NumericLineEdit
        Input widget for the lower‐bound value.
    to_value : NumericLineEdit
        Input widget for the upper‐bound value.
    unit_combo : QComboBox
        Dropdown for selecting display units.
    apply_button : QPushButton
        Button that applies the new range when clicked.
    layout : QVBoxLayout
        Container layout holding all of the widget’s UI elements.
    """

    def __init__(self, callback_func):
        """
        Initialize the frequency-range selector widget.

        Parameters
        ----------
        callback_func : callable
            Function to invoke with the updated frequency range [min_MHz, max_MHz].

        Returns
        -------
        None
        """
        self.callback_func = callback_func
        self.range_value = [0.0, 1e10]

        c = 2.99792458e8  # speed of light in m/s
        self.units_dict = {
            'Hz': 1e-6, 'KHz': 1e-3, 'MHz': 1.0, 'GHz': 1e3,
            'THz': 1e6, 'Å': c * 1e4, 'nm': c * 1e3,
            'μm': c, 'mm': c * 1e-3, 'm': c * 1e-6,
        }
        self.unit = 'MHz'
        self.from_value = self._make_line_edit()
        self.to_value = self._make_line_edit()
        unit_layout, self.unit_combo = create_combo(
            'Frequency Unit',
            items=list(self.units_dict.keys()),
            item=self.unit,
        )
        self.apply_button = create_button('Apply', self.update_range)

        self.groupbox = QGroupBox('Frequency Range')
        self.layout = QVBoxLayout(self.groupbox)
        self.layout.setContentsMargins(*GROUPBOX_MARGIN)
        self.layout.addStretch()
        self.layout.addLayout(self._labeled('From', self.from_value))
        self.layout.addLayout(self._labeled('To', self.to_value))
        self.layout.addLayout(unit_layout)
        self.layout.addWidget(self.apply_button, alignment=Qt.AlignHCenter)
        self.layout.addStretch()

    @staticmethod
    def _make_line_edit():
        return NumericLineEdit(0.0, val_fmt='{:.3f}', min_limit=0.0, place_holder_text='e.g. 123.45')

    @staticmethod
    def _labeled(text, widget):
        layout = QHBoxLayout()
        layout.addWidget(create_label(text, 'Right'))
        layout.addWidget(widget)
        return layout

    def _get_conversion_factor(self):
        """
        Get the conversion factor from the selected unit to MHz.

        Returns
        -------
        float
            Multiplicative factor for converting between the current unit and MHz.
        """
        return self.units_dict.get(self.unit_combo.currentText(), 1.0)

    def _unit_has_Hz(self):
        """
        Determine if the current unit label includes 'Hz'.

        Returns
        -------
        bool
            True if 'Hz' is in the selected unit label, False otherwise.
        """
        return 'Hz' in self.unit_combo.currentText()

    def _convert_to_mhz(self, value):
        """
        Convert an input value from the selected unit to MHz.

        Parameters
        ----------
        value : float
            Value in the currently selected display units.

        Returns
        -------
        float
            Converted value in MHz.
            If the unit is not a frequency (reciprocal units) and the input is zero,
            returns infinity.
        """
        factor = self._get_conversion_factor()
        if self._unit_has_Hz():
            return factor * value
        if value == 0:
            return float('inf')
        return factor / value

    def _convert_from_mhz(self, value):
        """
        Convert a frequency in MHz to the selected display unit.

        Parameters
        ----------
        value : float
            Frequency in MHz.

        Returns
        -------
        float
            Value in the currently selected display units.
            If the unit is not a frequency (reciprocal units) and the input is zero,
            returns infinity.
        """
        factor = self._get_conversion_factor()
        if self._unit_has_Hz():
            return value / factor
        if value == 0:
            return float('inf')
        return factor / value

    def _get_new_range(self):
        """
        Read UI inputs, convert them to MHz, and return ordered bounds.

        Returns
        -------
        tuple of float
            A 2-tuple (min_MHz, max_MHz) with the lower and upper frequency bounds in MHz.
        """
        low = self._convert_to_mhz(self.from_value.get_value())
        high = self._convert_to_mhz(self.to_value.get_value())
        if self._unit_has_Hz():
            return low, high
        return high, low

    def _set_line_edit_range(self):
        """
        Update UI inputs to reflect the internal frequency range in display units.

        Converts the stored `range_value` (in MHz) into the currently selected units
        and updates the 'From' and 'To' NumericLineEdit widgets accordingly, handling
        reciprocal units as needed.

        Returns
        -------
        None
        """
        mn = self._convert_from_mhz(self.range_value[0])
        mx = self._convert_from_mhz(self.range_value[1])
        if self._unit_has_Hz():
            self.from_value.set_value(mn)
            self.to_value.set_value(mx)
        else:
            self.from_value.set_value(mx)
            self.to_value.set_value(mn)

    def reset(self):
        """Back to the full range (0 to 1e10 MHz) in MHz, without calling back."""
        self.unit = 'MHz'
        self.unit_combo.setCurrentText(self.unit)
        self.set_range(0.0, 1e10)

    def set_range(self, min_mhz, max_mhz):
        """Show a range (in MHz) in the fields without calling back."""
        self.range_value = [float(min_mhz), float(max_mhz)]
        self._set_line_edit_range()

    def update_range(self):
        """
        Validate and apply a new frequency range from the UI inputs.

        Converts the ‘From’ and ‘To’ values to MHz and ensures the lower bound
        is less than the upper bound. On success, updates the internal range,
        stores the selected unit, and invokes the callback. On failure, reverts
        the unit selection and resets the displayed inputs.

        Returns
        -------
        None
        """
        new_min, new_max = self._get_new_range()
        if new_min < new_max and [new_min, new_max] != self.range_value:
            self.unit = self.unit_combo.currentText()
            self.range_value = [new_min, new_max]
            self.callback_func(self.range_value)
        else:
            self.unit_combo.setCurrentText(self.unit)
        self._set_line_edit_range()
