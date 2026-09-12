# Vendored dependencies

`access_parser` (0.0.6, Claroty), `construct` (2.10.70, MIT) and `tabulate`
(0.10.0) are vendored here — unmodified upstream sources, pure Python, no
compiled extensions — so `.accdb` comparison works on hosts where `pip
install` can't be run (no SSH/terminal access, e.g. some Hostinger plans).

`web/engine/cli.py` appends this directory to `sys.path` only as a
fallback: a real `pip install access-parser` still takes priority when
present. Safe to delete this folder on any host where you can `pip
install -r requirements.txt` instead.
