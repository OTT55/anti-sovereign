"""
The on switch.

    python run.py                          ->  http://127.0.0.1:5102
    VERIDACT_HTTPS=1 VERIDACT_HOST=0.0.0.0 python run.py
                                            ->  https://<this machine's LAN IP>:5102
                                                (open that URL on your phone to test
                                                 the capture agent with a real camera —
                                                 see decisions/0005)
"""

from app import create_app

app = create_app()

# A note on finding the LAN address to type into a phone: this machine may have
# several network interfaces (Wi-Fi, VPN, virtual adapters), and a quick guess
# (e.g. opening a throwaway UDP socket to see which interface the OS would
# route through) can name the wrong one — confirmed by testing, not assumed:
# a first attempt at this printed a VPN adapter's address, which doesn't reach
# the phone, instead of the real Wi-Fi address that does. Werkzeug (Flask's
# dev server) already enumerates every bound interface correctly when
# host="0.0.0.0" and prints each one in its own "Running on https://…" lines
# below — that enumeration is deferred to rather than duplicated.

if __name__ == "__main__":
    import os as _os
    # decisions/0009: load the watermark model once here, not on the first
    # capture a real user makes. Guarded so Werkzeug's debug-mode reloader
    # (which runs this file in two processes) only warms it in the one that
    # actually serves requests, not its parent watcher too.
    if not app.config["DEBUG"] or _os.environ.get("WERKZEUG_RUN_MAIN"):
        from app.watermark import _model as _warm_watermark_model
        print("  Loading soft-binding watermark model…")
        _warm_watermark_model()

    port = app.config["PORT"]
    host = app.config["HOST"]
    scheme = "https" if app.config["HTTPS"] else "http"

    print(f"\n  Veridact -> {scheme}://127.0.0.1:{port}")
    if host != "127.0.0.1":
        print("  On your phone (same Wi-Fi): use whichever address below is your "
              "LAN IP, not a VPN/virtual adapter (see decisions/0005).")
        if not app.config["HTTPS"]:
            print("  WARNING: a phone/webcam over the LAN needs HTTPS to use the "
                  "camera. Set VERIDACT_HTTPS=1.")
    print()

    app.run(
        host=host,
        port=port,
        debug=app.config["DEBUG"],
        ssl_context="adhoc" if app.config["HTTPS"] else None,
    )
