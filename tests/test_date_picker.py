from datetime import date
import tkinter as tk
from tkinter import ttk
import unittest

from date_picker import DatePicker
from shipment_browser import ShipmentBrowser


class DatePickerTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('900x700')
        self.value = tk.StringVar(self.root, '10.10.2026')
        self.entry = ttk.Entry(self.root, textvariable=self.value)
        self.entry.pack()
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_calendar_is_embedded_and_enforces_range(self):
        picker = DatePicker(self.entry, self.value, minimum=date(2026, 10, 9), maximum=date(2026, 10, 11))
        self.root.update()
        self.assertIs(picker.window.winfo_toplevel(), self.root)
        picker.choose(date(2026, 10, 12))
        self.assertEqual(self.value.get(), '10.10.2026')
        picker.choose(date(2026, 10, 11))
        self.assertEqual(self.value.get(), '11.10.2026')
        self.assertFalse(picker.window.winfo_exists())

    def test_escape_and_reopening_leave_no_extra_calendar(self):
        first = DatePicker(self.entry, self.value)
        second = DatePicker(self.entry, self.value)
        self.assertFalse(first.window.winfo_exists())
        second.escape(None)
        self.assertFalse(second.window.winfo_exists())
        self.assertIsNone(self.root._date_picker)

    def test_typed_dates_reject_invalid_days_and_reversed_range(self):
        browser = ShipmentBrowser.__new__(ShipmentBrowser)
        browser.start_date = tk.StringVar(self.root, '01.10.2026')
        browser.end_date = tk.StringVar(self.root, '10.10.2026')
        browser.notice = tk.StringVar(self.root)
        self.assertFalse(browser.validate_date_input(browser.start_date, '11.10.2026'))
        self.assertFalse(browser.validate_date_input(browser.end_date, '31.02.2026'))
        self.assertFalse(browser.validate_date_input(browser.end_date, '30.09.2026'))
        self.assertTrue(browser.validate_date_input(browser.start_date, '10.10.2026'))
        self.assertTrue(browser.validate_date_input(browser.start_date, ''))
