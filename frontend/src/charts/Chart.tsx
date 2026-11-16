// A thin React wrapper around ECharts. Only the chart types and components we use are
// imported (tree-shaking keeps the bundle small), and this file is only loaded on
// the Progress tab.
import { LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  SVGRenderer,
]);

type Props = { option: echarts.EChartsCoreOption; height?: number; label: string };

export function Chart({ option, height = 220, label }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption(option);
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(ref.current);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  }, [option]);

  return <div ref={ref} className="chart" style={{ height }} role="img" aria-label={label} />;
}
