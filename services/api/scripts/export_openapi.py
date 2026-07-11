import json
from pathlib import Path

from distributoros.main import create_app

OUTPUT_PATH = Path(__file__).resolve().parents[3] / "packages" / "api-client" / "openapi.json"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    app = create_app()
    OUTPUT_PATH.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
