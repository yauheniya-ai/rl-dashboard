import os
import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

NEON_CONN = os.environ.get("NEON_CONN")

app = FastAPI(title="Ping Pong Training Tracker")

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow frontend domains here
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    """Return a new NeonDB connection."""
    return psycopg2.connect(NEON_CONN)


def safe_float(x):
    """Convert NaN / inf to None for JSON."""
    if pd.isna(x) or (isinstance(x, float) and (pd.isna(x) or pd.isnull(x))):
        return None
    return float(x)


def get_all_run_tables():
    """
    Fetch all run tables in NeonDB.
    Returns a dict: run_id -> {"training_log": ..., "best_episode_results": ...}
    """
    runs = {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'run_%';"
            )
            tables = [row[0] for row in cur.fetchall()]

    for tbl in tables:
        # tbl example: run_20251003_232605_training_log
        if tbl.startswith("run_") and tbl.endswith("_training_log"):
            run_id = tbl[len("run_") : -len("_training_log")]  # extract 20251003_232605
            runs[run_id] = {"training_log": tbl}

            # check for best_episode_results
            best_tbl = f"run_{run_id}_best_episode_results"
            with get_conn() as conn:
                df = pd.read_sql(f"SELECT to_regclass('{best_tbl}') AS exists;", conn)
                if df["exists"].iloc[0] is not None:
                    runs[run_id]["best_episode_results"] = best_tbl

    # sort latest first
    runs = dict(sorted(runs.items(), reverse=True))
    return runs


@app.get("/results")
def get_results():
    """Return latest run details for live chart."""
    all_runs = get_all_run_tables()
    if not all_runs:
        return {"steps": [], "returns": [], "elapsed": [], "best": None, "last": None}

    latest_run_id, tables = next(iter(all_runs.items()))
    results = {"steps": [], "returns": [], "elapsed": [], "last": None, "best": None}

    # training_log
    if "training_log" in tables:
        with get_conn() as conn:
            df = pd.read_sql(f'SELECT * FROM "{tables["training_log"]}"', conn)
        if not df.empty:
            results["steps"] = df["steps"].tolist()
            results["returns"] = [safe_float(x) for x in df["avg_return_last50"]]
            results["elapsed"] = [safe_float(x) for x in df["elapsed_min"]]
            results["last"] = safe_float(df["avg_return_last50"].iloc[-1])

    # best_episode_results - get the last (most recent best) row
    if "best_episode_results" in tables:
        with get_conn() as conn:
            best_df = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
        if not best_df.empty:
            best_row = best_df.iloc[-1]
            results["best"] = {
                "episode": int(float(best_row["episode"])),
                "steps": int(float(best_row["steps"])),
                "reward": safe_float(best_row["reward"]),
            }

    return results


@app.get("/results/{run_id}")
def get_results_by_run(run_id: str):
    """Return specific run details for chart."""
    all_runs = get_all_run_tables()
    
    if run_id not in all_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    tables = all_runs[run_id]
    results = {"steps": [], "returns": [], "elapsed": [], "last": None, "best": None}

    # training_log
    if "training_log" in tables:
        with get_conn() as conn:
            df = pd.read_sql(f'SELECT * FROM "{tables["training_log"]}"', conn)
        if not df.empty:
            results["steps"] = df["steps"].tolist()
            results["returns"] = [safe_float(x) for x in df["avg_return_last50"]]
            results["elapsed"] = [safe_float(x) for x in df["elapsed_min"]]
            results["last"] = safe_float(df["avg_return_last50"].iloc[-1])

    # best_episode_results - get the last (most recent best) row
    if "best_episode_results" in tables:
        with get_conn() as conn:
            best_df = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
        if not best_df.empty:
            best_row = best_df.iloc[-1]
            results["best"] = {
                "episode": int(float(best_row["episode"])),
                "steps": int(float(best_row["steps"])),
                "reward": safe_float(best_row["reward"]),
            }

    return results


@app.get("/runs")
def get_runs_summary():
    """Return summary of all runs, latest first, including model name."""
    all_runs = get_all_run_tables()
    summary_list = []

    for run_id, tables in all_runs.items():
        last_avg_return = None
        best_reward = None
        elapsed_min = None
        model_name = None

        # fetch last avg_return and elapsed_min
        if "training_log" in tables:
            with get_conn() as conn:
                df = pd.read_sql(f'SELECT * FROM "{tables["training_log"]}"', conn)
            if not df.empty:
                last_avg_return = safe_float(df["avg_return_last50"].iloc[-1])
                elapsed_min = safe_float(df["elapsed_min"].iloc[-1])

        # fetch best reward from last row of best_episode_results
        if "best_episode_results" in tables:
            with get_conn() as conn:
                df_best = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
            if not df_best.empty:
                best_reward = safe_float(df_best["reward"].iloc[-1])

        # fetch model from config_kv table if it exists
        config_table = f"run_{run_id}_config_kv"
        with get_conn() as conn:
            # check table existence
            cur = conn.cursor()
            cur.execute(
                "SELECT to_regclass(%s) AS exists;",
                (config_table,)
            )
            exists = cur.fetchone()[0]
            if exists:
                df_config = pd.read_sql(
                    f'SELECT value FROM "{config_table}" WHERE key = %s',
                    conn,
                    params=("model",)
                )
                if not df_config.empty:
                    model_name = df_config["value"].iloc[0]

        summary_list.append({
            "run": run_id,
            "model": model_name,
            "last_avg_return": last_avg_return,
            "best_reward": best_reward,
            "elapsed_min": elapsed_min
        })

    return summary_list