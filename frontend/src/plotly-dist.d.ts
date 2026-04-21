// Minimal type shim for plotly.js-dist-min (no official @types package)
declare module 'plotly.js-dist-min' {
  type Datum = number | string | null;
  interface Data {
    type?: string;
    x?: Datum[];
    y?: Datum[];
    z?: Datum[] | Datum[][];
    mode?: string;
    line?: { color?: string; width?: number };
    marker?: { size?: number; color?: string; symbol?: string };
    opacity?: number;
    name?: string;
    showlegend?: boolean;
    flatshading?: boolean;
    colorscale?: [number, string][];
    showscale?: boolean;
    i?: number[];
    j?: number[];
    k?: number[];
  }
  interface Layout {
    paper_bgcolor?: string;
    plot_bgcolor?: string;
    margin?: { l: number; r: number; t: number; b: number };
    uirevision?: string;
    scene?: {
      bgcolor?: string;
      aspectmode?: string;
      camera?: {
        center?: { x: number; y: number; z: number };
        eye?: { x: number; y: number; z: number };
      };
      xaxis?: { backgroundcolor?: string; gridcolor?: string; showbackground?: boolean; title?: string };
      yaxis?: { backgroundcolor?: string; gridcolor?: string; showbackground?: boolean; title?: string };
      zaxis?: { backgroundcolor?: string; gridcolor?: string; showbackground?: boolean; title?: string };
    };
  }
  interface Config {
    displayModeBar?: boolean;
    scrollZoom?: boolean;
    responsive?: boolean;
  }
  function react(root: HTMLElement, data: Data[], layout?: Partial<Layout>, config?: Partial<Config>): Promise<void>;
  function newPlot(root: HTMLElement, data: Data[], layout?: Partial<Layout>, config?: Partial<Config>): Promise<void>;
  function purge(root: HTMLElement): void;
}
