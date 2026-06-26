import { ArrowLeftOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, Row, Space, Statistic, Typography, message } from "antd";
import * as echarts from "echarts";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { MetricPoint, Report } from "../types";

function Chart({ option }: { option: echarts.EChartsOption }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption(option);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [option]);
  return <div className="chart" ref={ref} />;
}

export default function ReportPage({ id, go }: { id: number; go: (route: any) => void }) {
  const [report, setReport] = useState<Report | null>(null);
  const load = async () => setReport(await api.report(id));
  useEffect(() => {
    load().catch((error) => message.error(error.message));
  }, [id]);

  if (!report) return null;
  const metrics = report.metrics;

  const rateOption: echarts.EChartsOption = {
    tooltip: {},
    legend: {},
    xAxis: { type: "category", data: metrics.map((m) => m.name) },
    yAxis: { type: "value", max: 100 },
    series: [
      { name: "成功率", type: "bar", label: { show: true, color: "#FFFFFF", formatter: "{c}%" }, data: metrics.map((m) => ({ value: m.success_rate, itemStyle: { color: m.color } })) },
      { name: "结构稳定性", type: "bar", label: { show: true, color: "#FFFFFF", formatter: "{c}%" }, data: metrics.map((m) => ({ value: m.stability_rate, itemStyle: { color: m.color } })) }
    ]
  };
  const latencyOption: echarts.EChartsOption = {
    tooltip: {},
    xAxis: { type: "category", data: metrics.map((m) => m.name) },
    yAxis: { type: "value", name: "ms" },
    series: [
      {
        name: "响应时长",
        type: "candlestick",
        data: metrics.map((m) => [m.latency_q1_ms || 0, m.latency_q3_ms || 0, m.latency_median_ms || 0, m.latency_avg_ms || 0]),
        itemStyle: { color: "#0A84FF", borderColor: "#0A84FF" }
      }
    ]
  };
  const labeling = report.labeling;
  const progressOption: echarts.EChartsOption | null = labeling
    ? {
        tooltip: {},
        series: [
          {
            type: "pie",
            radius: ["62%", "78%"],
            label: { show: true, position: "center", formatter: `${labeling.labeled}/${labeling.total}` },
            data: [
              { value: labeling.labeled, name: "已标注", itemStyle: { color: "#0A84FF" } },
              { value: Math.max(labeling.total - labeling.labeled, 0), name: "未标注", itemStyle: { color: "#D9DEE8" } }
            ]
          }
        ]
      }
    : null;
  const winnerOption: echarts.EChartsOption | null = labeling
    ? {
        tooltip: {},
        xAxis: { type: "category", data: labeling.winners.map((w) => w.name) },
        yAxis: { type: "value" },
        series: [{ type: "bar", label: { show: true, color: "#FFFFFF" }, data: labeling.winners.map((w) => ({ value: w.count, itemStyle: { color: w.color } })) }]
      }
    : null;

  return (
    <div>
      <div className="page-header">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => go({ name: "experiments" })}>
            返回
          </Button>
          <div>
            <Typography.Title level={3}>{report.experiment.name}</Typography.Title>
            <Typography.Text type="secondary">实验报告</Typography.Text>
          </div>
        </Space>
        {report.experiment.preference_enabled && report.experiment.status === "running" && labeling && labeling.total === labeling.labeled && (
          <Button icon={<CheckCircleOutlined />} type="primary" onClick={() => api.closeExperiment(id).then(load).catch((error) => message.error(error.message))}>
            手动关闭实验
          </Button>
        )}
      </div>
      {metrics.length === 0 ? (
        <Empty description="暂无数据" />
      ) : (
        <>
          <Row gutter={16}>
            {metrics.map((metric: MetricPoint) => (
              <Col span={8} key={metric.variant_id}>
                <Card>
                  <Statistic title={metric.name} value={metric.success_rate} suffix="%" precision={2} />
                  <Typography.Text type="secondary">结构稳定性 {metric.stability_rate.toFixed(2)}%</Typography.Text>
                </Card>
              </Col>
            ))}
          </Row>
          <Card title="成功率与结构稳定性" className="report-card">
            <Chart option={rateOption} />
          </Card>
          <Card title="响应时长" className="report-card">
            <Chart option={latencyOption} />
          </Card>
          {labeling && progressOption && winnerOption && (
            <Row gutter={16}>
              <Col span={10}>
                <Card title="标注进度" className="report-card">
                  <Chart option={progressOption} />
                </Card>
              </Col>
              <Col span={14}>
                <Card title="版本采纳数量" className="report-card">
                  <Chart option={winnerOption} />
                </Card>
              </Col>
            </Row>
          )}
        </>
      )}
    </div>
  );
}
