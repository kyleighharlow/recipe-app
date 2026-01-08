from pathlib import Path
import base64

import streamlit as st
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────
# Page config MUST be first Streamlit call
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DFAC Recipe Nutrition Calculator",
    layout="wide",
)


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
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    df = pd.read_excel(DATA_PATH)

    for col in ID_COLS + MACRO_COLS + OTHER_NUTRIENT_COLS:
        if col not in df.columns:
            df[col] = np.nan

    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["Name"] = df["Name"].astype(str).str.strip()
    return df


@st.cache_data(show_spinner=False)
def cached_data() -> pd.DataFrame:
    return load_data()


# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────
def init_state():
    st.session_state.setdefault("basket", [])
    st.session_state.setdefault("page", "select")


# ─────────────────────────────────────────────────────────────
# Basket helpers
# ─────────────────────────────────────────────────────────────
def add_to_basket(row: pd.Series, portions: float):
    item = {
        "Name": row["Name"],
        "Number": row["Number"],
        "Category": row["Category"],
        "Portion Size": row["Portion Size"],
        "Portions": float(portions),
    }
    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        item[c] = float(row[c]) if pd.notna(row[c]) else np.nan

    st.session_state.basket.append(item)


def remove_from_basket(index: int):
    st.session_state.basket.pop(index)


def basket_df() -> pd.DataFrame:
    if not st.session_state.basket:
        return pd.DataFrame(columns=["Name", "Portions"] + MACRO_COLS)
    return pd.DataFrame(st.session_state.basket)


def compute_totals(bdf: pd.DataFrame) -> pd.Series:
    if bdf.empty:
        return pd.Series(dtype=float)

    totals = {}
    portions = pd.to_numeric(bdf["Portions"], errors="coerce").fillna(0.0)

    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        vals = pd.to_numeric(bdf[c], errors="coerce").fillna(0.0)
        totals[c] = float((vals * portions).sum())

    totals["Items"] = int(len(bdf))
    totals["Total Portions"] = float(portions.sum())
    return pd.Series(totals)


def fmt(v, unit=""):
    if pd.isna(v):
        return "—"
    if abs(v) >= 100:
        s = f"{v:,.0f}"
    else:
        s = f"{v:,.1f}"
    return f"{s}{unit}"


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────
def header():
    st.title("DFAC Recipe Nutrition Calculator")
    st.caption("Search a recipe, add portions to your basket, then compute totals.")


def screen_select(df: pd.DataFrame):
    header()

    left, right = st.columns([1.2, 1.0], gap="large")

    with left:
        st.subheader("1) Find recipes")
        query = st.text_input("Search by recipe name")
        cat_options = ["(Any)"] + sorted(df["Category"].dropna().astype(str).unique())
        category = st.selectbox("Category (optional)", cat_options)

        filtered = df.copy()
        if query.strip():
            filtered = filtered[filtered["Name"].str.contains(query, case=False, na=False)]
        if category != "(Any)":
            filtered = filtered[filtered["Category"] == category]

        st.write(f"Matches: **{len(filtered):,}**")

        show_cols = ["Name", "Number", "Category", "Portion Size"] + MACRO_COLS
        preview = filtered[show_cols].head(200).reset_index(drop=False)

        st.dataframe(preview[show_cols], use_container_width=True, height=420)

        st.divider()
        st.subheader("2) Add to basket")

        if preview.empty:
            st.info("No matches.")
            return

        preview["Pick"] = preview["Name"] + "  (#" + preview["Number"].astype(str) + ")"
        pick = st.selectbox("Select recipe", preview["Pick"])

        portions = st.number_input("Portions consumed", min_value=0.0, value=1.0, step=0.5)

        if st.button("Add to basket", type="primary"):
            picked = preview.loc[preview["Pick"] == pick].iloc[0]
            row = df.loc[picked["index"]]
            add_to_basket(row, portions)
            st.success(f"Added {row['Name']} × {portions:g}")

        if st.button("Go to totals →", disabled=len(st.session_state.basket) == 0):
            st.session_state.page = "totals"

    with right:
        st.subheader("Basket")
        bdf = basket_df()

        if bdf.empty:
            st.info("Basket is empty.")
        else:
            st.dataframe(bdf[["Name", "Portions"] + MACRO_COLS], use_container_width=True)

            for i, item in enumerate(st.session_state.basket):
                cols = st.columns([0.85, 0.15])
                cols[0].write(f"{item['Name']} × {item['Portions']}")
                if cols[1].button("🗑️", key=f"del_{i}"):
                    remove_from_basket(i)
                    st.experimental_rerun()

            totals = compute_totals(bdf)
            st.divider()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Calories", fmt(totals["Kcal"]))
            m2.metric("Protein (g)", fmt(totals["Pro (gm)"]))
            m3.metric("Carbs (g)", fmt(totals["Carb (gm)"]))
            m4.metric("Fat (g)", fmt(totals["Total Fat (gm)"]))


def screen_totals(df: pd.DataFrame):
    header()
    bdf = basket_df()

    if bdf.empty:
        st.warning("Basket is empty.")
        if st.button("← Back"):
            st.session_state.page = "select"
        return

    totals = compute_totals(bdf)

    cols = st.columns(5)
    cols[0].metric("Items", totals["Items"])
    cols[1].metric("Total portions", fmt(totals["Total Portions"]))
    cols[2].metric("Calories", fmt(totals["Kcal"]))
    cols[3].metric("Protein (g)", fmt(totals["Pro (gm)"]))
    cols[4].metric("Fat (g)", fmt(totals["Total Fat (gm)"]))

    st.metric("Carbohydrates (g)", fmt(totals["Carb (gm)"]))

    st.divider()
    rows = []
    units = {
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

    for c in OTHER_NUTRIENT_COLS:
        rows.append({"Nutrient": c, "Total": fmt(totals[c], units.get(c, ""))})

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()
    st.dataframe(
        bdf[["Name", "Portion Size", "Portions"] + MACRO_COLS + OTHER_NUTRIENT_COLS],
        use_container_width=True,
        height=420,
    )

    if st.button("← Back"):
        st.session_state.page = "select"

    if st.button("Clear basket"):
        st.session_state.basket = []
        st.session_state.page = "select"
        st.experimental_rerun()

    st.download_button(
        "Download basket as CSV",
        data=bdf.to_csv(index=False).encode("utf-8"),
        file_name="basket.csv",
        mime="text/csv",
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

    if st.session_state.page == "totals":
        screen_totals(df)
    else:
        screen_select(df)


if __name__ == "__main__":
    main()

