"""TrinaxAI CLI subcommands.

Each module exposes a ``run(args, client, ui, config) -> int`` function.
The dispatcher in ``trinaxai_cli.app`` lazy-imports each module.
"""
