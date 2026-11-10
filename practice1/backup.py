"""Полное резервное копирование, проверка, ротация и восстановление."""

import argparse
import hashlib
import json
import shutil
import tarfile
import time
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory, mkdtemp


SOURCE = Path("company_data")
BACKUP_DIR = Path("backups")
KEEP_LAST = 3


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def make_manifest(folder):
    """Связывает относительные пути файлов с их хешами SHA-256."""
    if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
        raise ValueError(f"Ожидалась обычная папка: {folder}")
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Ссылки в данных не поддерживаются: {path}")
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = sha256(path)
        elif not path.is_dir():
            raise ValueError(f"Ожидался обычный файл: {path}")
    return files


def manifest_path(archive):
    return archive.with_suffix("").with_suffix(".json")


def list_archives(backup_dir):
    return sorted(
        archive for archive in backup_dir.glob("backup_*.tar.gz")
        if archive.is_file() and manifest_path(archive).is_file()
    )


def rotate(backup_dir):
    for archive in list_archives(backup_dir)[:-KEEP_LAST]:
        archive.unlink(missing_ok=True)
        manifest_path(archive).unlink(missing_ok=True)
        print(f"[ROTATE] Удалена старая копия {archive.name}")


def extract_checked(archive, destination):
    """Извлекает архив в пустую папку и проверяет его содержимое."""
    manifest = json.loads(manifest_path(archive).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise ValueError("Некорректный JSON-манифест.")
    if sha256(archive) != manifest["archive_sha256"]:
        raise ValueError("Архив повреждён: SHA-256 не совпадает.")

    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            parts = PurePosixPath(member.name).parts
            if (not parts or parts[0] != SOURCE.name or ".." in parts
                    or not (member.isfile() or member.isdir())):
                raise ValueError(f"Недопустимая запись в архиве: {member.name}")
        tar.extractall(destination, filter="data")

    restored = make_manifest(destination / SOURCE.name)
    expected = manifest["files"]
    missing = expected.keys() - restored.keys()
    extra = restored.keys() - expected.keys()
    changed = {
        path for path in expected.keys() & restored.keys()
        if expected[path] != restored[path]
    }
    for label, paths in (
        ("Отсутствует", missing), ("Лишний", extra), ("Изменён", changed)
    ):
        for path in sorted(paths):
            print(f"[FAIL] {label}: {path}")
    if missing or extra or changed:
        raise ValueError("Восстановленные файлы отличаются от манифеста.")
    return len(restored)


def verify_restore(archive):
    """Пробное восстановление без изменений в рабочей папке."""
    try:
        with TemporaryDirectory(prefix="backup-check-") as temp:
            count = extract_checked(archive, Path(temp))
    except (OSError, EOFError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"[FAIL] {error}")
        return False
    print(f"[OK] Восстановление проверено: {count} файлов совпадают")
    return True


def create_backup(source=SOURCE, backup_dir=BACKUP_DIR):
    files = make_manifest(source)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Сначала проверяем копию, затем публикуем пару архив + JSON.
    with TemporaryDirectory(prefix=".pending-", dir=backup_dir) as temp:
        staged = Path(temp) / f"backup_{stamp}.tar.gz"
        with tarfile.open(staged, "w:gz", dereference=True) as tar:
            tar.add(source, arcname=SOURCE.name)
        manifest = {
            "created": stamp,
            "archive_sha256": sha256(staged),
            "files": files,
        }
        manifest_path(staged).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if not verify_restore(staged):
            raise ValueError("Новая копия не прошла проверку.")
        archive = backup_dir / staged.name
        staged.rename(archive)
        try:
            manifest_path(staged).rename(manifest_path(archive))
        except OSError:
            archive.unlink(missing_ok=True)
            raise

    print(f"[OK] Создан {archive.name}, файлов: {len(files)}, "
          f"размер: {archive.stat().st_size} байт")
    rotate(backup_dir)
    return archive


def restore(archive, source=SOURCE):
    """Проверяет копию, затем заменяет рабочую папку целиком."""
    started = time.perf_counter()
    if (source.is_symlink() or source.is_junction()
            or (source.exists() and not source.is_dir())):
        raise ValueError(f"Ожидалась обычная папка: {source}")
    with TemporaryDirectory(prefix=".restore-", dir=source.parent) as temp:
        stage = Path(temp)
        count = extract_checked(archive, stage)
        # Убираем старые данные с рабочего пути. При ошибке возвращаем их.
        previous = None
        if source.exists():
            previous = Path(mkdtemp(prefix=".previous-", dir=source.parent))
            source.rename(previous / source.name)
        try:
            (stage / SOURCE.name).rename(source)
        except OSError:
            if previous is not None:
                (previous / source.name).rename(source)
                previous.rmdir()
            raise
        if previous is not None:
            shutil.rmtree(previous)
    elapsed = time.perf_counter() - started
    print(f"[OK] Восстановлено: {count} файлов за {elapsed:.3f} с")
    return elapsed


def demo():
    """Удаляет бухгалтерию только в новой временной папке."""
    from make_test_data import make_test_data

    with TemporaryDirectory(prefix=".demo-", dir=Path.cwd()) as temp:
        root = Path(temp)
        source = root / SOURCE
        buh = source / "buh"
        make_test_data(source, with_buh=True)
        before = make_manifest(buh)
        archive = create_backup(source, root / BACKUP_DIR)
        print(f"[ДО] В buh файлов: {len(before)}")
        # buh находится внутри только что созданного временного каталога.
        if buh.resolve().parent != source.resolve():
            raise ValueError("Папка бухгалтерии вне тестового каталога.")
        shutil.rmtree(buh)
        print(f"[СБОЙ] Папка buh удалена, существует: {buh.exists()}")
        restore(archive, source)
        if make_manifest(buh) != before:
            raise ValueError("Файлы бухгалтерии не совпадают.")
        print(f"[ПОСЛЕ] buh восстановлена: {len(before)} файлов, SHA-256 совпадают")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="backup",
                        choices=("backup", "verify", "restore", "demo"))
    parser.add_argument("archive", nargs="?", type=Path,
                        help="путь к архиву для verify или restore")
    args = parser.parse_args()
    if args.archive is not None and args.command in ("backup", "demo"):
        parser.error("путь к архиву можно указать только для verify или restore")

    try:
        if args.command == "demo":
            demo()
        elif args.command == "backup":
            create_backup()
        else:
            archives = list_archives(BACKUP_DIR) if args.archive is None else []
            archive = args.archive or (archives[-1] if archives else None)
            if archive is None:
                raise ValueError("В папке backups нет пары архив + манифест.")
            if args.command == "verify":
                return 0 if verify_restore(archive) else 1
            restore(archive)
    except (OSError, EOFError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"[FAIL] {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
