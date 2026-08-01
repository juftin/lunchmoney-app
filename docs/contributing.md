# Contributing

## Environment setup

This project uses [uv](https://docs.astral.sh/uv/) for dependencies and
[Task](https://taskfile.dev/) for project workflows.

```shell
task install
```

## Common tasks

| Task                 | Purpose                                |
| -------------------- | -------------------------------------- |
| `task test`          | Run the test suite.                    |
| `task lint`          | Check formatting and linting.          |
| `task check`         | Run static type checks.                |
| `task fix`           | Apply formatting and lint fixes.       |
| `task docs`          | Serve the documentation locally.       |
| `task docs -- build` | Build the documentation site.          |
| `task build`         | Build package and container artifacts. |

Before submitting a change, run:

```shell
task fix && task lint && task check && task test
```

Commits follow the project's Gitmoji convention; for example, `✨ Add feature`
or `🐛 Fix bug`.
