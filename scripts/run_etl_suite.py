#!/usr/bin/env python3
"""Run ETL pipelines with per-step timeouts and structured JSON logs (single source for ``start.sh``).

Examples::

    python scripts/run_etl_suite.py
    python scripts/run_etl_suite.py --profile full --with-joins
    python scripts/run_etl_suite.py --continue-on-error
    HOUSING_ETL_STEP_TIMEOUT=7200 python scripts/run_etl_suite.py --only ons_epc_etl
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]


def _py() -> str:
    return sys.executable


def _step(step_id: str, script: str, *args: str, timeout: int | None = None) -> tuple[str, list[str], int]:
    t = timeout if timeout is not None else int(os.environ.get("HOUSING_ETL_STEP_TIMEOUT", "3600"))
    cmd = [_py(), str(_REPO / script), *args]
    return step_id, cmd, t


def _step_module(step_id: str, module: str, *args: str, timeout: int | None = None) -> tuple[str, list[str], int]:
    t = timeout if timeout is not None else int(os.environ.get("HOUSING_ETL_STEP_TIMEOUT", "3600"))
    cmd = [_py(), "-m", module, *args]
    return step_id, cmd, t


def standard_steps() -> list[tuple[str, list[str], int]]:
    return [
        _step("uk_local_authority_housing", "uk_local_authority_housing_data.py"),
        _step("ons_epc_etl", "ons_epc_etl.py", "--edition", "march2025"),
        _step("ons_ee_fiveyear_etl", "ons_ee_fiveyear_etl.py", "--edition", "march2025"),
        _step("ons_housebuilding_la_etl", "ons_housebuilding_la_etl.py", "--edition", "fye_march2025"),
        _step("ons_housebuilding_country_etl", "ons_housebuilding_country_etl.py", "--edition", "current"),
        _step("ons_mainfuel_etl", "ons_mainfuel_etl.py", "--edition", "march2025"),
        _step("ons_uk_hpi_monthly_etl", "ons_uk_hpi_monthly_etl.py", "--edition", "march2026"),
        _step("ons_private_rental_index_etl", "ons_private_rental_index_etl.py", "--edition", "v41"),
        _step("ons_house_m2_room_etl", "ons_house_m2_room_etl.py", "--edition", "2004to2016"),
        _step("ons_median_price_admin_all", "ons_median_price_admin_etl.py", "--dataset", "all", "--edition", "yearendingseptember2025"),
        _step("ons_median_price_admin_existing", "ons_median_price_admin_etl.py", "--dataset", "existing", "--edition", "yearendingseptember2025"),
        _step("ons_median_price_admin_new", "ons_median_price_admin_etl.py", "--dataset", "new", "--edition", "yearendingseptember2025"),
        _step("ons_national_park_hpssa_etl", "ons_national_park_hpssa_etl.py", "--edition", "yearendingseptember2025"),
        _step("ons_vacant_second_homes_etl", "ons_vacant_second_homes_etl.py", "--edition", "current"),
        _step("ons_price_earnings_ratio_etl", "ons_price_earnings_ratio_etl.py", "--edition", "current"),
        _step("ons_price_newbuild_workplace_earnings_ratio_etl", "ons_price_newbuild_workplace_earnings_ratio_etl.py", "--edition", "current"),
        _step("ons_price_residence_earnings_ratio_etl", "ons_price_residence_earnings_ratio_etl.py", "--edition", "current"),
        _step("ons_house_price_explorer_etl", "ons_house_price_explorer_etl.py", "--edition", "current"),
    ]


def full_extra_steps() -> list[tuple[str, list[str], int]]:
    long_timeout = int(os.environ.get("HOUSING_ETL_CENSUS_TIMEOUT", "7200"))
    return [
        _step("ons_census2021_etl", "ons_census2021_etl.py", "--dataset", "sex_ts008", timeout=long_timeout),
        _step("build_processed_manifest", "scripts/build_processed_manifest.py", timeout=600),
    ]


def join_steps() -> list[tuple[str, list[str], int]]:
    return [
        _step_module("join_la_housebuilding_mainfuel", "joins.build_joined_la_housebuilding_mainfuel"),
        _step_module("aggregate_la_supply_to_region", "joins.aggregate_la_supply_to_region"),
        _step_module(
            "build_la_housing_market_snapshot",
            "joins.build_la_housing_market_snapshot",
            "--vacant-second-homes-edition",
            "current",
        ),
    ]


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", choices=("standard", "full"), default="standard", help="full adds Census TS008 + manifest.")
    p.add_argument("--with-joins", action="store_true", help="After other steps, run join builders (needs prior ETL outputs).")
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Run all steps even if one fails (default is stop on first error).",
    )
    p.add_argument("--only", action="append", default=[], metavar="STEP_ID", help="Run only these step ids (repeatable).")
    p.add_argument("--skip", action="append", default=[], metavar="STEP_ID", help="Skip these step ids (repeatable).")
    args = p.parse_args()

    fail_fast = not args.continue_on_error
    steps = list(standard_steps())
    if args.profile == "full":
        steps.extend(full_extra_steps())
    if args.with_joins:
        steps.extend(join_steps())

    skip_ids = set(args.skip)
    only_ids = set(args.only) if args.only else None

    failed = 0
    for step_id, cmd, timeout in steps:
        if only_ids is not None and step_id not in only_ids:
            continue
        if step_id in skip_ids:
            _emit({"step": step_id, "status": "skipped", "reason": "--skip"})
            continue

        t0 = time.perf_counter()
        _emit({"step": step_id, "status": "started", "cmd": cmd, "timeout_sec": timeout})
        try:
            proc = subprocess.run(
                cmd,
                cwd=_REPO,
                timeout=timeout,
                text=True,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            _emit(
                {
                    "step": step_id,
                    "status": "timeout",
                    "elapsed_sec": round(elapsed, 3),
                    "timeout_sec": timeout,
                }
            )
            failed += 1
            if fail_fast:
                return 124
            continue

        elapsed = time.perf_counter() - t0
        out_tail = (proc.stdout or "")[-4000:]
        err_tail = (proc.stderr or "")[-4000:]
        event: dict[str, Any] = {
            "step": step_id,
            "status": "ok" if proc.returncode == 0 else "error",
            "exit_code": proc.returncode,
            "elapsed_sec": round(elapsed, 3),
        }
        if proc.returncode != 0:
            event["stdout_tail"] = out_tail
            event["stderr_tail"] = err_tail
        # Optional: hash primary output if step id maps to a known parquet (best-effort)
        _emit(event)

        if proc.returncode != 0:
            failed += 1
            if fail_fast:
                return proc.returncode if proc.returncode else 1

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
