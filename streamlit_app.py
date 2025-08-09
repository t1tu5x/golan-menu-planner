#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ====== Константы ======
DATA_DIR = "data"
LOCAL_MENU_LOG = os.path.join(DATA_DIR, "menus.csv")
IL_TZ = ZoneInfo("Asia/Jerusalem")

REQUIRED_COLUMNS = [
    "id", "dish_name_hebrew", "ingredients",
    "gross_yield_per_person", "gross_yield_per_gn1_1",
    "preparation_method", "notes"
]

GROUP_KEYS_ORDER = [
    "grains_and_pasta", "baked_vegetables", "potato_dishes",
    "fish_dishes", "chicken_dishes", "meat_dishes",
    "fried_snacks", "stuffed_vegetables", "soups"
]

GROUP_LABELS_HE = {
    "grains_and_pasta": "🍝 דגנים ופסטה",
    "baked_vegetables": "🍠 ירקות אפויים",
    "potato_dishes": "🥔 מנות מתפוחי אדמה",
    "fish_dishes": "🐟 מנות דגים",
    "chicken_dishes": "🍗 מנות עוף",
    "meat_dishes": "🥩 מנות בשר",
    "fried_snacks": "🍟 נשנושים מטוגנים",
    "stuffed_vegetables": "🍆 ירקות ממולאים",
    "soups": "🍲 מרקים",
}

# ====== UI настройки (RTL, шрифт, "кухонный" стиль) ======
st.set_page_config(page_title="🏨 מלון גולן — מתכנן תפריט", page_icon="🍽️", layout="wide")

CUSTOM_CSS = """
<style>
/* Правильное направление для иврита */
html, body, [data-testid="stAppViewContainer"] * {
  direction: rtl;
  text-align: right;
}

/* Нежные кухонные оттенки */
:root {
  --bg: #fffdf8;
  --card: #ffffff;
  --accent: #2e7d32; /* зелёный как кухня/трава/свежесть */
  --accent-soft: #e8f5e9;
}

/* Фон приложения */
[data-testid="stAppViewContainer"] {
  background: var(--bg);
}

/* Карточки (контейнеры) */
.block-container {
  padding-top: 1rem;
}

/* Заголовки */
h1, h2, h3 {
  font-weight: 800;
}

/* Таблица печати */
.print-table {
  border-collapse: collapse;
  width: 100%;
  background: var(--card);
}
.print-table th, .print-table td {
  border: 1px solid #e0e0e0;
  padding: 8px 10px;
}
.print-table th {
  background: var(--accent-soft);
}

/* Кнопки — закруглённые */
.stButton>button {
  border-radius: 12px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ====== Helpers: загрузка CSV групп ======
@st.cache_data(show_spinner=False)
def load_group_csv(group_key: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{group_key}.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    # строгая проверка структуры
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        # вернём пустую, но покажем предупреждение
        st.warning(f"לקובץ חסרות עמודות: {path} — {missing}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    return df

# ====== Google Sheets ======
def gsheets_enabled() -> bool:
    return bool(st.secrets.get("gsheets", {}).get("enabled", False))

def get_gspread_client():
    import gspread
    from google.oauth2.service_account import Credentials

    conf = st.secrets["gsheets"]
    creds = Credentials.from_service_account_info(
        dict(conf),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def append_menu_to_gsheets(row: dict):
    """
    row: {"id": int, "dishes": "a, b, c", "at_date": "YYYY-MM-DD HH:MM:SS"}
    """
    client = get_gspread_client()
    spreadsheet_id = st.secrets["gsheets"]["spreadsheet_id"]
    sheet_name = st.secrets["gsheets"].get("sheet_name", "MENUS_LOG")

    sh = client.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(sheet_name)
    except Exception:
        # создаём лист с заголовками
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=3)
        ws.update("A1:C1", [["id", "dishes", "at_date"]])

    ws.append_row([row["id"], row["dishes"], row["at_date"]], value_input_option="USER_ENTERED")

def append_menu_to_local_csv(row: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(LOCAL_MENU_LOG):
        pd.DataFrame([row]).to_csv(LOCAL_MENU_LOG, index=False)
    else:
        df = pd.read_csv(LOCAL_MENU_LOG)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(LOCAL_MENU_LOG, index=False)

def next_menu_id_local() -> int:
    if not os.path.exists(LOCAL_MENU_LOG):
        return 1
    try:
        df = pd.read_csv(LOCAL_MENU_LOG)
        if df.empty or "id" not in df.columns:
            return 1
        return int(df["id"].max()) + 1
    except Exception:
        return 1

def next_menu_id_gsheets() -> int:
    try:
        client = get_gspread_client()
        spreadsheet_id = st.secrets["gsheets"]["spreadsheet_id"]
        sheet_name = st.secrets["gsheets"].get("sheet_name", "MENUS_LOG")
        sh = client.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet(sheet_name)
        except Exception:
            # нет листа — начнём с 1
            return 1
        vals = ws.get_all_records()  # список dict
        if not vals:
            return 1
        max_id = max([int(v.get("id", 0)) for v in vals if str(v.get("id", "")).isdigit()] or [0])
        return max_id + 1
    except Exception:
        # если секретов/доступа нет
        return next_menu_id_local()

def next_menu_id() -> int:
    return next_menu_id_gsheets() if gsheets_enabled() else next_menu_id_local()

# ====== Инициализация состояния ======
if "choices" not in st.session_state:
    st.session_state.choices = {k: "-" for k in GROUP_KEYS_ORDER}
if "preview" not in st.session_state:
    st.session_state.preview = pd.DataFrame(columns=["#", "שם המנה", "הערות"])

# ====== Заголовок ======
st.markdown("## 🍽️ מתכנן תפריט — מלון גולן")

st.caption("בחרו מנות מכל קבוצה למטה, לחצו **'בנה תפריט'**, ואז ניתן להדפיס ולשלוח ל-Google Sheets.")

# ====== Форма выбора блюд ======
with st.container():
    cols = st.columns(3)
    all_dfs = {}

    for i, key in enumerate(GROUP_KEYS_ORDER):
        df = load_group_csv(key)
        all_dfs[key] = df

        options = ["-"] + list(df["dish_name_hebrew"].dropna().astype(str)) if not df.empty else ["-"]
        with cols[i % 3]:
            st.selectbox(
                GROUP_LABELS_HE.get(key, key),
                options=options,
                index=0,
                key=f"sel_{key}",
                help="בחרו מנה מהרשימה (או - כדי לא לבחור)"
            )

# ====== Кнопка: сформировать меню ======
def build_preview():
    rows = []
    counter = 1
    for key in GROUP_KEYS_ORDER:
        chosen = st.session_state.get(f"sel_{key}", "-")
        if chosen and chosen != "-":
            df = all_dfs.get(key, pd.DataFrame(columns=REQUIRED_COLUMNS))
            notes = ""
            if not df.empty:
                row = df.loc[df["dish_name_hebrew"] == chosen].head(1)
                if not row.empty and pd.notna(row.iloc[0].get("notes", "")):
                    notes = str(row.iloc[0]["notes"])
            rows.append({"#": counter, "שם המנה": chosen, "הערות": notes})
            counter += 1

    st.session_state.preview = pd.DataFrame(rows, columns=["#", "שם המנה", "הערות"])

st.button("🧾 בנה תפריט", type="primary", on_click=build_preview)

# ====== Предпросмотр (для печати) ======
if not st.session_state.preview.empty:
    st.subheader("תצוגת תפריט (להדפסה)")
    st.dataframe(st.session_state.preview, use_container_width=True, hide_index=True)

    # HTML для «чистой печати»
    html_table = st.session_state.preview.to_html(index=False, classes="print-table")
    printable_html = f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <style>{CUSTOM_CSS}</style>
      <title>תפריט להדפסה</title>
    </head>
    <body>
      <h2>🧾 תפריט</h2>
      {html_table}
      <p style="margin-top:10px;">נבנה בתאריך: {datetime.now(IL_TZ).strftime("%Y-%m-%d %H:%M:%S")}</p>
    </body>
    </html>
    """
    st.download_button(
        "⬇️ הורד כ־HTML להדפסה",
        data=printable_html.encode("utf-8"),
        file_name=f"menu_{datetime.now(IL_TZ).strftime('%Y%m%d_%H%M')}.html",
        mime="text/html"
    )

# ====== Кнопка: отправить лог в Google Sheets / CSV ======
def save_menu():
    if st.session_state.preview.empty:
        st.warning("אין נתונים — קודם בנו תפריט.")
        return

    dishes_list = [str(x) for x in st.session_state.preview["שם המנה"].tolist()]
    row = {
        "id": next_menu_id(),
        "dishes": ", ".join(dishes_list),
        "at_date": datetime.now(IL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        if gsheets_enabled():
            append_menu_to_gsheets(row)
            st.success(f"נשמר ב־Google Sheets (id={row['id']}).")
        else:
            append_menu_to_local_csv(row)
            st.success(f"נשמר מקומית: data/menus.csv (id={row['id']}).")
    except Exception as e:
        st.error(f"תקלה בשמירה: {e}")

st.button("✅ שלח ל־Google Sheets / CSV", on_click=save_menu)
