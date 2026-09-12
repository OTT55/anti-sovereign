"""
Test Veridact with a real camera — one command, no environment variables.

    python run_phone_test.py

This is exactly `run.py` with VERIDACT_HTTPS and VERIDACT_HOST already turned
on for you, in the script itself rather than as shell environment variables —
so the same command works identically whether you're in PowerShell, Git Bash,
or cmd.exe. (The env-var form still exists in run.py for anyone who wants it,
but `VAR=value command` is bash-only syntax; it silently fails in PowerShell,
which is exactly the kind of shell-specific trap this file avoids.)

See decisions/0005 for why HTTPS is needed at all here (short version: a
phone reaching this machine over Wi-Fi is not a "secure context," and browsers
refuse camera access outside one).
"""

from app import create_app

app = create_app({"HTTPS": True, "HOST": "0.0.0.0"})

if __name__ == "__main__":
    port = app.config["PORT"]
    print(f"\n  Veridact (camera-testing mode) -> https://127.0.0.1:{port}")
    print("  On your phone: use whichever https://<ip>:PORT address below is your")
    print("  real Wi-Fi IP (usually 192.168.x.x or 10.x.x.x) — not a VPN adapter's.\n")
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"], ssl_context="adhoc")
