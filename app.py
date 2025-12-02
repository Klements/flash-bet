import streamlit as st
import pandas as pd

st.set_page_config(page_title="Statistiche squadre (football-data.co.uk)", layout="wide")

# -----------------------------
# LOGIN
# -----------------------------
def check_login():
    users = st.secrets.get("users", {})

    # Se già loggato → mostra solo il profilo
    if st.session_state.get("logged_in", False):
        username = st.session_state["username"]

        with st.sidebar:
            st.markdown("### 👋 Benvenuto")
            st.markdown(f"**{username}**")
            st.markdown("---")

            # Mostra icona profilo + nome
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:32px;">👤</span>
                    <span style="font-size:18px;">{username}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return True

    # Se NON loggato → mostra form login
    with st.sidebar:
        st.title("Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Entra")

        if login_button:
            if username in users and password == users[username]:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username

                # Aggiorna la UI
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()
            else:
                st.error("Credenziali errate.")

    return False


# Blocca l'app finché non è loggato
if not check_login():
    st.stop()

st.title("Statistiche medie ultime 5 e 10 partite per squadra")
st.caption("Puoi caricare più CSV (anche di campionati diversi). Le squadre saranno aggregate senza duplicati.")


# -----------------------------
# Funzioni di utilità
# -----------------------------
def prepara_dataframe(file_obj) -> pd.DataFrame | None:
    """Legge un singolo CSV football-data.co.uk e fa i controlli base."""
    try:
        df = pd.read_csv(file_obj)
    except Exception as e:
        st.error(f"Errore nella lettura del CSV '{getattr(file_obj, 'name', '')}': {e}")
        return None

    # Proviamo a parsare la data se presente
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    # Controllo colonne essenziali
    required_cols = {"HomeTeam", "AwayTeam"}
    if not required_cols.issubset(df.columns):
        st.error(
            f"Il file '{getattr(file_obj, 'name', '')}' non contiene le colonne minime richieste "
            "'HomeTeam' e 'AwayTeam'. Verifica che il file sia nel formato standard football-data.co.uk."
        )
        return None

    return df


def calcola_statistiche_squadra(df: pd.DataFrame, team: str, n_matches: int = 5):
    """
    Calcola le statistiche medie per una squadra sulle ultime n partite (max n),
    dal punto di vista della squadra (gol fatti, subiti, tiri, ecc.).
    Restituisce:
    - matches: dataframe con le partite considerate
    - stats_df: dataframe 1-colonna con le medie
    """

    # Filtra le partite in cui la squadra è home o away
    team_matches = df[(df["HomeTeam"] == team) | (df["AwayTeam"] == team)].copy()

    if team_matches.empty:
        return team_matches, None

    # Ordina per data (se disponibile) dalla più recente
    if "Date" in team_matches.columns:
        team_matches = team_matches.sort_values("Date", ascending=False)

    # Prendi al massimo le ultime n partite
    team_matches = team_matches.head(n_matches)
    n_eff = len(team_matches)

    stats = {}

    # Helper per colonne simmetriche casa/trasferta
    def add_stat(name: str, home_col: str, away_col: str):
        if home_col not in team_matches.columns or away_col not in team_matches.columns:
            return

        mask_home = team_matches["HomeTeam"] == team
        mask_away = team_matches["AwayTeam"] == team

        # Serie con il valore "dal punto di vista della squadra"
        vals = pd.Series(index=team_matches.index, dtype="float64")
        vals[mask_home] = team_matches.loc[mask_home, home_col]
        vals[mask_away] = team_matches.loc[mask_away, away_col]

        stats[name] = vals.mean()

    # Gol
    add_stat("Gol fatti (FT)", "FTHG", "FTAG")
    add_stat("Gol subiti (FT)", "FTAG", "FTHG")
    add_stat("Gol fatti (HT)", "HTHG", "HTAG")
    add_stat("Gol subiti (HT)", "HTAG", "HTHG")

    # Tiri / corner / falli / cartellini
    add_stat("Tiri totali", "HS", "AS")
    add_stat("Tiri in porta", "HST", "AST")
    add_stat("Calci d'angolo", "HC", "AC")
    add_stat("Falli commessi", "HF", "AF")
    add_stat("Ammonizioni", "HY", "AY")
    add_stat("Espulsioni", "HR", "AR")

    # W / D / L sulle partite considerate
    if "FTR" in team_matches.columns:
        results = []
        for _, row in team_matches.iterrows():
            res_code = row["FTR"]  # H/D/A
            if row["HomeTeam"] == team:
                if res_code == "H":
                    results.append("W")
                elif res_code == "A":
                    results.append("L")
                else:
                    results.append("D")
            else:  # team è away
                if res_code == "A":
                    results.append("W")
                elif res_code == "H":
                    results.append("L")
                else:
                    results.append("D")

        stats["Vittorie"] = results.count("W")
        stats["Pareggi"] = results.count("D")
        stats["Sconfitte"] = results.count("L")

    if not stats:
        return team_matches, None

    stats_series = pd.Series(stats, name=f"Media ultime {n_eff} partite")
    stats_df = stats_series.to_frame()

    return team_matches, stats_df


# -----------------------------
# UI: Upload di uno o più file
# -----------------------------
uploaded_files = st.file_uploader(
    "Carica uno o più file CSV di football-data.co.uk",
    type=["csv"],
    accept_multiple_files=True,
    help="Puoi caricare file di campionati diversi (Serie A, Premier, Liga, ecc.)."
)

if not uploaded_files:
    st.info("Carica almeno un CSV per iniziare.")
    st.stop()

dfs = []
for f in uploaded_files:
    df_single = prepara_dataframe(f)
    if df_single is not None:
        dfs.append(df_single)

if not dfs:
    st.error("Nessun file valido è stato caricato.")
    st.stop()

# Uniamo tutti i CSV in un unico DataFrame
df = pd.concat(dfs, ignore_index=True, sort=False)

st.success(f"Caricati {len(dfs)} file. Numero totale di partite: {len(df)}")

# -----------------------------
# UI: selezione squadre (da TUTTI i CSV)
# -----------------------------
# Unione di tutte le squadre home/away + rimozione duplicati + ordinamento
all_teams_series = pd.concat([df["HomeTeam"], df["AwayTeam"]], ignore_index=True)
all_teams = sorted(all_teams_series.dropna().unique().tolist())

col1, col2 = st.columns(2)

with col1:
    team1 = st.selectbox("Squadra 1", options=["— Seleziona —"] + all_teams, index=0)

with col2:
    team2 = st.selectbox("Squadra 2", options=["— Seleziona —"] + all_teams, index=0)

if team1 == "— Seleziona —" or team2 == "— Seleziona —":
    st.warning("Seleziona entrambe le squadre per vedere le statistiche.")
    st.stop()

if team1 == team2:
    st.warning("Seleziona due squadre diverse.")
    st.stop()

# -----------------------------
# Calcolo e visualizzazione risultati
# -----------------------------
st.subheader("Statistiche medie (ultime 5 e 10 partite)")

col_team1, col_team2 = st.columns(2)

for team, col in zip([team1, team2], [col_team1, col_team2]):
    with col:
        st.markdown(f"### {team}")

        # Calcolo per ultime 5 e ultime 10
        matches5, stats5 = calcola_statistiche_squadra(df, team, n_matches=5)
        matches10, stats10 = calcola_statistiche_squadra(df, team, n_matches=10)

        if stats5 is None and stats10 is None:
            st.info("Non ci sono abbastanza dati per calcolare le statistiche per questa squadra.")
        else:
            # Tabella con due colonne: Ultime 5 / Ultime 10
            frames = []
            if stats5 is not None:
                s5 = stats5.copy()
                s5.columns = ["Ultime 5"]
                frames.append(s5)
            if stats10 is not None:
                s10 = stats10.copy()
                s10.columns = ["Ultime 10"]
                frames.append(s10)

            stats_combined = pd.concat(frames, axis=1)
            st.table(stats_combined.style.format("{:.2f}"))

        # Dettaglio partite considerate (max 10)
        detail_matches = matches10 if matches10 is not None and not matches10.empty else matches5

        with st.expander("Dettaglio partite considerate (max 10)"):
            if detail_matches is None or detail_matches.empty:
                st.write("Nessuna partita disponibile.")
            else:
                cols_to_show = ["Date", "Div", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
                cols_to_show = [c for c in cols_to_show if c in detail_matches.columns]
                st.dataframe(detail_matches[cols_to_show])


st.caption(
    "Le colonne sono quelle standard di football-data.co.uk (FTHG, FTAG, HS, HST, ecc.). "
    "Vedi il file notes.txt sul sito per il dettaglio di ogni colonna."
)
