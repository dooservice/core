"""Generate and update odoo.conf — the single source of truth for Odoo runtime."""

from __future__ import annotations

import configparser
from io import StringIO
from pathlib import Path

from dooservice_models import ODOO_DATA_DIR, ODOO_GEVENT_PORT, Environment

ODOO_BUILTIN_ADDONS = "/usr/lib/python3/dist-packages/odoo/addons"
ODOO_CONFIG_FILE    = "/etc/odoo/odoo.conf"


def render(env: Environment, addons_paths: list[str]) -> str:
    cfg = configparser.ConfigParser(interpolation=None)
    options: dict[str, str] = {
        "db_host":      env.config.pg_db_host,
        "db_port":      str(env.config.pg_db_port),
        "db_user":      env.config.pg_db_user,
        "db_password":  env.config.pg_db_password,
        "db_name":      env.config.pg_db_name,
        "db_filter":    f"^{env.config.pg_db_name}$",
        "list_db":      "False",
        "addons_path":  ",".join([ODOO_BUILTIN_ADDONS, *addons_paths]),
        "limit_time_cpu":   "600",
        "limit_time_real":  "600",
        "proxy_mode":       "True",
        "unaccent":         "True",
        "data_dir":         ODOO_DATA_DIR,
    }
    total_workers = env.config.base_workers + env.config.extra_workers
    options["db_maxconn"] = str(max(10, total_workers * 8))
    if total_workers >= 1:
        options["workers"]           = str(total_workers)
        options["gevent_port"]       = str(ODOO_GEVENT_PORT)
        options["db_maxconn_gevent"] = str(max(6, total_workers * 4))
    cfg["options"] = options
    out = StringIO()
    cfg.write(out)
    return out.getvalue()


def write(path: Path, env: Environment, addons_paths: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render(env, addons_paths))
    tmp.replace(path)


def read_addons_path(path: Path) -> list[str]:
    if not path.exists():
        return []
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path)
    raw = cfg.get("options", "addons_path", fallback="")
    items = [p.strip() for p in raw.split(",") if p.strip()]
    return [p for p in items if p != ODOO_BUILTIN_ADDONS]
