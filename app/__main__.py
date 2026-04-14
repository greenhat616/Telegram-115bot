# -*- coding: utf-8 -*-
"""Entry point for `python -m app` and `telegram-115bot` CLI command."""

import importlib

def main():
    # 115bot.py cannot be imported directly due to the leading digit in the filename,
    # so we use importlib to load it.
    bot = importlib.import_module("app.115bot")
    bot.main()

if __name__ == "__main__":
    main()
