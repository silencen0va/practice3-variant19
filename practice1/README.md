# Практическая работа № 3

**Порываев Кирил Денисович, вариант № 19 — телеканал**

Нужен Python 3.12 или новее. Скрипты используют стандартную библиотеку Python. Запускайте команды из папки practice1.

| Файл | Назначение |
| --- | --- |
| make_test_data.py | Генерирует 12 учебных CSV-файлов, по четыре для editors, video и archive. |
| backup.py | Создаёт полную копию, проверяет пробное восстановление, хранит три последние копии, восстанавливает данные. |
| rpo_rto.md | Расчёт для телеканала и схема хранения по правилу 3-2-1. |

## Создание копий и проверка ротации

~~~powershell
python make_test_data.py
1..8 | ForEach-Object {
    python backup.py
    if ($LASTEXITCODE -ne 0) { throw "Ошибка резервного копирования" }
    if ($_ -lt 8) { Start-Sleep -Seconds 2 }
}
Get-ChildItem .\backups
python backup.py verify
~~~

В backups останутся три архива .tar.gz и три одноимённых JSON-манифеста. В JSON хранятся метка времени, SHA-256 архива и SHA-256 каждого исходного файла. Команды verify и restore по умолчанию выбирают последнюю пару архив и манифест. Для выбора другой пары укажите путь к архиву после команды.

## Восстановление для защиты

~~~powershell
python backup.py demo
~~~

В отдельной временной папке программа добавит к набору варианта четыре файла бухгалтерии, создаст и проверит копию, удалит buh, восстановит весь набор и сравнит хеши файлов бухгалтерии. Команда подходит для повторного запуска на защите.

Пример вывода

~~~text
[OK] company_data: editors, video, archive, buh, создано файлов: 16
[OK] Восстановление проверено: 16 файлов совпадают
[OK] Создан backup_20261110_205826_673253.tar.gz, файлов: 16, размер: 13306 байт
[ДО] В buh файлов: 4
[СБОЙ] Папка buh удалена, существует: False
[OK] Восстановлено: 16 файлов за 0.063 с
[ПОСЛЕ] buh восстановлена: 4 файлов, SHA-256 совпадают
~~~

Для ручного опыта работайте в отдельной учебной копии проекта. В ней выполните python make_test_data.py --with-buh, затем python backup.py. Удалите учебную папку company_data/buh, проверьте её отсутствие и выполните python backup.py restore. Команда restore заменяет всю текущую папку company_data содержимым проверенной копии. Изменения после создания этой копии будут потеряны.

## Проверка повреждений

Скопируйте последнюю пару архив и JSON в отдельную папку damage_test.

~~~powershell
$archive = Get-ChildItem .\backups\backup_*.tar.gz |
    Sort-Object Name | Select-Object -Last 1
$jsonName = $archive.Name -replace '\.tar\.gz$', '.json'
New-Item -ItemType Directory -Force .\damage_test | Out-Null
Copy-Item -LiteralPath $archive.FullName -Destination .\damage_test
Copy-Item -LiteralPath (Join-Path $archive.DirectoryName $jsonName) -Destination .\damage_test
$copy = Join-Path .\damage_test $archive.Name
~~~

1. В копии JSON измените один символ хеша файла в объекте files и удалите запись о другом файле. Сохраните корректные запятые. Выполните python backup.py verify $copy. Ожидаются строки «Изменён» и «Лишний».
2. Скопируйте исходный JSON поверх изменённого. В копии архива измените один байт командой ниже, затем снова выполните проверку. Ожидается сообщение о несовпадении SHA-256 архива. Код завершения при провале проверки равен 1.

~~~powershell
Copy-Item -LiteralPath (Join-Path $archive.DirectoryName $jsonName) -Destination .\damage_test -Force
python -c "import sys; from pathlib import Path; p = Path(sys.argv[1]); b = bytearray(p.read_bytes()); b[20] ^= 255; p.write_bytes(b)" $copy
python backup.py verify $copy
~~~

## Сдача

Корень репозитория должен содержать .gitignore и папку practice1. Загрузите файлы в свой репозиторий GitHub и внесите его URL в строку «Репозиторий» на титульном листе отчёта. Рабочие данные и архивы исключены через .gitignore.
