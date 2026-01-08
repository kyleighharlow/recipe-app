from __future__ import annotations

from pathlib import Path
import base64
import uuid

import streamlit as st
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────
# Page config MUST be first Streamlit call
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="DFAC Recipe Nutrition Calculator", layout="wide")


# ─────────────────────────────────────────────────────────────
# Background logo (faded watermark)
# ─────────────────────────────────────────────────────────────
def set_bg_logo(image_path: str, opacity: float = 0.08):
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    st.markdown(
        f"""
        <style>
        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            background-image: url("data:image/png;base64,{b64}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: 55%;
            opacity: {opacity};
            pointer-events: none;
            z-index: 0;
        }}
        .stApp > div {{
            position: relative;
            z-index: 1;
        }}

        /* Slightly smaller text helper */
        .small-note {{
            font-size: 0.9rem;
            opacity: 0.9;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# Call after set_page_config, before UI
set_bg_logo("assets/logo.png", opacity=0.07)


# ─────────────────────────────────────────────────────────────
# Data configuration
# ─────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "data" / "recipes.xlsx"

ID_COLS = ["Name", "Number", "Category", "Portion Size"]
MACRO_COLS = ["Kcal", "Pro (gm)", "Total Fat (gm)", "Carb (gm)"]
OTHER_NUTRIENT_COLS = [
    "Fiber (gm)", "Sugar (gm)", "Sat Fat (gm)",
    "Ca (mg)", "Potassium (mg)", "Sodium (mg)", "Added Sugar (g)",
    "Vit A (mcg RAE)", "Vit C (mg)", "Vit D (mcg)",
    "Omega-3’s (mg/g)", "Grams of Whole Grains",
]


# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH)  # default: first sheet

    # Ensure expected columns exist
    for col in ID_COLS + MACRO_COLS + OTHER_NUTRIENT_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # Coerce nutrient columns to numeric
    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Clean name field
    df["Name"] = df["Name"].astype(str).str.strip()

    return df


@st.cache_data(show_spinner=False)
def cached_data() -> pd.DataFrame:
    return load_data()


# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────
def init_state():
    st.session_state.setdefault("meal", [])  # list of dict items
    st.session_state.setdefault("page", "select")  # select | totals
    st.session_state.setdefault("selected_df_index", None)  # original df index of clicked recipe


# ─────────────────────────────────────────────────────────────
# Meal helpers
# ─────────────────────────────────────────────────────────────
def add_to_meal(row: pd.Series, portions: float):
    item = {
        "_id": str(uuid.uuid4()),
        "Name": row.get("Name", ""),
        "Number": row.get("Number", ""),
        "Category": row.get("Category", ""),
        "Portion Size": row.get("Portion Size", ""),
        "Portions": float(portions),
    }
    # Store per-portion nutrients
    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        v = row.get(c, np.nan)
        item[c] = float(v) if pd.notna(v) else np.nan

    st.session_state.meal.append(item)


def delete_from_meal(item_id: str):
    st.session_state.meal = [x for x in st.session_state.meal if x.get("_id") != item_id]


def meal_df() -> pd.DataFrame:
    if not st.session_state.meal:
        return pd.DataFrame(columns=["Name", "Portions"])
    return pd.DataFrame(st.session_state.meal)


def compute_totals(mdf: pd.DataFrame) -> pd.Series:
    if mdf.empty:
        return pd.Series(dtype=float)

    totals = {}
    portions = pd.to_numeric(mdf["Portions"], errors="coerce").fillna(0.0)

    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        vals = pd.to_numeric(mdf[c], errors="coerce").fillna(0.0)
        totals[c] = float((vals * portions).sum())

    totals["Items"] = int(len(mdf))
    totals["Total Portions"] = float(portions.sum())
    return pd.Series(totals)


def fmt_num(v: float, decimals_small: int = 1) -> str:
    if pd.isna(v):
        return "—"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:,.{decimals_small}f}"


def header():
    st.title("DFAC Recipe Nutrition Calculator")
    st.caption("Search a recipe, add portions to your meal, then compute totals.")


# ─────────────────────────────────────────────────────────────
# Clipboard helper (HTML/JS)
# ─────────────────────────────────────────────────────────────
def quick_copy_block(text: str):
    """
    Renders a 'Quick Copy' button that copies `text` to clipboard via JS.
    Also includes a fallback text area for manual copy.
    """
    # Escape for JS template literal
    safe = (
        text.replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
    )

    st.markdown(
        """
        <div class="small-note">
        Copy and paste your meal information into a Quick Add entry using your favorite nutrition tracker!
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.components.v1.html(
        f"""
        <div style="display:flex; gap: 0.5rem; align-items:center; margin: 0.25rem 0 0.75rem 0;">
          <button
            style="
              padding: 0.5rem 0.9rem;
              border-radius: 0.5rem;
              border: 1px solid rgba(49, 51, 63, 0.2);
              background: white;
              cursor: pointer;
              font-weight: 600;
            "
            onclick="navigator.clipboard.writeText(`{safe}`).then(() => {{
              const el = document.getElementById('copy_status');
              if (el) el.innerText = 'Copied to clipboard ✅';
              setTimeout(() => {{ if (el) el.innerText = ''; }}, 1800);
            }}).catch(() => {{
              const el = document.getElementById('copy_status');
              if (el) el.innerText = 'Clipboard blocked — use manual copy below.';
              setTimeout(() => {{ if (el) el.innerText = ''; }}, 2200);
            }})"
          >
            Quick Copy
          </button>
          <span id="copy_status" style="font-size: 0.9rem; opacity: 0.85;"></span>
        </div>
        """,
        height=70,
    )

    # Fallback (manual copy)
    st.text_area("Meal totals (copy if needed)", value=text, height=220)


def build_tracker_text(totals: pd.Series) -> str:
    """
    Produces a clipboard-friendly block suitable for most "Quick Add" flows.
    Lead with the common macro line, then include the rest as lines.
    """
    # Common trackers usually care most about kcal + macros (and often fiber).
    kcal = fmt_num(totals.get("Kcal", 0.0), decimals_small=0)
    pro = fmt_num(totals.get("Pro (gm)", 0.0))
    carb = fmt_num(totals.get("Carb (gm)", 0.0))
    fat = fmt_num(totals.get("Total Fat (gm)", 0.0))
    fiber = fmt_num(totals.get("Fiber (gm)", 0.0))

    lines = [
        f"Calories: {kcal}",
        f"Carbohydrates: {carb} g",
        f"Fat: {fat} g",
        f"Protein: {pro} g",
        f"Fiber: {fiber} g",
        "",
        "---- Full nutrition totals ----",
    ]

    # Include everything (macros + micros), in a predictable order
    all_cols = MACRO_COLS + OTHER_NUTRIENT_COLS
    units = {
        "Kcal": "",
        "Pro (gm)": " g",
        "Carb (gm)": " g",
        "Total Fat (gm)": " g",
        "Fiber (gm)": " g",
        "Sugar (gm)": " g",
        "Sat Fat (gm)": " g",
        "Ca (mg)": " mg",
        "Potassium (mg)": " mg",
        "Sodium (mg)": " mg",
        "Added Sugar (g)": " g",
        "Vit A (mcg RAE)": " mcg RAE",
        "Vit C (mg)": " mg",
        "Vit D (mcg)": " mcg",
        "Omega-3’s (mg/g)": " mg",
        "Grams of Whole Grains": " g",
    }

    for c in all_cols:
        v = totals.get(c, 0.0)
        if c == "Kcal":
            lines.append(f"{c}: {fmt_num(v, decimals_small=0)}{units.get(c,'')}")
        else:
            lines.append(f"{c}: {fmt_num(v)}{units.get(c,'')}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Screen 1: Select + Meal build
# ─────────────────────────────────────────────────────────────
def screen_select(df: pd.DataFrame):
    header()

    left, right = st.columns([1.25, 0.95], gap="large")

    with left:
        st.subheader("1) Find recipes")
        query = st.text_input("Search by recipe name", placeholder="e.g., chicken, lasagna, oatmeal…")

        # Filter ONLY by name (category filter removed)
        filtered = df.copy()
        if query.strip():
            q = query.strip().lower()
            filtered = filtered[filtered["Name"].astype(str).str.lower().str.contains(q, na=False)]

        st.write(f"Matches: **{len(filtered):,}**")

        # Table columns requested
        show_cols = ["Name", "Portion Size", "Kcal", "Pro (gm)", "Carb (gm)", "Total Fat (gm)"]

        # Keep original df index for accurate selection mapping
        preview = filtered[show_cols].head(400).copy()
        preview.insert(0, "_df_index", filtered.head(400).index)

        # Click-to-select table (Streamlit row selection feature)
        selection = st.dataframe(
            preview[show_cols],
            use_container_width=True,
            height=440,
            hide_index=True,
            key="recipes_table",
            on_select="rerun",
            selection_mode="single-row",
        )

        # If a row is clicked, store its original df index
        try:
            selected_rows = selection.get("selection", {}).get("rows", [])
        except Exception:
            selected_rows = []

        if selected_rows:
            row_pos = int(selected_rows[0])
            st.session_state.selected_df_index = int(preview.iloc[row_pos]["_df_index"])

    with right:
        st.subheader("2) Add to meal")

        selected_idx = st.session_state.selected_df_index
        if selected_idx is None or selected_idx not in df.index:
            st.info("Click a recipe row in the table to select it.")
            selected_name = ""
            selected_portion = ""
        else:
            selected_name = str(df.loc[selected_idx, "Name"])
            selected_portion = str(df.loc[selected_idx, "Portion Size"])

        st.text_input("Select Recipe", value=selected_name, disabled=True)
        st.text_input("Portion Size", value=selected_portion, disabled=True)

        portions = st.number_input(
            "Portions consumed",
            min_value=0.0,
            value=1.00,
            step=0.25,
            format="%.2f",
        )

        add_disabled = (selected_idx is None or selected_idx not in df.index)
        if st.button("Add to Meal", type="primary", use_container_width=True, disabled=add_disabled):
            row = df.loc[selected_idx]
            add_to_meal(row, portions)
            st.success(f"Added: {row['Name']} × {portions:.2f} portions")

        st.divider()
        st.subheader("Meal Selections")

        mdf = meal_df()
        if mdf.empty:
            st.info("No items added yet.")
        else:
            # Only show meal items (no running nutrition totals on this page)
            st.dataframe(
                mdf[["Name", "Portion Size", "Portions"]],
                use_container_width=True,
                hide_index=True,
                height=260,
            )

            st.caption("Delete individual selections:")
            for item in st.session_state.meal:
                cols = st.columns([0.88, 0.12])
                cols[0].write(f"• {item.get('Name','')} × {float(item.get('Portions',0.0)):.2f}")
                if cols[1].button("🗑️", key=f"del_{item['_id']}", use_container_width=True, help="Delete"):
                    delete_from_meal(item["_id"])
                    st.rerun()

        st.divider()
        if st.button("Go to Totals", use_container_width=True, disabled=(len(st.session_state.meal) == 0)):
            st.session_state.page = "totals"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Screen 2: Totals
# ─────────────────────────────────────────────────────────────
def screen_totals(df: pd.DataFrame):
    header()

    mdf = meal_df()
    if mdf.empty:
        st.warning("Your meal is empty. Go back and add some recipes.")
        if st.button("← Back to selection"):
            st.session_state.page = "select"
            st.rerun()
        return

    totals = compute_totals(mdf)

    # Top cards requested: Calories, Protein, Carbs, Fat, Fiber
    cals = totals.get("Kcal", 0.0)
    pro = totals.get("Pro (gm)", 0.0)
    carbs = totals.get("Carb (gm)", 0.0)
    fat = totals.get("Total Fat (gm)", 0.0)
    fiber = totals.get("Fiber (gm)", 0.0)

    top = st.columns(5)
    top[0].metric("Calories", fmt_num(cals, decimals_small=0))
    top[1].metric("Protein (g)", fmt_num(pro))
    top[2].metric("Carbohydrates (g)", fmt_num(carbs))
    top[3].metric("Fat (g)", fmt_num(fat))
    top[4].metric("Fiber (g)", fmt_num(fiber))

    st.divider()

    # Smaller-font full nutrition + quick copy
    st.subheader("Full nutrition totals (Quick Add format)")
    tracker_text = build_tracker_text(totals)
    quick_copy_block(tracker_text)

    st.divider()
    st.subheader("Meal details")
    show_cols = ["Name", "Portion Size", "Portions"] + MACRO_COLS + OTHER_NUTRIENT_COLS
    st.dataframe(mdf[show_cols], use_container_width=True, hide_index=True, height=420)

    c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
    with c1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = "select"
            st.rerun()
    with c2:
        if st.button("Clear meal", use_container_width=True):
            st.session_state.meal = []
            st.session_state.page = "select"
            st.rerun()
    with c3:
        st.download_button(
            "Download meal as CSV",
            data=mdf.drop(columns=["_id"], errors="ignore").to_csv(index=False).encode("utf-8"),
            file_name="meal.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    init_state()

    if not DATA_PATH.exists():
        st.error(f"Missing data file: {DATA_PATH}")
        st.stop()

    df = cached_data()

    if "Name" not in df.columns:
        st.error("Spreadsheet must contain a 'Name' column.")
        st.stop()

    if st.session_state.page == "totals":
        screen_totals(df)
    else:
        screen_select(df)


if __name__ == "__main__":
    main()


