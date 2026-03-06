import React, { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Box,
  Card,
  Divider,
  Grid,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { Activity, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";

const API = "/api";

type DailyPnl = {
  id: number;
  date: string;
  realized: number;
  unrealized: number;
};

type PerformanceSummary = {
  start_date: string | null;
  end_date: string | null;
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number | null;
  max_drawdown_pct: number;
  equity_curve: { date: string; equity: number }[];
};

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "good" | "bad" | "neutral";
}) {
  const color = tone === "good" ? "green" : tone === "bad" ? "red" : "gray";
  return (
    <Card withBorder>
      <Text size="xs" tt="uppercase" fw={700} c="dimmed">
        {label}
      </Text>
      <Group justify="space-between" mt={6}>
        <Text fz={26} fw={800} style={{ fontVariantNumeric: "tabular-nums" }}>
          {value}
        </Text>
        <Badge color={color} variant="light">
          {tone === "good" ? <TrendingUp size={14} /> : tone === "bad" ? <TrendingDown size={14} /> : <Activity size={14} />}
        </Badge>
      </Group>
      {hint && (
        <Text size="xs" c="dimmed" mt={6}>
          {hint}
        </Text>
      )}
    </Card>
  );
}

export function PerformancePage() {
  const [health, setHealth] = useState<"ok" | "ng" | "loading">("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [pnl, setPnl] = useState<DailyPnl[]>([]);
  const [perf, setPerf] = useState<PerformanceSummary | null>(null);

  const fetchAll = async (): Promise<void> => {
    setRefreshing(true);
    try {
      const [hRes, pnlRes, perfRes] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/metrics/pnl/daily`),
        fetch(`${API}/metrics/performance`),
      ]);
      setHealth(hRes.ok ? "ok" : "ng");
      if (pnlRes.ok) setPnl((await pnlRes.json()) as DailyPnl[]);
      if (perfRes.ok) setPerf((await perfRes.json()) as PerformanceSummary);
    } catch {
      setHealth("ng");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const stats = useMemo(() => {
    if (!perf) return null;
    const totalTone = perf.total_return_pct >= 0 ? "good" : "bad";
    const ddTone = perf.max_drawdown_pct < 0 ? "bad" : "neutral";
    return {
      totalReturn: {
        value: `${perf.total_return_pct >= 0 ? "+" : ""}${perf.total_return_pct.toFixed(2)}%`,
        tone: totalTone as "good" | "bad",
      },
      cagr: {
        value: perf.cagr_pct == null ? "—" : `${perf.cagr_pct >= 0 ? "+" : ""}${perf.cagr_pct.toFixed(2)}%`,
        tone: (perf.cagr_pct ?? 0) >= 0 ? ("good" as const) : ("bad" as const),
      },
      mdd: {
        value: `${perf.max_drawdown_pct.toFixed(2)}%`,
        tone: ddTone as "good" | "bad" | "neutral",
      },
      equity: {
        value: `${perf.final_equity.toFixed(2)}`,
        tone: perf.final_equity >= perf.initial_equity ? ("good" as const) : ("bad" as const),
      },
    };
  }, [perf]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Performance</Title>
          <Text c="dimmed" size="sm" mt={4}>
            実運用の損益・リターン・ドローダウンを確認します。
          </Text>
        </Box>
        <Group gap="sm">
          <Badge color={health === "ok" ? "green" : health === "ng" ? "red" : "gray"} variant="light" size="lg">
            API: {health.toUpperCase()}
          </Badge>
          <Tooltip label="再読み込み">
            <ActionIcon variant="subtle" size="lg" onClick={fetchAll} loading={refreshing} aria-label="refresh">
              <RefreshCw size={20} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <StatCard label="Total Return" value={stats?.totalReturn.value ?? "—"} tone={stats?.totalReturn.tone} />
        <StatCard label="CAGR" value={stats?.cagr.value ?? "—"} tone={stats?.cagr.tone} />
        <StatCard label="Max Drawdown" value={stats?.mdd.value ?? "—"} tone={stats?.mdd.tone} />
        <StatCard label="Final Equity" value={stats?.equity.value ?? "—"} tone={stats?.equity.tone} />
      </SimpleGrid>

      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder>
            <Text fw={700} mb="xs">
              Daily PnL
            </Text>
            <Divider mb="sm" />
            {pnl.length === 0 ? (
              <Text size="sm" c="dimmed">
                PnL データがありません。
              </Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Date</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Realized</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Unrealized</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {pnl.slice(0, 120).map((row) => (
                    <Table.Tr key={row.id}>
                      <Table.Td>{row.date}</Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {row.realized >= 0 ? "+" : ""}
                        {row.realized.toFixed(2)}
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {row.unrealized >= 0 ? "+" : ""}
                        {row.unrealized.toFixed(2)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder>
            <Text fw={700} mb="xs">
              Summary
            </Text>
            <Divider mb="sm" />
            {perf && (perf.start_date ?? perf.end_date) ? (
              <Stack gap={6}>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">
                    Period
                  </Text>
                  <Text size="sm" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                    {perf.start_date} ~ {perf.end_date}
                  </Text>
                </Group>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">
                    Initial
                  </Text>
                  <Text size="sm" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                    {perf.initial_equity.toFixed(2)}
                  </Text>
                </Group>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">
                    Final
                  </Text>
                  <Text size="sm" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                    {perf.final_equity.toFixed(2)}
                  </Text>
                </Group>
                <Divider my="xs" />
                <Text size="xs" c="dimmed">
                  Equity curve は API から取得可能ですが、現状は描画 UI を未実装です。
                </Text>
              </Stack>
            ) : (
              <Text size="sm" c="dimmed">
                パフォーマンスデータがありません。
              </Text>
            )}
          </Card>
        </Grid.Col>
      </Grid>

      <Card withBorder>
        <Text fw={700} mb={4}>
          Next
        </Text>
        <Text size="sm" c="dimmed">
          グラフ（equity curve / drawdown）や、期間フィルタを追加するとさらに見栄えが良くなります。
        </Text>
      </Card>
    </Stack>
  );
}
