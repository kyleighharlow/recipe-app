# Recipe Basket Nutrition Calculator (Streamlit)

This app uses the provided Excel spreadsheet as the backend.
Users can:
- Search recipes by name
- Enter portions consumed
- Add items to a basket
- Compute summed macro + micronutrient totals

## Run locally

```bash
cd recipe_basket_app
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Replace/update the backend spreadsheet

Put your updated file at:
`recipe_basket_app/data/recipes.xlsx`

(Keep the same column headers.)
