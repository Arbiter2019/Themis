import { ArrowLeftOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Radio, Space, Switch, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import JsonEditor from "../components/JsonEditor";
import { api } from "../lib/api";
import type { Variant, VariantRole } from "../types";

const defaultInputSchema = '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}';
const defaultOutputSchema = '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}';

const roleLabel: Record<VariantRole, string> = {
  control: "对照组",
  experiment_a: "实验组 A",
  experiment_b: "实验组 B"
};

export default function ExperimentEditPage({ id, go }: { id?: number; go: (route: any) => void }) {
  const [form] = Form.useForm();
  const [hasB, setHasB] = useState(false);
  const [inputSchemaText, setInputSchemaText] = useState(defaultInputSchema);
  const [outputSchemas, setOutputSchemas] = useState<Record<VariantRole, string>>({
    control: defaultOutputSchema,
    experiment_a: defaultOutputSchema,
    experiment_b: defaultOutputSchema
  });
  const preference = Form.useWatch("preference_enabled", form);

  useEffect(() => {
    if (!id) return;
    api
      .getExperiment(id)
      .then((exp) => {
        form.setFieldsValue({
          name: exp.name,
          api_key: exp.api_key || "",
          response_mode: exp.response_mode,
          preference_enabled: exp.preference_enabled,
          variants: Object.fromEntries((exp.variants || []).map((variant) => [variant.role, variant]))
        });
        setInputSchemaText(JSON.stringify(exp.input_schema, null, 2));
        const schemas = { ...outputSchemas };
        exp.variants?.forEach((variant) => {
          schemas[variant.role] = JSON.stringify(variant.output_schema, null, 2);
          if (variant.role === "experiment_b") setHasB(true);
        });
        setOutputSchemas(schemas);
      })
      .catch((error) => message.error(error.message));
  }, [id]);

  const roles = useMemo<VariantRole[]>(() => (hasB ? ["control", "experiment_a", "experiment_b"] : ["control", "experiment_a"]), [hasB]);

  const submit = async (values: any) => {
    try {
      const input_schema = JSON.parse(inputSchemaText);
      const variants: Variant[] = roles.map((role, index) => {
        const variant = values.variants?.[role] || {};
        return {
          role,
          name: variant.name,
          description: variant.description,
          workflow_id: variant.workflow_id,
          output_schema: JSON.parse(outputSchemas[role]),
          merge_template: variant.merge_template,
          display_order: index + 1
        };
      });
      const payload = {
        name: values.name,
        api_key: values.api_key,
        response_mode: values.response_mode || "blocking",
        input_schema,
        preference_enabled: !!values.preference_enabled,
        variants
      };
      const saved = id ? await api.updateExperiment(id, payload) : await api.createExperiment(payload);
      message.success("实验已保存");
      go({ name: "experiment-edit", id: saved.id });
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <Form form={form} layout="vertical" initialValues={{ response_mode: "blocking", preference_enabled: false }} onFinish={submit}>
      <div className="sticky-actions">
        <Button icon={<ArrowLeftOutlined />} onClick={() => go({ name: "experiments" })}>
          取消
        </Button>
        <Button type="primary" icon={<SaveOutlined />} htmlType="submit">
          保存
        </Button>
      </div>
      <div className="page-header">
        <div>
          <Typography.Title level={3}>{id ? "实验详情" : "创建实验"}</Typography.Title>
          <Typography.Text type="secondary">配置对照组、实验组和 JSON Schema</Typography.Text>
        </div>
      </div>
      <Card title="基础信息" className="form-card">
        <Form.Item name="name" label="实验名称" rules={[{ required: true, message: "请输入实验名称" }, { max: 100 }]}>
          <Input maxLength={100} />
        </Form.Item>
        <Form.Item name="api_key" label="workflow API Key" rules={[{ required: true, message: "请输入 API Key" }, { max: 255 }]}>
          <Input maxLength={255} />
        </Form.Item>
        <Form.Item name="response_mode" label="response_mode">
          <Radio.Group
            options={[
              { label: "blocking", value: "blocking" },
              { label: "streaming", value: "streaming" }
            ]}
          />
        </Form.Item>
        <Form.Item name="preference_enabled" label="Preference Labeling" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="输入参数 JSON Schema" required>
          <JsonEditor value={inputSchemaText} onChange={setInputSchemaText} rows={9} />
        </Form.Item>
      </Card>
      <div className="variant-grid">
        {roles.map((role) => (
          <VariantCard
            key={role}
            role={role}
            preference={!!preference}
            schemaText={outputSchemas[role]}
            onSchemaChange={(value) => setOutputSchemas((prev) => ({ ...prev, [role]: value }))}
          />
        ))}
      </div>
      {!hasB && (
        <Button icon={<PlusOutlined />} onClick={() => setHasB(true)}>
          添加实验组 B
        </Button>
      )}
    </Form>
  );
}

function VariantCard({
  role,
  preference,
  schemaText,
  onSchemaChange
}: {
  role: VariantRole;
  preference: boolean;
  schemaText: string;
  onSchemaChange: (value: string) => void;
}) {
  return (
    <Card title={roleLabel[role]} className="form-card">
      <Form.Item name={["variants", role, "name"]} label="版本名称" rules={[{ required: true, message: "请输入版本名称" }, { max: 100 }]}>
        <Input maxLength={100} />
      </Form.Item>
      <Form.Item name={["variants", role, "description"]} label="版本描述" rules={[{ max: 600 }]}>
        <Input.TextArea rows={3} maxLength={600} />
      </Form.Item>
      <Form.Item name={["variants", role, "workflow_id"]} label="workflow_id" rules={[{ required: true, message: "请输入 workflow_id" }, { max: 150 }]}>
        <Input maxLength={150} />
      </Form.Item>
      <Form.Item label="输出参数 JSON Schema" required>
        <JsonEditor value={schemaText} onChange={onSchemaChange} rows={8} />
      </Form.Item>
      {preference && (
        <Form.Item
          name={["variants", role, "merge_template"]}
          label="输出结果合并规则"
          rules={[{ required: true, message: "开启 Preference Labeling 后必填" }, { max: 1000 }]}
        >
          <Input.TextArea rows={4} placeholder="例如：标题：{title}\n结论：{result.summary}" />
        </Form.Item>
      )}
    </Card>
  );
}
