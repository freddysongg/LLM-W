from __future__ import annotations

import sys


def test_app_cli_module_load_does_not_pull_modal_adapter() -> None:
    """`from app.cli import modal_smoke` must not transitively import modal.

    Loading the CLI for unrelated subcommands (`llmw voice smoke`, `llmw eval
    replay`) in a base install without the optional `[cloud]` extra must not
    fail at module load. The modal adapter (which does a top-level
    `import modal`) is therefore deferred to inside `modal_smoke.run()`.
    """
    for module_name in list(sys.modules):
        if module_name == "app.services.cloud.modal_adapter" or module_name.startswith(
            "app.services.cloud.modal_adapter."
        ):
            del sys.modules[module_name]
        if module_name == "app.cli.modal_smoke":
            del sys.modules[module_name]

    from app.cli import modal_smoke  # noqa: F401

    assert "app.services.cloud.modal_adapter" not in sys.modules


def test_app_cli_package_module_load_does_not_pull_modal_adapter() -> None:
    """Building the top-level CLI parser must not require modal either.

    Mirrors the dispatcher-level contract: `app.cli.__init__` builds the
    argparse tree at module load and previously transitively imported
    `modal_adapter` via `modal_smoke`.
    """
    for module_name in list(sys.modules):
        if module_name == "app.services.cloud.modal_adapter":
            del sys.modules[module_name]
        if module_name in {"app.cli", "app.cli.modal_smoke"}:
            del sys.modules[module_name]

    import app.cli  # noqa: F401

    assert "app.services.cloud.modal_adapter" not in sys.modules


def test_modal_smoke_register_subcommand_does_not_pull_modal_adapter() -> None:
    """Registering the modal subcommand on argparse must not import modal."""
    import argparse

    for module_name in list(sys.modules):
        if module_name == "app.services.cloud.modal_adapter":
            del sys.modules[module_name]
        if module_name == "app.cli.modal_smoke":
            del sys.modules[module_name]

    from app.cli import modal_smoke

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    modal_smoke.register_subcommand(subparsers=subparsers)

    assert "app.services.cloud.modal_adapter" not in sys.modules


