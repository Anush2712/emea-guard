import Plotly from "plotly.js-cartesian-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const Plot = createPlotlyComponent(Plotly);

// Validated reference palette (categorical slots + status colours).
export const SERIES = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"];
export const MUTED = "#c9cfd8";
export const SEV_COLOR: Record<string, string> = { Critical: "#dc3c3d", High: "#f18a59", Medium: "#fbb315", Low: "#0aac23" };

const baseLayout: Partial<Plotly.Layout> = {
  font: { family: "Inter, -apple-system, Segoe UI, Roboto, sans-serif", size: 12, color: "#16202e" },
  paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
  margin: { l: 44, r: 12, t: 8, b: 36 },
  xaxis: { gridcolor: "#e7e7e7", linecolor: "#e7e7e7", tickfont: { color: "#5b6576" }, zeroline: false },
  yaxis: { gridcolor: "#e7e7e7", linecolor: "#e7e7e7", tickfont: { color: "#5b6576" }, zeroline: false },
  hoverlabel: { bgcolor: "#0b1b33", bordercolor: "#0b1b33", font: { color: "#fff", size: 12 } },
  showlegend: false, bargap: 0.35,
};

export function Chart({ data, layout = {}, height = 280 }: { data: Plotly.Data[]; layout?: Partial<Plotly.Layout>; height?: number }) {
  return (
    <Plot
      data={data}
      layout={{ ...baseLayout, ...layout, xaxis: { ...baseLayout.xaxis, ...(layout.xaxis ?? {}) }, yaxis: { ...baseLayout.yaxis, ...(layout.yaxis ?? {}) }, height, autosize: true }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
