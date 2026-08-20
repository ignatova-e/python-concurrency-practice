from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests


def printable_table(results: list[tuple[str, bool]]) -> str:
    headers = ("Ссылка", "Статус")
    rows = [(url, "Успех" if success else "Ошибка") for url, success in results]
    widths = [max([len(headers[index]), *(len(row[index]) for row in rows)]) for index in range(2)]
    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    line = lambda row: "| " + " | ".join(value.ljust(width) for value, width in zip(row, widths)) + " |"
    return "\n".join((border, line(headers), border, *(line(row) for row in rows), border))


def validate_directory(raw_path: str) -> Path | None:
    path = Path(raw_path).expanduser()
    try:
        if not path.is_dir():
            return None
        descriptor, probe = tempfile.mkstemp(prefix=".download-test-", dir=path)
        os.close(descriptor)
        Path(probe).unlink()
        return path
    except (OSError, PermissionError):
        return None


def target_name(url: str, index: int) -> str:
    name = Path(unquote(urlparse(url).path)).name
    return name if name not in {"", ".", ".."} else f"image_{index}"


def download_sync(url: str, directory: Path, index: int) -> bool:
    target = directory / target_name(url, index)
    temporary = target.with_name(f".{target.name}.{index}.part")
    try:
        with requests.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        output.write(chunk)
        temporary.replace(target)
        return True
    except (requests.RequestException, OSError):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False


async def download(url: str, directory: Path, index: int) -> tuple[str, bool]:
    return url, await asyncio.to_thread(download_sync, url, directory, index)


async def async_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def choose_directory() -> Path:
    while True:
        path = validate_directory(await async_input("Путь для сохранения изображений: "))
        if path is not None:
            return path
        print("Некорректный путь или нет доступа для записи. Попробуйте снова.")


async def main() -> None:
    directory = await choose_directory()
    tasks: list[asyncio.Task[tuple[str, bool]]] = []
    while True:
        url = (await async_input("Ссылка на изображение (пустая строка — закончить): ")).strip()
        if not url:
            break
        tasks.append(asyncio.create_task(download(url, directory, len(tasks) + 1)))
    if any(not task.done() for task in tasks):
        print("Не все изображения загружены. Ожидаем завершения загрузок...")
    results = await asyncio.gather(*tasks)
    print("\nСводка об успешных и неуспешных загрузках")
    print(printable_table(results))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (EOFError, KeyboardInterrupt):
        print("\nРабота программы прервана.")
