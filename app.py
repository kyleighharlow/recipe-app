import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="Recipe Basket Nutrition Calculator", layout="wide")

DATA_PATH = Path(__file__).parent / "data" / "recipes.xlsx"
SHEET_NAME = "Sheet1"

# Columns expected in the provided spreadsheet
ID_COLS = ["Name", "Number", "Category", "Portion Size"]
MACRO_COLS = ["Kcal", "Pro (gm)", "Total Fat (gm)", "Carb (gm)"]
OTHER_NUTRIENT_COLS = [
    "Fiber (gm)", "Sugar (gm)", "Sat Fat (gm)",
    "Ca (mg)", "Potassium (mg)", "Sodium (mg)", "Added Sugar (g)",
    "Vit A (mcg RAE)", "Vit C (mg)", "Vit D (mcg)",
    "Omega-3’s (mg/g)", "Grams of Whole Grains",
]

def load_data() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)

    # Ensure expected columns exist (if not, fall back gracefully)
    for col in ID_COLS + MACRO_COLS + OTHER_NUTRIENT_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # Coerce nutrient columns to numeric
    nutrient_cols = MACRO_COLS + OTHER_NUTRIENT_COLS
    for c in nutrient_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Clean name field
    df["Name"] = df["Name"].astype(str).str.strip()

    return df

@st.cache_data(show_spinner=False)
def cached_data() -> pd.DataFrame:
    return load_data()

def init_state():
    st.session_state.setdefault("basket", [])  # list of dict items
    st.session_state.setdefault("page", "select")  # select | totals

def add_to_basket(row: pd.Series, portions: float):
    item = {
        "Name": row.get("Name", ""),
        "Number": row.get("Number", ""),
        "Category": row.get("Category", ""),
        "Portion Size": row.get("Portion Size", ""),
        "Portions": float(portions),
    }
    # Store per-portion nutrients
    for c in MACRO_COLS + OTHER_NUTRIENT_COLS:
        item[c] = float(row.get(c, np.nan)) if pd.notna(row.get(c, np.nan)) else np.nan

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
        vals = pd.to_numeric(bdf[c], errors="coerce")
        totals[c] = float((vals.fillna(0.0) * portions).sum())

    totals["Items"] = int(len(bdf))
    totals["Total Portions"] = float(portions.sum())
    return pd.Series(totals)

def fmt(v, unit=""):
    if pd.isna(v):
        return "—"
    # Show no decimals for large mg-style numbers, one decimal otherwise
    if abs(v) >= 100:
        s = f"{v:,.0f}"
    else:
        s = f"{v:,.1f}"
    return f"{s}{unit}"

def header():
    st.title("Recipe Basket Nutrition Calculator")
    st.caption("Search a recipe, add portions to your basket, then compute totals.")

def screen_select(df: pd.DataFrame):
    header()

    left, right = st.columns([1.2, 1.0], gap="large")

    with left:
        st.subheader("1) Find recipes")
        query = st.text_input("Search by recipe name", placeholder="e.g., chicken, lasagna, oatmeal…")
        cat_options = ["(Any)"] + sorted([c for c in df["Category"].dropna().astype(str).unique() if c.strip() != ""])
        category = st.selectbox("Filter by category (optional)", cat_options, index=0)

        filtered = df.copy()
        if query.strip():
            q = query.strip().lower()
            filtered = filtered[filtered["Name"].str.lower().str.contains(q, na=False)]
        if category != "(Any)":
            filtered = filtered[filtered["Category"].astype(str) == category]

        st.write(f"Matches: **{len(filtered):,}**")

        show_cols = ["Name", "Number", "Category", "Portion Size"] + MACRO_COLS
        preview = filtered[show_cols].head(200).reset_index(drop=True)

        st.dataframe(
            preview,
            use_container_width=True,
            height=420,
            hide_index=True
        )

        st.divider()
        st.subheader("2) Add to basket")

        if len(filtered) == 0:
            st.info("No matches. Try a different search term.")
            return

        # Choose from up to 200 shown, but map back to original filtered row by reusing the same head slice
        choices = preview["Name"].tolist()
        pick = st.selectbox("Select a recipe from the table above", choices)

        portions = st.number_input("Portions consumed", min_value=0.0, value=1.0, step=0.5)

        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("Add to basket", type="primary", use_container_width=True):
                row = filtered[filtered["Name"] == pick].iloc[0]
                add_to_basket(row, portions)
                st.success(f"Added: {pick} × {portions:g} portions")
        with colB:
            if st.button("Go to totals →", use_container_width=True, disabled=(len(st.session_state.basket) == 0)):
                st.session_state.page = "totals"

    with right:
        st.subheader("Basket")
        bdf = basket_df()
        if bdf.empty:
            st.info("Basket is empty.")
        else:
            display_cols = ["Name", "Portions"] + MACRO_COLS
            st.dataframe(bdf[display_cols], use_container_width=True, hide_index=True, height=350)

            st.caption("Remove items:")
            for i, item in enumerate(st.session_state.basket):
                cols = st.columns([0.8, 0.2])
                with cols[0]:
                    st.write(f"{i+1}. {item['Name']} × {item['Portions']:g}")
                with cols[1]:
                    if st.button("🗑️", key=f"del_{i}", help="Remove", use_container_width=True):
                        remove_from_basket(i)
                        st.experimental_rerun()

            totals = compute_totals(bdf)
            st.divider()
            st.subheader("Running totals (so far)")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Calories", fmt(totals.get("Kcal", 0.0)))
            m2.metric("Protein (g)", fmt(totals.get("Pro (gm)", 0.0)))
            m3.metric("Carbs (g)", fmt(totals.get("Carb (gm)", 0.0)))
            m4.metric("Fat (g)", fmt(totals.get("Total Fat (gm)", 0.0)))

def screen_totals(df: pd.DataFrame):
    header()

    bdf = basket_df()
    if bdf.empty:
        st.warning("Your basket is empty. Go back and add some recipes.")
        if st.button("← Back to selection"):
            st.session_state.page = "select"
        return

    totals = compute_totals(bdf)

    top = st.columns([1, 1, 1, 1, 1])
    top[0].metric("Items", int(totals.get("Items", 0)))
    top[1].metric("Total portions", fmt(totals.get("Total Portions", 0.0)))
    top[2].metric("Calories", fmt(totals.get("Kcal", 0.0)))
    top[3].metric("Protein (g)", fmt(totals.get("Pro (gm)", 0.0)))
    top[4].metric("Fat (g)", fmt(totals.get("Total Fat (gm)", 0.0)))

    st.metric("Carbohydrates (g)", fmt(totals.get("Carb (gm)", 0.0)))

    st.divider()
    st.subheader("Micronutrients & other totals")
    # Build a tidy table
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
        rows.append({"Nutrient": c, "Total": fmt(totals.get(c, 0.0), units.get(c, ""))})

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Basket details")
    show_cols = ["Name", "Portion Size", "Portions"] + MACRO_COLS + OTHER_NUTRIENT_COLS
    st.dataframe(bdf[show_cols], use_container_width=True, hide_index=True, height=420)

    c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
    with c1:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = "select"
    with c2:
        if st.button("Clear basket", use_container_width=True):
            st.session_state.basket = []
            st.session_state.page = "select"
            st.experimental_rerun()
    with c3:
        st.download_button(
            "Download basket as CSV",
            data=bdf.to_csv(index=False).encode("utf-8"),
            file_name="basket.csv",
            mime="text/csv",
            use_container_width=True,
        )

def main():
    init_state()

    # Data load
    if not DATA_PATH.exists():
        st.error(f"Missing data file: {DATA_PATH}")
        st.stop()

    df = cached_data()

    # Simple integrity hint
    if "Name" not in df.columns:
        st.error("Spreadsheet must contain a 'Name' column.")
        st.stop()

    if st.session_state.page == "totals":
        screen_totals(df)
    else:
        screen_select(df)

if __name__ == "__main__":
    main()
