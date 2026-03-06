import React from "react";
import { Card, Grid, Group, Stack, Text, Title, ThemeIcon } from "@mantine/core";
import { Activity, FlaskConical, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

function QuickCard({
  title,
  description,
  to,
  icon,
}: {
  title: string;
  description: string;
  to: string;
  icon: React.ReactNode;
}) {
  return (
    <Card component={Link} to={to} withBorder style={{ textDecoration: "none" }}>
      <Group wrap="nowrap" align="flex-start">
        <ThemeIcon size={38} radius="md" variant="light">
          {icon}
        </ThemeIcon>
        <Stack gap={4}>
          <Text fw={800}>{title}</Text>
          <Text size="sm" c="dimmed">
            {description}
          </Text>
        </Stack>
      </Group>
    </Card>
  );
}

export function OverviewPage() {
  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Dashboard</Title>
        <Text c="dimmed" size="sm" mt={4}>
          目的の画面へ移動してください。
        </Text>
      </div>

      <Grid>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <QuickCard
            title="Signals"
            description="シグナル / 注文 / ポジションを集中監視"
            to="/signals"
            icon={<Sparkles size={20} />}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <QuickCard
            title="Performance"
            description="損益・リターン・最大DDを一覧で確認"
            to="/performance"
            icon={<Activity size={20} />}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <QuickCard
            title="Backtest"
            description="戦略パラメータを変えてバックテストを実行"
            to="/backtest"
            icon={<FlaskConical size={20} />}
          />
        </Grid.Col>
      </Grid>

      <Card withBorder>
        <Text fw={700} mb={4}>
          Note
        </Text>
        <Text size="sm" c="dimmed">
          旧 UI の Tabs 構成を、画面（ルート）ごとに分割しました。必要であればこの Overview に
          KPI やサマリーを集約して「豪華なトップ画面」にできます。
        </Text>
      </Card>
    </Stack>
  );
}
