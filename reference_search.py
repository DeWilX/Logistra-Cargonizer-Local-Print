"""Resolve exact order references across all API history pages."""
from shipment_browser import load_shipments
from datetime import date


def find_reference(cfg, reference, progress=None):
    reference = reference.strip().casefold()
    if not reference:
        raise ValueError('Ievadi ref. / order numuru.')
    rows = load_shipments(cfg, 'Visi', start=date(1900, 1, 1), end=date.today(), progress=progress)
    return [row for row in rows if row['reference'].strip().casefold() == reference]
