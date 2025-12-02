import streamlit as st
import pandas as pd

st.set_page_config(page_title="Statistiche squadre (football-data.co.uk)", layout="wide")
st.title("Statistiche medie ultime 5 e 10 partite per squadra")
st.caption("Dati in formato football-data.co.uk – vedi notes.txt per il significato delle colonne.")


# -----------------------------
# Funzioni di utilità
# -----------------------------
def prepara_dataframe(uploaded_file: "UploadedFile") -> pd.DataFrame | None:
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Errore nella lettura del CSV: {e}")
        return None

    # Proviamo a parsare la data se presente
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    # Controllo colonne essenziali
    required_cols = {"HomeTeam", "AwayTeam"}
    if not required_cols.issubset(df.columns):
        st.error(
            "Il file caricato non contiene le colonne minime richieste "
            "'HomeTeam' e 'AwayTeam'.\n\n"
            "Verifica che il file sia nel formato standard football-data.co.uk."
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
# UI: Upload del file
# -----------------------------
uploaded_file = st.file_uploader(
    "Carica un file CSV di football-data.co.uk",
    type=["csv"],
    help="Ad esempio un file della Serie A / Premier League scaricato da football-data.co.uk",
)

if uploaded_file is None:
    st.info("Carica un CSV per iniziare.")
    st.stop()

df = prepara_dataframe(uploaded_file)
if df is None:
    st.stop()

# -----------------------------
# UI: selezione squadre
# -----------------------------
all_teams = pd.unique(pd.concat([df["HomeTeam"], df["AwayTeam"]])).tolist()
all_teams = sorted([t for t in all_teams if pd.notna(t)])

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
            # Costruiamo una tabella con due colonne: Ultime 5 / Ultime 10
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

        # Mostriamo il dettaglio delle partite considerate (fino a 10)
        # Se matches10 è vuoto, usiamo matches5
        detail_matches = matches10 if matches10 is not None and not matches10.empty else matches5

        with st.expander("Dettaglio partite considerate (max 10)"):
            if detail_matches is None or detail_matches.empty:
                st.write("Nessuna partita disponibile.")
            else:
                cols_to_show = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
                cols_to_show = [c for c in cols_to_show if c in detail_matches.columns]
                st.dataframe(detail_matches[cols_to_show])


st.caption(
    "Le colonne sono quelle standard di football-data.co.uk (FTHG, FTAG, HS, HST, ecc.). "
    "Vedi il file notes.txt sul sito per il dettaglio di ogni colonna."
)
