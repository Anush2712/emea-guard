/// <reference types="vite/client" />
declare module "plotly.js-cartesian-dist-min" {
  import Plotly from "plotly.js";
  export default Plotly;
}
interface ImportMetaEnv {
  readonly VITE_DEMO?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_BASE_PATH?: string;
}
