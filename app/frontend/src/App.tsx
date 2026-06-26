import { BarChartOutlined, LogoutOutlined, TagsOutlined } from "@ant-design/icons";
import { Button, Layout, Menu, Space, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { getSession, saveSession } from "./lib/api";
import ExperimentEditPage from "./pages/ExperimentEditPage";
import ExperimentListPage from "./pages/ExperimentListPage";
import LabelingPage from "./pages/LabelingPage";
import LoginPage from "./pages/LoginPage";
import ReportPage from "./pages/ReportPage";

type Route =
  | { name: "experiments" }
  | { name: "experiment-new" }
  | { name: "experiment-edit"; id: number }
  | { name: "report"; id: number }
  | { name: "labeling"; experimentId?: number };

export default function App() {
  const [session, setSession] = useState(getSession());
  const initialRoute: Route = session?.role === "labeler" ? { name: "labeling" } : { name: "experiments" };
  const [route, setRoute] = useState<Route>(initialRoute);

  useEffect(() => {
    if (!session) return;
    setRoute(session.role === "labeler" ? { name: "labeling" } : { name: "experiments" });
  }, [session?.token]);

  const menuKey = useMemo(() => (route.name === "labeling" ? "labeling" : "experiments"), [route]);

  if (!session) {
    return <LoginPage onLogin={(next) => setSession(next)} />;
  }

  const logout = () => {
    saveSession(null);
    setSession(null);
    message.success("已退出登录");
  };

  return (
    <Layout className="app-shell">
      <Layout.Sider width={224} theme="light" className="sidebar">
        <div className="brand">
          <img src="/logo.png" alt="Themis" />
          <div>
            <Typography.Text strong>Themis</Typography.Text>
            <Typography.Text type="secondary" className="brand-subtitle">
              AB Test Tools
            </Typography.Text>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[menuKey]}
          items={[
            ...(session.role === "admin"
              ? [{ key: "experiments", icon: <BarChartOutlined />, label: "实验管理", onClick: () => setRoute({ name: "experiments" }) }]
              : []),
            { key: "labeling", icon: <TagsOutlined />, label: "标注任务", onClick: () => setRoute({ name: "labeling" }) }
          ]}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header className="topbar">
          <Space>
            <Typography.Text>{session.username}</Typography.Text>
            <Typography.Text type="secondary">{session.role === "admin" ? "管理员" : "标注人员"}</Typography.Text>
            <Button icon={<LogoutOutlined />} onClick={logout}>
              退出
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content className="content">
          {route.name === "experiments" && <ExperimentListPage go={setRoute} />}
          {route.name === "experiment-new" && <ExperimentEditPage go={setRoute} />}
          {route.name === "experiment-edit" && <ExperimentEditPage id={route.id} go={setRoute} />}
          {route.name === "report" && <ReportPage id={route.id} go={setRoute} />}
          {route.name === "labeling" && <LabelingPage experimentId={route.experimentId} go={setRoute} />}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
