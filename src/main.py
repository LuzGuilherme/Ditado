"""Entry point for Ditado."""

import sys

# Force unbuffered output (only if streams exist - they may be None in frozen exe)
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass


def main():
    """Main entry point."""
    print("=" * 50, flush=True)
    print("  Ditado - Voice Dictation Tool", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)

    from .app import DitadoApp

    app = DitadoApp()

    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
