"""USB barcode / QR scanners act like a keyboard: they type the code, then press Enter.
So a scan is just text in an Entry field. Typing the ID by hand works the same way."""


def bind_scanner(entry, on_scan, clear=True):
    """Call on_scan(code) when Enter is pressed in `entry`.

    Returns the handler, so a 'Find' button can use the same code path.
    """
    def handle(event=None):
        code = entry.get().strip()
        if clear:
            entry.delete(0, "end")
        if code:
            on_scan(code)
        entry.focus_set()
        return "break"

    entry.bind("<Return>", handle)
    entry.focus_set()
    return handle