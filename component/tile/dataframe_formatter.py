import re
import ast
from typing import List, Optional, cast

import numpy as np
import pandas as pd
import geopandas as gpd
import solara
import solara.lab
from component.model.state_manager import app_state

import logging

logger = logging.getLogger("zs.gdf_formatter")


def _parse_list_string(raw) -> Optional[list]:
    """Improved parser for various exactextract list formats"""
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if isinstance(raw, np.ndarray):
        return raw.tolist()

    if pd.isna(raw) or not isinstance(raw, str):
        return None

    s = raw.strip()
    if not s:
        return []

    # Most common case: [num num num ...]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []

        try:
            cleaned = re.sub(r"\s+", " ", inner).strip()
            tokens = cleaned.split()
            result = []
            for t in tokens:
                if t:
                    try:
                        result.append(int(t))
                    except ValueError:
                        result.append(float(t))
            return result
        except:
            pass

    return None


def _list_lengths(series: pd.Series) -> pd.Series:
    """Per-cell list length (0 if unparsable)."""
    return series.map(lambda v: len(_parse_list_string(v) or []))


def _detect_list_columns(df: gpd.GeoDataFrame, min_fraction: float = 0.7) -> List[str]:
    """Detect list-type columns from exactextract output more reliably."""
    result = []
    for col in df.columns:
        if col == df.geometry.name:  # skip geometry
            continue

        sample = df[col].dropna().head(30)  # increased sample size
        if len(sample) == 0:
            continue

        # Convert to string for detection
        sample_str = sample.astype(str).str.strip()

        hits = 0
        for val in sample_str:
            parsed = _parse_list_string(val)
            if parsed is not None and isinstance(parsed, list) and len(parsed) > 0:
                hits += 1
            # Extra heuristic: looks like array
            elif val.startswith("[") and val.endswith("]") and len(val) > 5:
                hits += 1

        hit_rate = hits / len(sample)

        if hit_rate >= min_fraction:
            result.append(col)
            logger.info(f"Detected list column: '{col}' (hit rate: {hit_rate:.2f}")
        else:
            logger.debug(f"Skipped column '{col}' (hit rate: {hit_rate:.2f})")

    return result


def _explode(gdf: gpd.GeoDataFrame, explode_cols: List[str]) -> gpd.GeoDataFrame:
    """Explode with robust parsing and logging."""

    logger.info(f"Explode started - columns: {explode_cols}")

    if gdf is None or len(gdf) == 0:
        logger.error("Input GeoDataFrame is empty")
        raise ValueError("Input GeoDataFrame is empty")

    try:
        work = gdf.copy()

        # Parse lists safely
        for col in explode_cols:
            work[col] = work[col].map(
                lambda v: (
                    _parse_list_string(v)
                    if isinstance(v, (str, np.ndarray))
                    else (v if isinstance(v, (list, tuple)) else [])
                )
            )

        logger.info("Parsing completed. Sample after parsing:")

        # Log sample for debugging
        for col in explode_cols:
            sample = work[col].iloc[0] if len(work) > 0 else None
            logger.info(
                f"  {col}: {sample} (type: {type(sample)}, len: {len(sample) if isinstance(sample, (list, tuple)) else 'N/A'})"
            )

        # Convert to pandas and explode
        exploded_pd = pd.DataFrame(work).explode(explode_cols, ignore_index=True)

        logger.info(f"Exploded successfully: {len(gdf)} → {len(exploded_pd)} rows")

        # Rebuild GeoDataFrame
        if gdf.geometry.name in exploded_pd.columns:
            result = gpd.GeoDataFrame(
                exploded_pd, geometry=gdf.geometry.name, crs=gdf.crs
            )
        else:
            result = gpd.GeoDataFrame(exploded_pd)

        logger.info(f"Explode completed. Final shape: {result.shape}")
        return result

    except Exception as e:
        logger.exception("Explode failed")
        raise


def _widen(
    gdf: gpd.GeoDataFrame,
    unique_col: str,
    value_cols: List[str],
    fill_missing: float = np.nan,
) -> gpd.GeoDataFrame:
    """Convert list columns to wide format with proper logging."""

    logger.info(f"Widen started - unique_col: '{unique_col}', value_cols: {value_cols}")

    if gdf is None or len(gdf) == 0:
        logger.error("Input GeoDataFrame is empty or None")
        raise ValueError("Input GeoDataFrame is empty")

    try:
        # Parse string lists to Python lists
        parsed = {}
        for col in [unique_col] + value_cols:
            series_parsed = gdf[col].map(_parse_list_string)
            parsed[col] = series_parsed

            valid = series_parsed.dropna()
            if len(valid) > 0:
                sample = valid.iloc[0]
                logger.info(
                    f"Parsed sample for '{col}': {sample} | length={len(sample) if sample else 0}"
                )

        # === BUILD WIDE TABLE ===
        unique_values: set = set()
        for lst in parsed[unique_col]:
            if isinstance(lst, list):
                unique_values.update(lst)

        unique_sorted = sorted(unique_values)
        logger.info(f"Found {len(unique_sorted)} unique values: {unique_sorted[:15]}")

        stat_names = [
            col.rsplit("_", 1)[-1] if "_" in col else col for col in value_cols
        ]

        exclude = {unique_col} | set(value_cols)
        base_cols = [c for c in gdf.columns if c not in exclude]

        new_rows = []
        for i, _ in gdf.iterrows():
            new_row = {c: gdf[c].iloc[i] for c in base_cols}

            uniq_list = parsed[unique_col].iloc[i] or []
            for u in unique_sorted:
                for val_col, stat in zip(value_cols, stat_names):
                    col_name = f"{u}_{stat}"
                    val_list = parsed[val_col].iloc[i] or []

                    if (
                        isinstance(uniq_list, list)
                        and isinstance(val_list, list)
                        and u in uniq_list
                    ):
                        pos = uniq_list.index(u)
                        new_row[col_name] = (
                            val_list[pos] if pos < len(val_list) else fill_missing
                        )
                    else:
                        new_row[col_name] = fill_missing

            new_rows.append(new_row)

        wide_df = pd.DataFrame(new_rows)
        logger.info(
            f"Created wide DataFrame with shape {wide_df.shape} "
            f"({len(wide_df.columns) - len(base_cols)} new columns added)"
        )

        # Rebuild GeoDataFrame
        if gdf.geometry.name in wide_df.columns:
            result = gpd.GeoDataFrame(wide_df, geometry=gdf.geometry.name, crs=gdf.crs)
        else:
            result = gpd.GeoDataFrame(wide_df)

        logger.info(
            f"Widen completed successfully. Final columns: {len(result.columns)}"
        )
        return result

    except Exception as e:
        logger.exception(f"Error during widening operation: {e}")
        raise


@solara.component  # type: ignore
def _ColumnBadge(col: str, is_list_col: bool):
    color = "#0d6efd" if is_list_col else "#6c757d"
    label = "list" if is_list_col else "scalar"
    with solara.Tooltip(f"Type: {label}"):
        solara.Text(
            col,
            style=(
                f"color:{color}; font-weight:{'600' if is_list_col else '400'}; "
                "font-size:0.82rem; font-family:monospace;"
            ),
        )


@solara.component  # type: ignore
def _InfoChip(text: str, bg: str = "#e8f4f8", fg: str = "#0d6efd"):
    solara.Text(
        text,
        style=(
            f"background:{bg}; color:{fg}; padding:2px 9px; border-radius:12px; "
            "font-size:0.78rem; font-family:monospace; display:inline-block;"
        ),
    )


# -------Method panels-----------------------------------


@solara.component  # type: ignore
def _ExplodePanel(working_gdf: gpd.GeoDataFrame, list_cols: List[str]):
    """UI for the Explode (long-format) method."""

    selected_cols = solara.use_reactive(cast(List[str], []))
    result_gdf: solara.Reactive[Optional[gpd.GeoDataFrame]] = solara.use_reactive(None)
    error_msg = solara.use_reactive("")

    # Precompute lengths
    length_series = {
        col: _list_lengths(pd.Series(working_gdf[col])) for col in list_cols
    }

    def _match_pct(a: str, b: str) -> int:
        return int((length_series[a] == length_series[b]).mean() * 100)

    def on_toggle(col: str, checked: bool):
        if checked and col not in selected_cols.value:
            selected_cols.value = selected_cols.value + [col]
        elif not checked:
            selected_cols.value = [c for c in selected_cols.value if c != col]
        result_gdf.value = None

    def apply_explode():
        error_msg.value = ""
        if not selected_cols.value:
            error_msg.value = "Select at least one column to explode."
            return
        try:
            result = _explode(working_gdf, selected_cols.value)
            result_gdf.value = result
            app_state.results_gdf_modified.value = result
            expansion = len(result) / len(working_gdf) if len(working_gdf) > 0 else 1
            solara.Success(
                f"✅ Exploded successfully! {len(working_gdf)} → {len(result)} rows ({expansion:.1f}×)",
                timeout=5,
            )
        except Exception as e:
            error_msg.value = f"Explode failed: {e}"
            logger.error(f"Explode error: {e}")

    if not list_cols:
        solara.Warning("No list-valued columns detected, No need to explode the data")
        return

    for col in list_cols:
        is_checked = col in selected_cols.value
        lengths = length_series[col]
        len_dist = ", ".join(
            f"len={k}: {v}" for k, v in sorted(lengths.value_counts().to_dict().items())
        )
        mismatch_note = ""
        if (
            is_checked
            and len(selected_cols.value) > 1
            and selected_cols.value[0] != col
        ):
            pct = _match_pct(selected_cols.value[0], col)
            if pct < 100:
                mismatch_note = (
                    f"only {pct}% of rows share list length with "
                    f"'{selected_cols.value[0]}' — mismatched rows will be dropped"
                )

        with solara.Row(style="align-items:flex-start; gap:8px; margin-bottom:4px;"):
            solara.Checkbox(
                label=col,
                value=is_checked,
                on_value=lambda chk, c=col: on_toggle(c, chk),
            )
            with solara.Column(style="gap:1px;"):
                solara.Text(
                    f"({len_dist})",
                    style="font-size:0.76rem; color:#6c757d; margin-top:3px;",
                )
                if mismatch_note:
                    solara.Text(
                        f"  {mismatch_note}",
                        style="font-size:0.76rem; color:#856404;",
                    )

    with solara.Row(style="align-items:center; gap:12px;"):
        solara.Button(
            "Explode to long format",
            on_click=apply_explode,
            color="primary",
            disabled=not selected_cols.value,
        )
        if selected_cols.value:
            solara.Text(
                f"Columns: {selected_cols.value}",
                style="font-size:0.8rem; color:#555;",
            )

    if error_msg.value:
        solara.Text(
            error_msg.value, style="color:#dc3545; font-size:0.85rem; margin-top:6px;"
        )

    if result_gdf.value is not None:
        orig_rows = len(working_gdf)
        new_rows = len(result_gdf.value)

        solara.Markdown(
            f"**Result — long format**\n\n"
            f"{orig_rows} rows × {len(working_gdf.columns)} cols → "
            f"{new_rows} rows × {len(result_gdf.value.columns)} cols "
            f"({new_rows / orig_rows:.1f}× expansion)"
        )

        solara.DataFrame(pd.DataFrame(result_gdf.value))


@solara.component  # type: ignore
def _WidenPanel(working_gdf: gpd.GeoDataFrame, list_cols: List[str]):
    """UI for the Widen (wide/pivot format) method."""

    default_unique = next(
        (
            c
            for c in list_cols
            if c.lower().endswith("unique") or c.lower().endswith("ids")
        ),
        list_cols[0] if list_cols else None,
    )

    # Reactive variables
    unique_col = solara.use_reactive(cast(Optional[str], default_unique))
    sel_value_cols = solara.use_reactive(cast(List[str], []))
    fill_missing_str = solara.use_reactive("NaN")
    result_gdf: solara.Reactive[Optional[gpd.GeoDataFrame]] = solara.use_reactive(None)
    error_msg = solara.use_reactive("")

    def on_unique_col(val):
        unique_col.value = val
        sel_value_cols.value = []
        result_gdf.value = None

    def on_toggle_value_col(col: str, checked: bool):
        if checked and col not in sel_value_cols.value:
            sel_value_cols.value = sel_value_cols.value + [col]
        elif not checked:
            sel_value_cols.value = [c for c in sel_value_cols.value if c != col]
        result_gdf.value = None

    def do_widen():
        error_msg.value = ""
        if not unique_col.value or not sel_value_cols.value:
            error_msg.value = (
                "Select a unique-values column and at least one value column."
            )
            return
        try:
            fill = (
                float(fill_missing_str.value)
                if fill_missing_str.value.strip().lower() != "nan"
                else np.nan
            )
            result = _widen(working_gdf, unique_col.value, sel_value_cols.value, fill)
            result_gdf.value = result
            app_state.results_gdf_modified.value = result
            solara.Success("Widened successfully and saved!", timeout=4)
        except Exception as e:
            error_msg.value = f"Widen failed: {e}"

    # derived: eligible value columns + mismatch info
    eligible_value_cols: List[str] = []
    length_mismatch_info: dict = {}
    if unique_col.value and unique_col.value in working_gdf.columns:
        u_lengths = _list_lengths(pd.Series(working_gdf[unique_col.value]))
        for col in list_cols:
            if col == unique_col.value:
                continue
            v_lengths = _list_lengths(pd.Series(working_gdf[col]))
            match_frac = (u_lengths == v_lengths).mean()
            eligible_value_cols.append(col)
            if match_frac < 1.0:
                length_mismatch_info[col] = round(match_frac * 100)

    # ------ render ------
    if not list_cols:
        solara.Warning("No list-valued columns detected.")
        return

    solara.Select(
        label="Unique-values column",
        value=unique_col.value,
        values=list_cols,
        on_value=on_unique_col,
        style="max-width:320px;",
    )

    if unique_col.value and unique_col.value in working_gdf.columns:
        sample_lengths = _list_lengths(pd.Series(working_gdf[unique_col.value]))
        len_dist = ", ".join(
            f"len={k}: {v}"
            for k, v in sorted(sample_lengths.value_counts().to_dict().items())
        )
        solara.Text(
            f"List-length distribution: {len_dist}",
            style="font-size:0.78rem; color:#6c757d; margin-top:2px;",
        )

        all_vals: set = set()
        for raw in working_gdf[unique_col.value].dropna():
            p = _parse_list_string(raw)
            if p:
                all_vals.update(p)

        with solara.Row(
            style="flex-wrap:wrap; gap:6px; margin-top:6px; margin-bottom:6px;"
        ):
            solara.Text(
                "Distinct values -> stubs:",
                style="font-size:0.8rem; color:#333; font-weight:600;",
            )
            for v in sorted(all_vals):
                _InfoChip(str(v))

    if unique_col.value and eligible_value_cols:
        for col in eligible_value_cols:
            is_checked = col in sel_value_cols.value
            mismatch_pct = length_mismatch_info.get(col)
            stat = col.rsplit("_", 1)[-1] if "_" in col else col

            with solara.Row(
                style="align-items:flex-start; gap:8px; margin-bottom:4px;"
            ):
                solara.Checkbox(
                    label=f'{col}   ->  stat = "{stat}"',
                    value=is_checked,
                    on_value=lambda chk, c=col: on_toggle_value_col(c, chk),
                )
                if mismatch_pct is not None:
                    solara.Text(
                        f"  {mismatch_pct}% of rows length-match '{unique_col.value}'",
                        style="font-size:0.76rem; color:#856404; margin-top:3px;",
                    )

        # live preview of new column names
        if sel_value_cols.value and unique_col.value:
            all_vals2: set = set()
            for raw in working_gdf[unique_col.value].dropna():
                p = _parse_list_string(raw)
                if p:
                    all_vals2.update(p)
            preview_names = [
                f"{u}_{vc.rsplit('_', 1)[-1] if '_' in vc else vc}"
                for u in sorted(all_vals2)
                for vc in sel_value_cols.value
            ]
            solara.Text(
                "New columns to be created:",
                style="font-size:0.82rem; font-weight:600; margin-top:10px;",
            )
            with solara.Row(style="flex-wrap:wrap; gap:6px; margin-bottom:8px;"):
                for name in preview_names:
                    _InfoChip(name)
    elif unique_col.value:
        solara.Text(
            "No other list-valued columns to pair with.",
            style="color:#6c757d; font-size:0.85rem;",
        )

    with solara.Row(style="align-items:center; gap:16px; flex-wrap:wrap;"):
        solara.InputText(
            label="Fill value for absent categories",
            value=fill_missing_str.value,
            on_value=lambda v: setattr(fill_missing_str, "value", v),
            style="max-width:200px;",
        )
        solara.Button(
            "Widen to wide format",
            on_click=do_widen,
            color="primary",
            disabled=(not unique_col.value or not sel_value_cols.value),
        )

    if error_msg.value:
        solara.Text(
            error_msg.value, style="color:#dc3545; font-size:0.85rem; margin-top:6px;"
        )

    if result_gdf.value is not None:
        orig_cols = len(working_gdf.columns)
        new_cols = len(result_gdf.value.columns)
        extra = new_cols - orig_cols + len(sel_value_cols.value) + 1

        solara.Text(
            "Result — wide format",
            f"{len(working_gdf)} rows x {orig_cols} cols  →  "
            f"{len(result_gdf.value)} rows x {new_cols} cols  "
            f"(+{extra} new wide columns)",
        )

        solara.DataFrame(pd.DataFrame(result_gdf.value))


@solara.component  # type: ignore
def ZonalDataFrameFormatterTile():
    """
    Main component for list-to-long / list-to-wide transformations.
    """

    # Reactive variables
    working_gdf = app_state.results_gdf
    list_cols = solara.use_reactive(cast(List[str], []))
    method = solara.use_reactive("skip")  # "explode" | "widen"
    show_raw = solara.use_reactive(False)
    load_error = solara.use_reactive("")

    def _update_list_cols():
        if working_gdf.value is not None:
            detected = _detect_list_columns(working_gdf.value)
            if detected != list_cols.value:  # avoid unnecessary updates
                list_cols.value = detected
        else:
            list_cols.value = []

    solara.use_effect(_update_list_cols, [working_gdf])  # type: ignore
    _update_list_cols()

    # -------------------- card shell --------------------

    with solara.Card(
        title="",
        style="max-width:960px; margin:auto; font-family:'Inter',sans-serif;",
    ):
        with solara.Row(style="flex-wrap:wrap; gap:10px; margin-bottom:8px;"):
            if working_gdf.value is not None:
                for col in working_gdf.value.columns:
                    _ColumnBadge(col, col in list_cols.value)

        solara.Checkbox(
            label="Show raw data preview (first 5 rows)",
            value=show_raw.value,
            on_value=lambda v: setattr(show_raw, "value", v),
        )

        if show_raw.value and working_gdf.value is not None:
            solara.DataFrame(pd.DataFrame(working_gdf.value.head(5)))

        # Method switcher
        with solara.ToggleButtonsSingle(value=method):
            solara.Button("Skip (Keep original)", icon_name="mdi-table",value="skip", text=True,)
            solara.Button(
                "WIDEN (wide format)",
                icon_name="mdi-table-column-plus-after",
                value="widen",
                text=True,
            )
            solara.Button(
                "EXPLODE (long format)",
                icon_name="mdi-table-row-plus-after",
                value="explode",
                text=True,
            )

        # Active panel
        if working_gdf.value is not None:
            if method.value == "explode":
                _ExplodePanel(working_gdf=working_gdf.value, list_cols=list_cols.value)
            elif method.value == "widen":
                _WidenPanel(working_gdf=working_gdf.value, list_cols=list_cols.value)
            else:
                pass
        else:
            solara.Warning("No data loaded yet.")

        if load_error.value:
            solara.Text(load_error.value, style="color:#dc3545;")
