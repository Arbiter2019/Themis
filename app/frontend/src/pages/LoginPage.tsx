import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Form, Input, Typography, message } from "antd";
import { api, saveSession, type Session } from "../lib/api";

export default function LoginPage({ onLogin }: { onLogin: (session: Session) => void }) {
  const submit = async (values: { username: string; password: string }) => {
    try {
      const session = await api.login(values.username, values.password);
      saveSession(session);
      onLogin(session);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <div className="login-page">
      <div className="login-panel">
        <img src="/logo.png" alt="Themis" className="login-logo" />
        <Typography.Title level={2}>Themis</Typography.Title>
        <Typography.Text type="secondary">Dify Workflow AB Test Tools</Typography.Text>
        <Form layout="vertical" className="login-form" onFinish={submit}>
          <Form.Item name="username" rules={[{ required: true, message: "请输入账号" }]}>
            <Input prefix={<UserOutlined />} placeholder="账号" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block>
            登录
          </Button>
        </Form>
      </div>
    </div>
  );
}

