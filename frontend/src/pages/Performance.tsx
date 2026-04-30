import React, { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Box,
  Card,
  Divider,
  Grid,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { RefreshCw, TrendingDown, TrendingUp } from "lucide-react";

const API = "/api";

type PnlRow = {
  id: number;
  date: string;
  realized: number;
  unrealized: number;
};

type ExecutionRow = {
  id: number;
  order_id: number;
  ticker: string;
  side: string;
  qty: number;
  price: number;
  executed_at: string;
};

type PositionRow = {
  id: number;
  ticker: string;
  qty: number;
  avg_price: number;
};

function PnlText({ value }: { value: number }) {
  const color = value > 0 ? "teal" : value < 0 ? "red" : undefined;
  return (
    <Text
      size="sm"
      c={color}
      fw={value !== 0 ? 600 : undefined}
      style={{ fontVariantNumeric: "tabular-nums" }}
    >
      {value >= 0 ? "+" : ""}
      {value.toFixed(2)}
    </Text>
  );
}

function SideBadge({ side }: { side: string }) {
  const s = side.toLowerCase();
  const color = s.includes("buy") ? "teal" : s.includes("sell") ? "red" : "gray";
  return <Badge color={color} variant="light" size="sm">{side}</Badge>;
}

function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean | null;
}) {
  const color = positive === true ? "teal" : positive === false ? "red" : "gray";
  const Icon = positive === true ? TrendingUp : positive === false ? TrendingDown : null;
  return (
    <Card withBorder>
      <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
        {label}
      </Text>
      <Group justify="space-between" align="flex-end">
        <Text
          fz={24}
          fw={800}
          c={positive === true ? "teal" : positive === false ? "red" : undefined}
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {value}
        </Text>
        {Icon && (
          <Badge color={color} variant="light" p={6}>
            <Icon size={14} />
          </Badge>
        )}
      </Group>
      {sub && (
        <Text size="xs" c="dimmed" mt={4}>
          {sub}
        </Text>
      )}
    </Card>
  );
}

export function PerformancePage() {
  const [env, setEnv] = useState<"SIMULATE" | "REAL">("SIMULATE");
  const [pnl, setPnl] = useState<PnlRow[]>([]);
  const [executions, setExecutions] = useState<ExecutionRow[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = async (e = env) => {
    setRefreshing(true);
    try {
      const [pnlRes, exRes, posRes] = await Promise.all([
        fetch(`${API}/pnl?broker_env=${e}`),
        fetch(`${API}/executions?broker_env=${e}`),
        fetch(`${API}/positions?broker_env=${e}`),
      ]);
      if (pnlRes.ok) setPnl((await pnlRes.json()) as PnlRow[]);
      if (exRes.ok) setExecutions((await exRes.json()) as ExecutionRow[]);
      if (posRes.ok) setPositions((await posRes.json()) as PositionRow[]);
    } finally {
      setRefreshing(false);
    }
  };

  const handleEnvChange = (v: string) => {
    const next = v as "SIMULATE" | "REAL";
    setEnv(next);
    fetchAll(next);
  };

  useEffect(() => { fetchAll(env); }, []);

  const stats = useMemo(() => {
    const totalRealized = pnl.reduce((s, r) => s + r.realized, 0);
    const totalUnrealized = positions.reduce((s, p) => s + p.qty * p.avg_price, 0);
    const today = new Date().toISOString().slice(0, 10);
    const todayRow = pnl.find((r) => r.date === today);
    return { totalRealized, totalUnrealized, todayPnl: todayRow?.realized ?? null, tradeCount: executions.length };
  }, [pnl, executions, positions]);

  const sortedPnl = useMemo(() => [...pnl].sort((a, b) => b.date.localeCompare(a.date)), [pnl]);
  const sortedExec = useMemo(
    () => [...executions].sort((a, b) => b.executed_at.localeCompare(a.executed_at)),
    [executions]
  );

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Performance</Title>
          <Text c="dimmed" size="sm" mt={2}>損益・約定履歴・ポジション</Text>
        </Box>
        <Group gap="sm">
          <SegmentedControl
            size="xs"
            value={env}
            onChange={handleEnvChange}
            data={[
              { value: "SIMULATE", label: "SIMULATE" },
              { value: "REAL", label: "REAL" },
            ]}
            color={env === "REAL" ? "orange" : "blue"}
          />
          <Tooltip label="再読み込み">
            <ActionIcon variant="subtle" size="lg" onClick={() => fetchAll(env)} loading={refreshing} aria-label="refresh">
              <RefreshCw size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
        <StatCard
          label="Realized PnL"
          value={`${stats.totalRealized >= 0 ? "+" : ""}${stats.totalRealized.toFixed(2)}`}
          sub="全期間累積"
          positive={stats.totalRealized > 0 ? true : stats.totalRealized < 0 ? false : null}
        />
        <StatCard
          label="Today"
          value={stats.todayPnl == null ? "—" : `${stats.todayPnl >= 0 ? "+" : ""}${stats.todayPnl.toFixed(2)}`}
          sub="本日の実現損益"
          positive={stats.todayPnl == null ? null : stats.todayPnl > 0 ? true : stats.todayPnl < 0 ? false : null}
        />
        <StatCard
          label="Trades"
          value={String(stats.tradeCount)}
          sub="総約定件数"
        />
        <StatCard
          label="Positions"
          value={String(positions.length)}
          sub="保有銘柄数"
        />
      </SimpleGrid>

      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder>
            <Text fw={700} mb="sm">
              Daily PnL <Text span c="dimmed" size="sm">({sortedPnl.length})</Text>
            </Text>
            <Divider mb="sm" />
            {sortedPnl.length === 0 ? (
              <Text size="sm" c="dimmed">PnL データがありません。</Text>
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
                  {sortedPnl.slice(0, 90).map((row) => (
                    <Table.Tr key={row.id}>
                      <Table.Td style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{row.date}</Table.Td>
                      <Table.Td style={{ textAlign: "right" }}><PnlText value={row.realized} /></Table.Td>
                      <Table.Td style={{ textAlign: "right" }}><PnlText value={row.unrealized} /></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder h="100%">
            <Text fw={700} mb="sm">
              Positions <Text span c="dimmed" size="sm">({positions.length})</Text>
            </Text>
            <Divider mb="sm" />
            {positions.length === 0 ? (
              <Text size="sm" c="dimmed">保有ポジションがありません。</Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Ticker</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Qty</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Avg</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {positions.map((p) => (
                    <Table.Tr key={p.id}>
                      <Table.Td><Text fw={700} size="sm">{p.ticker}</Text></Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                        <Text size="sm" c={p.qty > 0 ? "teal" : "red"} fw={600}>
                          {p.qty > 0 ? `+${p.qty}` : p.qty}
                        </Text>
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                        {p.avg_price.toFixed(2)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>
      </Grid>

      <Card withBorder>
        <Text fw={700} mb="sm">
          Executions <Text span c="dimmed" size="sm">({sortedExec.length})</Text>
        </Text>
        <Divider mb="sm" />
        {sortedExec.length === 0 ? (
          <Text size="sm" c="dimmed">約定履歴がありません。</Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Time</Table.Th>
                <Table.Th>Ticker</Table.Th>
                <Table.Th>Side</Table.Th>
                <Table.Th style={{ textAlign: "right" }}>Qty</Table.Th>
                <Table.Th style={{ textAlign: "right" }}>Price</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sortedExec.slice(0, 100).map((ex) => (
                <Table.Tr key={ex.id}>
                  <Table.Td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                    {new Date(ex.executed_at).toLocaleString("ja-JP")}
                  </Table.Td>
                  <Table.Td><Text fw={700} size="sm">{ex.ticker}</Text></Table.Td>
                  <Table.Td><SideBadge side={ex.side} /></Table.Td>
                  <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>{ex.qty}</Table.Td>
                  <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                    {ex.price.toFixed(2)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}
