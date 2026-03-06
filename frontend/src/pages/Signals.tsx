import React, { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  Loader,
  NumberInput,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { RefreshCw, Search, TrendingUp } from "lucide-react";

const API = "/api";

type SignalRow = {
  id: number;
  message_id: string;
  author: string;
  ticker: string;
  side: string;
  confidence: number | null;
  created_at: string;
};

type OrderRow = {
  id: number;
  broker: string;
  ticker: string;
  side: string;
  qty: number;
  price: number | null;
  status: string;
  created_at: string;
};

type PositionRow = {
  id: number;
  ticker: string;
  qty: number;
  avg_price: number;
};

function SideBadge({ side }: { side: string }) {
  const s = side.toLowerCase();
  const color = s.includes("buy") || s.includes("long") ? "green" : s.includes("sell") || s.includes("short") ? "red" : "gray";
  return (
    <Badge color={color} variant="light">
      {side}
    </Badge>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const color = s.includes("filled") ? "green" : s.includes("canceled") ? "gray" : s.includes("rejected") ? "red" : "blue";
  return (
    <Badge color={color} variant="light">
      {status}
    </Badge>
  );
}

export function SignalsPage() {
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [health, setHealth] = useState<"ok" | "ng" | "loading">("loading");
  const [refreshing, setRefreshing] = useState(false);

  const [query, setQuery] = useState("");
  const [minConf, setMinConf] = useState<number | "">("");

  const fetchAll = async (): Promise<void> => {
    setRefreshing(true);
    try {
      const [hRes, sigRes, ordRes, posRes] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/signals`),
        fetch(`${API}/orders`),
        fetch(`${API}/positions`),
      ]);
      setHealth(hRes.ok ? "ok" : "ng");
      if (sigRes.ok) setSignals((await sigRes.json()) as SignalRow[]);
      if (ordRes.ok) setOrders((await ordRes.json()) as OrderRow[]);
      if (posRes.ok) setPositions((await posRes.json()) as PositionRow[]);
    } catch {
      setHealth("ng");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const filteredSignals = useMemo(() => {
    const q = query.trim().toLowerCase();
    return signals.filter((s) => {
      const matchesQ =
        q.length === 0 ||
        s.ticker.toLowerCase().includes(q) ||
        s.author.toLowerCase().includes(q) ||
        s.side.toLowerCase().includes(q);
      const matchesConf = minConf === "" || (s.confidence ?? 0) >= (minConf as number);
      return matchesQ && matchesConf;
    });
  }, [signals, query, minConf]);

  const confAvg = useMemo(() => {
    const vals = filteredSignals.map((s) => s.confidence).filter((v): v is number => typeof v === "number");
    if (vals.length === 0) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }, [filteredSignals]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Signals</Title>
          <Text c="dimmed" size="sm" mt={4}>
            シグナル / 注文 / ポジションをまとめて監視します。
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

      <Grid>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Group gap="xs">
                <TrendingUp size={18} />
                <Text fw={700}>Signal Explorer</Text>
              </Group>
              {refreshing && <Loader size="sm" />}
            </Group>
            <Divider mb="md" />

            <Stack gap="sm">
              <TextInput
                leftSection={<Search size={16} />}
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                placeholder="ticker / author / side を検索"
              />
              <NumberInput
                value={minConf}
                onChange={(value) => {
                  if (value === "" || value == null) {
                    setMinConf("");
                    return;
                  }
                  setMinConf(typeof value === "number" ? value : Number(value));
                }}
                min={0}
                max={1}
                step={0.05}
                allowDecimal
                decimalScale={2}
                placeholder="min confidence (0-1)"
                label="Confidence filter"
              />

              <Group justify="space-between">
                <Text size="sm" c="dimmed">
                  件数: <b>{filteredSignals.length}</b>
                </Text>
                <Text size="sm" c="dimmed">
                  平均信頼度: <b>{confAvg != null ? confAvg.toFixed(2) : "—"}</b>
                </Text>
              </Group>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder>
            <Text fw={700} mb="xs">
              Latest Signals
            </Text>
            <Divider mb="sm" />
            {filteredSignals.length === 0 ? (
              <Text size="sm" c="dimmed">
                シグナルがありません。
              </Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Ticker</Table.Th>
                    <Table.Th>Side</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Conf.</Table.Th>
                    <Table.Th>Author</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {filteredSignals.slice(0, 50).map((s) => (
                    <Table.Tr key={s.id}>
                      <Table.Td>{new Date(s.created_at).toLocaleString()}</Table.Td>
                      <Table.Td>
                        <Text fw={700}>{s.ticker}</Text>
                      </Table.Td>
                      <Table.Td>
                        <SideBadge side={s.side} />
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {s.confidence == null ? "—" : s.confidence.toFixed(2)}
                      </Table.Td>
                      <Table.Td>{s.author}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>
      </Grid>

      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Text fw={700}>Orders</Text>
              <Button variant="light" size="xs" onClick={fetchAll} leftSection={<RefreshCw size={14} />}
                loading={refreshing}
              >
                Refresh
              </Button>
            </Group>
            <Divider mb="sm" />
            {orders.length === 0 ? (
              <Text size="sm" c="dimmed">
                注文がありません。
              </Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Broker</Table.Th>
                    <Table.Th>Ticker</Table.Th>
                    <Table.Th>Side</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Qty</Table.Th>
                    <Table.Th>Status</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {orders.slice(0, 50).map((o) => (
                    <Table.Tr key={o.id}>
                      <Table.Td>{new Date(o.created_at).toLocaleString()}</Table.Td>
                      <Table.Td>{o.broker}</Table.Td>
                      <Table.Td>
                        <Text fw={700}>{o.ticker}</Text>
                      </Table.Td>
                      <Table.Td>
                        <SideBadge side={o.side} />
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {o.qty}
                      </Table.Td>
                      <Table.Td>
                        <StatusBadge status={o.status} />
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
              Positions
            </Text>
            <Divider mb="sm" />
            {positions.length === 0 ? (
              <Text size="sm" c="dimmed">
                ポジションがありません。
              </Text>
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
                      <Table.Td>
                        <Text fw={700}>{p.ticker}</Text>
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {p.qty}
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
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
        <Text fw={700} mb={4}>
          Tips
        </Text>
        <Text size="sm" c="dimmed">
          ここは「表示」専用です（現時点の API 仕様では発注/取消の操作 UI は未実装）。
        </Text>
      </Card>
    </Stack>
  );
}
