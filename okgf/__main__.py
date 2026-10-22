"""Enable ``python -m okgf`` as an alias for the ``okgf`` console command."""

from okgf.validate import main

if __name__ == "__main__":
    raise SystemExit(main())
