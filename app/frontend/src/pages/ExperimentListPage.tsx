import { PlusOutlined, UploadOutlined } from "@ant-design/icons";
import { Button, Modal, Progress, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Experiment } from "../types";

const statusText = {
  not_started: "未开始",
  running: "进行中",
  completed: "完成",
  failed: "失败"
};

export default function ExperimentListPage({ go }: { go: (route: any) => void }) {
  const [rows, setRows] = useState<Experiment[]>([]);
  const [importing, setImporting] = useState<Experiment | null>(null);
  const [sampleText, setSampleText] = useState("");

  const load = async () => setRows(await api.listExperiments());
  useEffect(() => {
    load().catch((error) => message.error(error.message));
  }, []);

  const submitImport = async () => {
    if (!importing) return;
    try {
      const parsed = JSON.parse(sampleText);
      if (!Array.isArray(parsed)) throw new Error("导入内容必须是 JSON List");
      const result = await api.importSamples(importing.id, parsed);
      if (result.errors.length) {
        message.error("样本校验失败，请检查 JSON Schema");
      } else {
        message.success(`已导入 ${result.imported} 条样本，后台开始执行`);
        setImporting(null);
        setSampleText("");
        load();
      }
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <Typography.Title level={3}>实验管理</Typography.Title>
          <Typography.Text type="secondary">创建、执行并查看 Dify workflow 版本回测结果</Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => go({ name: "experiment-new" })}>
          创建实验
        </Button>
      </div>
      <Table
        rowKey="id"
        dataSource={rows}
        columns={[
          { title: "实验名称", dataIndex: "name" },
          { title: "创建时间", dataIndex: "created_at", render: (value) => new Date(value).toLocaleString() },
          { title: "状态", dataIndex: "status", render: (value) => <Tag>{statusText[value as keyof typeof statusText]}</Tag> },
          {
            title: "执行进度",
            render: (_, row) => <Progress percent={row.total_samples ? Math.round((row.executed_samples / row.total_samples) * 100) : 0} size="small" />
          },
          { title: "Preference", dataIndex: "preference_enabled", render: (value) => (value ? "开启" : "关闭") },
          {
            title: "操作",
            render: (_, row) => (
              <Space>
                {row.status === "not_started" && <Button onClick={() => go({ name: "experiment-edit", id: row.id })}>详情</Button>}
                {row.status === "not_started" && (
                  <Button icon={<UploadOutlined />} onClick={() => setImporting(row)}>
                    导入数据
                  </Button>
                )}
                {row.status !== "not_started" && <Button onClick={() => go({ name: "report", id: row.id })}>查看实验报告</Button>}
              </Space>
            )
          }
        ]}
      />
      <Modal title="导入 JSON List" open={!!importing} onCancel={() => setImporting(null)} onOk={submitImport} width={760}>
        <Typography.Paragraph type="secondary">导入后系统会按输入 JSON Schema 校验，通过后后台逐条调用 Dify。</Typography.Paragraph>
        <textarea className="sample-import" value={sampleText} onChange={(event) => setSampleText(event.target.value)} />
      </Modal>
    </div>
  );
}

