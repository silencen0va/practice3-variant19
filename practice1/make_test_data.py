"""Создаёт учебные CSV-файлы варианта 19."""

import argparse
import random
from pathlib import Path


DEPARTMENTS = ("editors", "video", "archive")
FILES_PER_DEPARTMENT = 4


def make_test_data(root=Path("company_data"), *, with_buh=False):
    departments = DEPARTMENTS + ("buh",) if with_buh else DEPARTMENTS
    rng = random.Random(19)
    for department in departments:
        folder = root / department
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(1, FILES_PER_DEPARTMENT + 1):
            lines = [
                f"{department};doc{index};{rng.randint(1000, 99999)}"
                for _ in range(200)
            ]
            (folder / f"report_{index}.csv").write_text(
                "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
            )
    print(f"[OK] {root.name}: {', '.join(departments)}, "
          f"создано файлов: {len(departments) * FILES_PER_DEPARTMENT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-buh", action="store_true",
                        help="добавить бухгалтерию для учебного инцидента")
    make_test_data(with_buh=parser.parse_args().with_buh)
