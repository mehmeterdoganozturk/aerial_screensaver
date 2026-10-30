"""Uyumluluk yardımcıları."""

from gi.repository import GLib


def unix_signal_add(sig, callback, *args):
    try:
        import gi
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        return GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, callback, *args)
    except (ImportError, ValueError, AttributeError):
        return GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, callback, *args)
