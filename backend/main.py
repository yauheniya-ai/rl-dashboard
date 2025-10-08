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


def safe_int(x):
    """Convert safely to int, handling strings / floats / NaN."""
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return None


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
        if tbl.startswith("run_") and tbl.endswith("_training_log"):
            run_id = tbl[len("run_") : -len("_training_log")]
            runs[run_id] = {"training_log": tbl}

            best_tbl = f"run_{run_id}_best_episode_results"
            with get_conn() as conn:
                df = pd.read_sql(f"SELECT to_regclass('{best_tbl}') AS exists;", conn)
                if df["exists"].iloc[0] is not None:
                    runs[run_id]["best_episode_results"] = best_tbl

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
            df["steps"] = pd.to_numeric(df["steps"], errors="coerce")
            df["avg_return_last50"] = pd.to_numeric(df["avg_return_last50"], errors="coerce")
            df["elapsed_min"] = pd.to_numeric(df["elapsed_min"], errors="coerce")
            df = df.sort_values("steps")
            results["steps"] = df["steps"].astype("int").tolist()
            results["returns"] = df["avg_return_last50"].apply(safe_float).tolist()
            results["elapsed"] = df["elapsed_min"].apply(safe_float).tolist()
            results["last"] = safe_float(df["avg_return_last50"].iloc[-1])

    # best_episode_results
    if "best_episode_results" in tables:
        with get_conn() as conn:
            best_df = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
        if not best_df.empty:
            best_row = best_df.iloc[-1]
            results["best"] = {
                "episode": safe_int(best_row["episode"]),
                "steps": safe_int(best_row["steps"]),
                "reward": safe_float(best_row["reward"]),
            }

    print(f"[/results] Sending latest run data (types): { {k: type(v) for k,v in results.items()} }")
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
            df["steps"] = pd.to_numeric(df["steps"], errors="coerce")
            df["avg_return_last50"] = pd.to_numeric(df["avg_return_last50"], errors="coerce")
            df["elapsed_min"] = pd.to_numeric(df["elapsed_min"], errors="coerce")
            df = df.sort_values("steps")
            results["steps"] = df["steps"].astype("int").tolist()
            results["returns"] = df["avg_return_last50"].apply(safe_float).tolist()
            results["elapsed"] = df["elapsed_min"].apply(safe_float).tolist()
            results["last"] = safe_float(df["avg_return_last50"].iloc[-1])

    # best_episode_results
    if "best_episode_results" in tables:
        with get_conn() as conn:
            best_df = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
        if not best_df.empty:
            best_row = best_df.iloc[-1]
            results["best"] = {
                "episode": safe_int(best_row["episode"]),
                "steps": safe_int(best_row["steps"]),
                "reward": safe_float(best_row["reward"]),
            }

    print(f"[/results/{run_id}] Sending run data (types): { {k: type(v) for k,v in results.items()} }")
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

        # training_log
        if "training_log" in tables:
            with get_conn() as conn:
                df = pd.read_sql(f'SELECT * FROM "{tables["training_log"]}"', conn)
            if not df.empty:
                df["avg_return_last50"] = pd.to_numeric(df["avg_return_last50"], errors="coerce")
                df["elapsed_min"] = pd.to_numeric(df["elapsed_min"], errors="coerce")
                last_avg_return = safe_float(df["avg_return_last50"].iloc[-1])
                elapsed_min = safe_float(df["elapsed_min"].iloc[-1])

        # best_episode_results
        if "best_episode_results" in tables:
            with get_conn() as conn:
                df_best = pd.read_sql(f'SELECT * FROM "{tables["best_episode_results"]}"', conn)
            if not df_best.empty:
                df_best["reward"] = pd.to_numeric(df_best["reward"], errors="coerce")
                best_reward = safe_float(df_best["reward"].iloc[-1])

        # config_kv table
        config_table = f"run_{run_id}_config_kv"
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT to_regclass(%s) AS exists;", (config_table,))
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

    print(f"[/runs] summary types as sent to frontend for first run: "
          f"{ {k: type(v) for k,v in summary_list[0].items()} if summary_list else {}}")
    return summary_list
