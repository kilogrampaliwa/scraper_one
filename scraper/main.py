"""Entry point: `python -m scraper.main` (used by the GitHub Actions workflow)."""

from .orchestrator import main

if __name__ == "__main__":
    main()
