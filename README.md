# Python Concurrency Practice

## Project Goal

The goal of this project is to explore different approaches to structuring
Python programs and learn how to apply them in practice. The exercises cover
object-oriented, procedural, and functional programming, file handling, and
error handling. Special attention is given to concurrent task execution:
creating separate processes with `multiprocessing` and asynchronous work with
`asyncio`.

## Exercise 1: Exam

The `exercise1` directory contains an exam simulation. Students wait in a
shared queue, and each examiner conducts exams in a separate process. Exam
results depend on the student's answers, the participant's gender, the
examiner's mood, and random factors specified in the task.

The program:

- reads lists of students, examiners, and questions from text files;
- assigns students to examiners through a shared queue;
- simulates answers, exam results, and examiner breaks;
- updates live statistics in the console;
- prints summary tables and highlights the top students, examiners, and
  questions when it finishes.

This exercise uses object-oriented programming and data classes, file input,
the `multiprocessing` module, inter-process communication, random values, and
exception handling.

Run it with:

```bash
python exercise1/task1.py
```

## Exercise 2: Downloading Images

The `exercise2` directory contains a URL handler for downloading multiple
images at the same time. The user selects a destination folder and enters URLs
one by one while downloads run in parallel with further input.

The program:

- checks that the destination folder exists and is writable;
- creates a separate asynchronous task for each URL;
- waits for all started downloads to finish;
- continues running if an individual request fails;
- prints a summary table of successful and failed downloads.

This exercise uses `asyncio`, asynchronous tasks, running blocking operations
in separate threads, HTTP requests, path handling, and network error handling.

The `requests` package is required:

```bash
pip install requests
python exercise2/task2.py
```
