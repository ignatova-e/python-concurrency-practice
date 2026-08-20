from __future__ import annotations

import multiprocessing as mp
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PHI = (1 + 5**0.5) / 2
PASS = "Сдал"
FAIL = "Провалил"
WAIT = "Очередь"


@dataclass(frozen=True)
class Student:
    name: str
    gender: str


@dataclass(frozen=True)
class Question:
    text: str

    @property
    def words(self) -> list[str]:
        return self.text.split()


@dataclass(frozen=True)
class Examiner:
    name: str
    gender: str


def golden_weights(size: int, reverse: bool = False) -> list[float]:
    """Return golden-ratio probabilities, optionally favouring the end."""
    if size < 1:
        raise ValueError("В вопросе должно быть хотя бы одно слово")
    remaining = 1.0
    weights = []
    for _ in range(size - 1):
        weight = remaining / PHI
        weights.append(weight)
        remaining -= weight
    weights.append(remaining)
    return list(reversed(weights)) if reverse else weights


def choose_word(words: Sequence[str], gender: str, rng: random.Random) -> str:
    return rng.choices(words, weights=golden_weights(len(words), gender.upper() == "Ж"), k=1)[0]


def examiner_answers(question: Question, gender: str, rng: random.Random) -> set[str]:
    available = list(dict.fromkeys(question.words))
    answers: set[str] = set()
    while available:
        word = choose_word(available, gender, rng)
        answers.add(word)
        available.remove(word)
        if not available or rng.random() >= 1 / 3:
            break
    return answers


def examine(student: Student, examiner: Examiner, questions: Sequence[Question], rng: random.Random):
    selected = rng.sample(list(questions), k=min(3, len(questions)))
    correct_questions: list[str] = []
    for question in selected:
        answer = choose_word(question.words, student.gender, rng)
        if answer in examiner_answers(question, examiner.gender, rng):
            correct_questions.append(question.text)

    mood = rng.random()
    passed = False if mood < 1 / 8 else True if mood < 3 / 8 else len(correct_questions) > len(selected) / 2
    return passed, correct_questions


def examiner_worker(examiner: Examiner, students, questions, events, started_at: float) -> None:
    rng = random.Random(os.getpid() ^ time.time_ns())
    total = failed = 0
    lunch_taken = False
    while True:
        student = students.get()
        if student is None:
            break
        events.put(("start", examiner.name, student.name, time.monotonic() - started_at))
        duration = rng.uniform(max(0.0, len(examiner.name) - 1), len(examiner.name) + 1)
        time.sleep(duration)
        passed, correct = examine(student, examiner, questions, rng)
        total += 1
        failed += not passed
        events.put(("finish", examiner.name, student.name, passed, correct,
                    duration, total, failed, time.monotonic() - started_at))

        if not lunch_taken and time.monotonic() - started_at >= 30:
            lunch_taken = True
            events.put(("lunch", examiner.name, time.monotonic() - started_at))
            time.sleep(rng.uniform(12, 18))

    events.put(("done", examiner.name, total, failed, time.monotonic() - started_at))


def read_objects(path: Path, factory):
    with path.open(encoding="utf-8") as source:
        return list(map(lambda line: factory(*line.strip().rsplit(maxsplit=1)),
                        filter(lambda line: line.strip(), source)))


def read_questions(path: Path) -> list[Question]:
    with path.open(encoding="utf-8") as source:
        return list(map(lambda line: Question(line.strip()), filter(lambda line: line.strip(), source)))


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    values = [list(map(str, row)) for row in rows]
    widths = [len(header) for header in headers]
    for row in values:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    line = lambda row: "| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |"
    return "\n".join([border, line(headers), border, *(line(row) for row in values), border])


def clear_screen() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")


def render(students, examiners, state, started_at: float, final: bool = False) -> None:
    clear_screen()
    status_order = {WAIT: 0, PASS: 1, FAIL: 2}
    ordered = sorted(students, key=lambda item: status_order[state["students"][item.name]["status"]])
    print(table(("Студент", "Статус"),
                ((item.name, state["students"][item.name]["status"]) for item in ordered)))
    print()
    if final:
        headers = ("Экзаменатор", "Всего студентов", "Завалил", "Время работы")
        rows = ((item.name, state["examiners"][item.name]["total"],
                 state["examiners"][item.name]["failed"],
                 f'{state["examiners"][item.name]["time"]:.2f}') for item in examiners)
    else:
        headers = ("Экзаменатор", "Текущий студент", "Всего студентов", "Завалил", "Время работы")
        elapsed = time.monotonic() - started_at
        rows = ((item.name, state["examiners"][item.name]["current"],
                 state["examiners"][item.name]["total"], state["examiners"][item.name]["failed"],
                 f'{state["examiners"][item.name]["time"] if state["examiners"][item.name]["done"] else elapsed:.2f}')
                for item in examiners)
    print(table(headers, rows))
    if not final:
        waiting = sum(state["students"][item.name]["status"] == WAIT for item in students)
        print(f"\nОсталось в очереди: {waiting} из {len(students)}")
        print(f"Время с момента начала экзамена: {time.monotonic() - started_at:.2f}")


def find_input(name: str) -> Path:
    local = Path(name)
    return local if local.is_file() else Path(__file__).resolve().parent / name


def run_exam(students: list[Student], examiners: list[Examiner], questions: list[Question]) -> None:
    if not students or not examiners or not questions:
        raise ValueError("Списки студентов, экзаменаторов и вопросов не должны быть пустыми")
    context = mp.get_context("spawn")
    student_queue = context.Queue()
    events = context.Queue()
    for student in students:
        student_queue.put(student)
    for _ in examiners:
        student_queue.put(None)
    state = {
        "students": {s.name: {"status": WAIT, "duration": 0.0} for s in students},
        "examiners": {e.name: {"current": "-", "total": 0, "failed": 0,
                                 "time": 0.0, "done": False} for e in examiners},
        "questions": {q.text: 0 for q in questions},
    }
    started_at = time.monotonic()
    processes = [context.Process(target=examiner_worker,
                                 args=(e, student_queue, questions, events, started_at)) for e in examiners]
    for process in processes:
        process.start()

    done = 0
    render(students, examiners, state, started_at)
    while done < len(examiners):
        event = events.get()
        kind, examiner_name = event[:2]
        examiner_state = state["examiners"][examiner_name]
        if kind == "start":
            examiner_state["current"] = event[2]
        elif kind == "finish":
            _, _, student_name, passed, correct, duration, total, failed, elapsed = event
            state["students"][student_name] = {"status": PASS if passed else FAIL, "duration": duration}
            examiner_state.update(current="-", total=total, failed=failed, time=elapsed, done=True)
            for question in correct:
                state["questions"][question] += 1
        elif kind == "lunch":
            examiner_state.update(current="-", time=event[2])
        else:
            _, _, total, failed, elapsed = event
            examiner_state.update(current="-", total=total, failed=failed, time=elapsed)
            done += 1
        render(students, examiners, state, started_at)

    for process in processes:
        process.join()
    elapsed = time.monotonic() - started_at
    render(students, examiners, state, started_at, final=True)
    passed = [s for s in students if state["students"][s.name]["status"] == PASS]
    failed = [s for s in students if state["students"][s.name]["status"] == FAIL]
    fastest_pass = min((state["students"][s.name]["duration"] for s in passed), default=None)
    fastest_fail = min((state["students"][s.name]["duration"] for s in failed), default=None)
    rates = {e.name: (state["examiners"][e.name]["failed"] / state["examiners"][e.name]["total"]
                      if state["examiners"][e.name]["total"] else float("inf")) for e in examiners}
    best_rate = min(rates.values())
    best_score = max(state["questions"].values())
    join = lambda names: ", ".join(names) if names else "-"
    print(f"\nВремя с момента начала экзамена и до момента его завершения: {elapsed:.2f}")
    print("Имена лучших студентов:", join(s.name for s in passed if state["students"][s.name]["duration"] == fastest_pass))
    print("Имена лучших экзаменаторов:", join(e.name for e in examiners if rates[e.name] == best_rate))
    print("Имена студентов, которых после экзамена отчислят:",
          join(s.name for s in failed if state["students"][s.name]["duration"] == fastest_fail))
    print("Лучшие вопросы:", join(text for text, score in state["questions"].items() if score == best_score))
    print("Вывод:", "экзамен удался" if len(passed) / len(students) > 0.85 else "экзамен не удался")


def main() -> None:
    try:
        examiners = read_objects(find_input("examiners.txt"), Examiner)
        students = read_objects(find_input("students.txt"), Student)
        questions = read_questions(find_input("questions.txt"))
        run_exam(students, examiners, questions)
    except (OSError, ValueError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    mp.freeze_support()
    main()
