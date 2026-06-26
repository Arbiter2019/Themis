import { Button, Card, Drawer, List, Radio, Space, Table, Tag, Typography, message } from "antd";
import ReactMarkdown from "react-markdown";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { LabelingExperiment, LabelingTask, LabelingTaskDetail } from "../types";

export default function LabelingPage({ experimentId, go }: { experimentId?: number; go: (route: any) => void }) {
  const [experiments, setExperiments] = useState<LabelingExperiment[]>([]);
  const [tasks, setTasks] = useState<LabelingTask[]>([]);
  const [activeExperiment, setActiveExperiment] = useState<number | undefined>(experimentId);
  const [detail, setDetail] = useState<LabelingTaskDetail | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const loadExperiments = async () => setExperiments(await api.labelingExperiments());
  const loadTasks = async (id: number) => setTasks(await api.labelingTasks(id));

  useEffect(() => {
    loadExperiments().catch((error) => message.error(error.message));
  }, []);
  useEffect(() => {
    if (activeExperiment) loadTasks(activeExperiment).catch((error) => message.error(error.message));
  }, [activeExperiment]);

  const openTask = async (taskId: number) => {
    try {
      setDetail(await api.labelingTask(taskId));
      setSelected(null);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const submit = async () => {
    if (!detail || !selected) return;
    try {
      await api.submitLabel(detail.id, selected);
      message.success("标注已提交");
      setDetail(null);
      if (activeExperiment) loadTasks(activeExperiment);
      loadExperiments();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  if (!activeExperiment) {
    return (
      <div>
        <div className="page-header">
          <div>
            <Typography.Title level={3}>标注任务</Typography.Title>
            <Typography.Text type="secondary">选择开启 Preference Labeling 的实验</Typography.Text>
          </div>
        </div>
        <List
          grid={{ gutter: 16, column: 3 }}
          dataSource={experiments}
          renderItem={(item) => (
            <List.Item>
              <Card hoverable onClick={() => setActiveExperiment(item.experiment_id)}>
                <Typography.Title level={5}>{item.name}</Typography.Title>
                <Typography.Text type="secondary">{new Date(item.created_at).toLocaleString()}</Typography.Text>
                <div className="label-progress">
                  {item.labeled}/{item.total}
                </div>
              </Card>
            </List.Item>
          )}
        />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <Space>
          <Button onClick={() => setActiveExperiment(undefined)}>返回</Button>
          <div>
            <Typography.Title level={3}>标注数据列表</Typography.Title>
            <Typography.Text type="secondary">查看并提交偏好版本</Typography.Text>
          </div>
        </Space>
      </div>
      <Table
        rowKey="id"
        dataSource={tasks}
        columns={[
          { title: "任务 UUID", dataIndex: "task_uuid" },
          { title: "标注状态", dataIndex: "status", render: (value) => <Tag color={value === "labeled" ? "green" : "blue"}>{value === "labeled" ? "已标注" : "未标注"}</Tag> },
          { title: "胜出版本", dataIndex: "winner_name", render: (value) => value || "-" },
          { title: "创建时间", dataIndex: "created_at", render: (value) => new Date(value).toLocaleString() },
          { title: "操作", render: (_, row) => <Button onClick={() => openTask(row.id)}>{row.status === "labeled" ? "查看" : "标注"}</Button> }
        ]}
      />
      <Drawer
        title={detail?.task_uuid}
        width={920}
        open={!!detail}
        onClose={() => setDetail(null)}
        extra={
          <Space>
            <Button onClick={() => setDetail(null)}>取消</Button>
            <Button type="primary" disabled={!selected || detail?.status === "labeled"} onClick={submit}>
              提交
            </Button>
          </Space>
        }
      >
        <Radio.Group className="label-radio-group" value={selected} onChange={(event) => setSelected(event.target.value)}>
          {detail?.items.map((item) => (
            <Card
              key={item.id}
              className={`label-card ${selected === item.variant_id ? "label-card-selected" : ""}`}
              onClick={() => detail.status !== "labeled" && setSelected(item.variant_id)}
            >
              <Radio value={item.variant_id}>
                <Typography.Text strong>{item.variant_name}</Typography.Text>
              </Radio>
              {item.variant_description && <Typography.Paragraph type="secondary">{item.variant_description}</Typography.Paragraph>}
              <Typography.Text type="secondary">{item.workflow_id}</Typography.Text>
              <div className="markdown-output">
                <ReactMarkdown>{item.merged_output}</ReactMarkdown>
              </div>
            </Card>
          ))}
        </Radio.Group>
      </Drawer>
    </div>
  );
}

