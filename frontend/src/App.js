import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import "./App.css";
import TableTennisScene from "./TableTennisScene";

function App() {
  const [liveData, setLiveData] = useState({
    steps: [],
    returns: [],
    best: null,
    last: null,
    elapsed: [],
  });

  const [runs, setRuns] = useState([]);
  const [activePlots, setActivePlots] = useState([]); // multi-selection for Plot
  const [runDataCache, setRunDataCache] = useState({}); // Cache for individual run data
  const [showAllRuns, setShowAllRuns] = useState(false); // Toggle for showing all runs

  const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

  // Fetch live chart data for the latest run
  const fetchLiveResults = async () => {
    try {
      const res = await fetch(`${API_URL}/results`);
      const json = await res.json();
      // Convert string arrays to numbers for plotting
      setLiveData({
        ...json,
        steps: json.steps?.map(s => parseFloat(s)) || [],
        returns: json.returns?.map(r => parseFloat(r)) || [],
      });
    } catch (e) {
      console.error("Failed to fetch live results:", e);
    }
  };

  // Fetch summary of all runs
  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API_URL}/runs`);
      const json = await res.json();
      setRuns(json);
    } catch (e) {
      console.error("Failed to fetch runs summary:", e);
    }
  };

  // Fetch data for a specific run
  const fetchRunData = async (runId) => {
    try {
      const res = await fetch(`${API_URL}/results/${runId}`);
      const json = await res.json();
      setRunDataCache(prev => ({
        ...prev,
        [runId]: {
          ...json,
          steps: json.steps?.map(s => parseFloat(s)) || [],
          returns: json.returns?.map(r => parseFloat(r)) || [],
        }
      }));
    } catch (e) {
      console.error(`Failed to fetch data for run ${runId}:`, e);
    }
  };

  useEffect(() => {
    fetchLiveResults();
    fetchRuns();
    const interval = setInterval(() => {
      fetchLiveResults();
      fetchRuns();
    }, 5000); // refresh every 5s
    return () => clearInterval(interval);
  }, []); // Empty dependency array - only run on mount

  // Set default selection when runs first load
  useEffect(() => {
    if (runs.length > 0 && activePlots.length === 0) {
      setActivePlots([runs[0].run]);
    }
  }, [runs.length]); // Only trigger when runs.length changes

  // Fetch data for newly selected runs
  useEffect(() => {
    activePlots.forEach(runId => {
      if (!runDataCache[runId]) {
        fetchRunData(runId);
      }
    });
  }, [activePlots]); // Fetch when selection changes

  // Refresh data for active plots
  useEffect(() => {
    if (activePlots.length > 0) {
      const interval = setInterval(() => {
        activePlots.forEach(runId => {
          fetchRunData(runId);
        });
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [activePlots]);

  return (
    <div className="App">
      <h1 style={{ paddingBottom: "2rem" }}>Ping Pong Training Dashboard</h1>

      {/* Plot */}
      <div style={{ width: "800px", margin: "0 auto", backgroundColor: "#111", paddingTop: "1rem", boxSizing: "border-box" }}> 
        <Plot
          data={activePlots.map((runId, idx) => {
            const run = runs.find(r => r.run === runId);
            if (!run) return null;

            // Get cached data for this run
            const runData = runDataCache[runId];
            if (!runData || !runData.steps || runData.steps.length === 0) {
              return null;
            }

            // Use different colors for different runs
            const colors = ["#8b76e9", "#76a5e9", "#e97676", "#76e9b3", "#e9d176", "#e976d1"];
            const color = colors[idx % colors.length];

            return {
              x: runData.steps,
              y: runData.returns,
              type: "scatter",
              //mode: "lines+markers",
              mode: "lines",
              //marker: { color: color, size: 2 },
              line: { color: color, shape: "linear" },
              name: run.run,
            };
          }).filter(Boolean)}
          layout={{
            width: 768,
            //height: 500,
            title: {
              text: "Training Curve",
              font: { color: "#fff" },
            },
            xaxis: {
              title: { text: "Steps", font: { color: "#fff" } },
              tickfont: { color: "#fff" },
              gridcolor: "#444",
              zerolinecolor: "#444",
            },
            yaxis: {
              title: { text: "∅ Reward (Last 50 Episodes)", font: { color: "#fff" } },
              tickfont: { color: "#fff" },
              gridcolor: "#444",
              zerolinecolor: "#444",
            },
            paper_bgcolor: "#111",
            plot_bgcolor: "#111",
            font: { color: "#fff" },
            showlegend: true,
            margin: { l: 60, r: 20, t: 60, b: 60 },
          }}
          config={{ responsive: false }}
        />
      </div>

      {/* Summary Table */}
      <div style={{ paddingTop: "1rem", paddingBottom: "1rem", width: "800px", margin: "0 auto"  }}>
        <table style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>Run</th>
              <th>Model</th>
              <th>Best Reward</th>
              <th>Last ∅ Reward</th>
              <th>Time (HH:MM)</th>
              <th>Plot</th>
            </tr>
          </thead>
          <tbody>
            {(showAllRuns ? runs : runs.slice(0, 1)).map((run, idx) => (
              <tr key={idx}>
                <td>{run.run ?? "-"}</td>
                <td>{run.model ?? "-"}</td>
                <td>{run.best_reward ?? "-"}</td>
                <td>{run.last_avg_return ?? "-"}</td>
                <td>
                  {run.elapsed_min
                    ? (() => {
                        const totalMinutes = Number(run.elapsed_min);
                        const hours = Math.floor(totalMinutes / 60);
                        const minutes = Math.floor(totalMinutes % 60);
                        // Pad with zeros if needed
                        const pad = num => num.toString().padStart(2, '0');
                        return `${pad(hours)}:${pad(minutes)}`;
                      })()
                    : "-"}
                </td>
                {/* Plot checkbox */}
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={activePlots.includes(run.run)}
                    onChange={() => {
                      setActivePlots(prev => {
                        if (prev.includes(run.run)) {
                          return prev.filter(id => id !== run.run);
                        } else {
                          return [...prev, run.run];
                        }
                      });
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {/* Toggle link for previous runs */}
        {runs.length > 1 && (
          <div style={{ marginTop: "0.5rem", textAlign: "left" }}>
            <span
              onClick={() => setShowAllRuns(!showAllRuns)}
              style={{
                color: "#76a5e9",
                cursor: "pointer",
                fontSize: "0.95rem",
                textDecoration: "underline",
              }}
              onMouseEnter={(e) => e.target.style.color = "#5a8dd1"}
              onMouseLeave={(e) => e.target.style.color = "#76a5e9"}
            >
              {showAllRuns ? `Hide Previous Runs (${runs.length - 1})` : `Show Previous Runs (${runs.length - 1})`}
            </span>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "2rem", marginTop: "3rem" , marginRight: "5rem" }}>
        {/* Left: Table Tennis Model */}
        <div style={{ flex: "0 0 40%", height: "600px" }}>
          <h2 style={{ color: "#fff", textAlign: "center", marginBottom: "1rem" }}>
            Ping Pong Game
          </h2>
          <TableTennisScene />
        </div>

        {/* Right: Rules */}
        <div style={{ flex: "1", color: "#000", fontSize: "1rem", lineHeight: "1.6",  textAlign: "left" }}>
          <div style={{ display: "flex", alignItems: "center", marginBottom: "1rem" }}>
            <img
              src="/images/olympics_logo_color.svg"
              alt="Olympics Logo"
              style={{ height: "50px", marginRight: "1rem" }}
            />
            <h2>Olympic Table Tennis Rules</h2>
          </div>

          <p>
            Table tennis has been an Olympic sport since the 1988 Seoul Games. 
          </p>

          <h3>Equipment</h3>
          <ul>
            <li><strong>Table:</strong> 2.74x1.53 m with a net at 15.25 cm height.</li>
            <li><strong>Racquet:</strong> Wooden paddle (~17x15 cm) with black and red rubber surfaces.</li>
            <li><strong>Ball:</strong> Spherical, 40 mm diameter, 2.7 g weight, orange or white.</li>
          </ul>

          <h3>Gameplay & Service</h3>
          <ul>
            <li>Matches start with a coin toss; winner chooses to serve, receive, or side.</li>
            <li>The server tosses the ball from an open palm, striking it to bounce on their side first, then over the net.</li>
            <li>In singles, service can go to any part of the opponent's side; in doubles, it must be diagonal.</li>
          </ul>

          <h3>Scoring</h3>
          <ul>
            <li>Games are played to 11 points; a 2-point lead is required if tied at 10-10.</li>
            <li>Points are awarded when the opponent fails to return the ball correctly, hits it off the table, or contacts it improperly.</li>
            <li>Matches are typically best-of-seven for singles, best-of-five for doubles.</li>
          </ul>

          <p style={{ fontSize: "0.85rem", marginTop: "1rem" }}>
            Source: <a href="https://olympics.com" target="_blank" style={{ color: "#8b76e9" }}>olympics.com</a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;