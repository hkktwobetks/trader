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
  NumberInput,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { RefreshCw, Search } from "lucide-react";

const API = "/api";

type SignalRow = {
  id: number;
  author: string;
  ticker: string;
  side: string;
  confidence: number | null;
  created_at: string;
};

type OrderRow = {
  id: number;
  broker: string;
  broker_env: string;
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
  acc_type: string;
};

function SideBadge({ side }: { side: string }) {
  const s = side.toLowerCase();
  const color = s.includes("buy") ? "teal" : s.includes("sell") ? "red" : "gray";
  return <Badge color={color} variant="light" size="sm">{side}</Badge>;
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const color = s === "filled" ? "teal" : s === "canceled" ? "gray" : s === "rejected" ? "red" : "blue";
  return <Badge color={color} variant="light" size="sm">{status}</Badge>;
}

function EnvBadge({ env }: { env: string }) {
  return (
    <Badge color={env === "REAL" ? "orange" : "gray"} variant="outline" size="xs">
      {env}
    </Badge>
  );
}

export function SignalsPage() {
  const [env, setEnv] = useState<"SIMULATE" | "REAL">("REAL");
  const [accType, setAccType] = useState<"ALL" | "MARGIN" | "CASH">("ALL");
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [minConf, setMinConf] = useState<number | "">("");

  const fetchAll = async (e = env, at = accType) => {
    setRefreshing(true);
    try {
      const accParam = at !== "ALL" ? `&acc_type=${at}` : "";
      const [sigRes, ordRes, posRes] = await Promise.all([
        fetch(`${API}/signals`),
        fetch(`${API}/orders?broker_env=${e}`),
        fetch(`${API}/positions?broker_env=${e}${accParam}`),
      ]);
      if (sigRes.ok) setSignals((await sigRes.json()) as SignalRow[]);
      if (ordRes.ok) setOrders((await ordRes.json()) as OrderRow[]);
      if (posRes.ok) setPositions((await posRes.json()) as PositionRow[]);
    } finally {
      setRefreshing(false);
    }
  };

  const handleEnvChange = (v: string) => {
    const next = v as "SIMULATE" | "REAL";
    setEnv(next);
    fetchAll(next, accType);
  };

  const handleAccTypeChange = (v: string) => {
    const next = v as "ALL" | "MARGIN" | "CASH";
    setAccType(next);
    fetchAll(env, next);
  };

  useEffect(() => { fetchAll(env, accType); }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return signals.filter((s) => {
      const matchQ = !q || s.ticker.toLowerCase().includes(q) || s.author.toLowerCase().includes(q);
      const matchC = minConf === "" || (s.confidence ?? 0) >= (minConf as number);
      return matchQ && matchC;
    });
  }, [signals, query, minConf]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Signals</Title>
          <Text c="dimmed" size="sm" mt={2}>シグナル・注文・ポジションの監視</Text>
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

      {/* シグナル */}
      <Card withBorder>
        <Group justify="space-between" mb="sm">
          <Text fw={700}>Signals <Text span c="dimmed" size="sm">({filtered.length})</Text></Text>
          <Group gap="sm">
            <TextInput
              size="xs"
              leftSection={<Search size={13} />}
              placeholder="ticker / author"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              style={{ width: 160 }}
            />
            <NumberInput
              size="xs"
              placeholder="min conf"
              value={minConf}
              onChange={(v) => setMinConf(v === "" ? "" : Number(v))}
              min={0} max={1} step={0.05} decimalScale={2}
              style={{ width: 100 }}
            />
          </Group>
        </Group>
        <Divider mb="sm" />
        {filtered.length === 0 ? (
          <Text size="sm" c="dimmed">シグナルがありません。</Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Time</Table.Th>
                <Table.Th>Author</Table.Th>
                <Table.Th>Ticker</Table.Th>
                <Table.Th>Side</Table.Th>
                <Table.Th style={{ textAlign: "right" }}>Conf.</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtered.slice(0, 100).map((s) => (
                <Table.Tr key={s.id}>
                  <Table.Td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                    {new Date(s.created_at).toLocaleString("ja-JP")}
                  </Table.Td>
                  <Table.Td style={{ fontSize: 13 }}>{s.author}</Table.Td>
                  <Table.Td><Text fw={700} size="sm">{s.ticker}</Text></Table.Td>
                  <Table.Td><SideBadge side={s.side} /></Table.Td>
                  <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                    {s.confidence == null ? "—" : s.confidence.toFixed(2)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      <Grid>
        {/* 注文 */}
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card withBorder>
            <Group justify="space-between" mb="sm">
              <Text fw={700}>Orders <Text span c="dimmed" size="sm">({orders.length})</Text></Text>
              <Button variant="subtle" size="xs" leftSection={<RefreshCw size={13} />} onClick={fetchAll} loading={refreshing}>
                Refresh
              </Button>
            </Group>
            <Divider mb="sm" />
            {orders.length === 0 ? (
              <Text size="sm" c="dimmed">注文がありません。</Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Ticker</Table.Th>
                    <Table.Th>Side</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Qty</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Env</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {orders.slice(0, 100).map((o) => (
                    <Table.Tr key={o.id}>
                      <Table.Td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                        {new Date(o.created_at).toLocaleString("ja-JP")}
                      </Table.Td>
                      <Table.Td><Text fw={700} size="sm">{o.ticker}</Text></Table.Td>
                      <Table.Td><SideBadge side={o.side} /></Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>{o.qty}</Table.Td>
                      <Table.Td><StatusBadge status={o.status} /></Table.Td>
                      <Table.Td><EnvBadge env={o.broker_env} /></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>

        {/* ポジション */}
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Card withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text fw={700}>
                Positions <Text span c="dimmed" size="sm">({positions.length})</Text>
              </Text>
              <SegmentedControl
                size="xs"
                value={accType}
                onChange={handleAccTypeChange}
                data={[
                  { value: "ALL", label: "ALL" },
                  { value: "MARGIN", label: "MARGIN" },
                  { value: "CASH", label: "CASH" },
                ]}
              />
            </Group>
            <Divider mb="sm" />
            {positions.length === 0 ? (
              <Text size="sm" c="dimmed">ポジションがありません。</Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Ticker</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Qty</Table.Th>
                    <Table.Th style={{ textAlign: "right" }}>Avg</Table.Th>
                    {accType === "ALL" && <Table.Th>Type</Table.Th>}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {positions.map((p) => (
                    <Table.Tr key={p.id}>
                      <Table.Td><Text fw={700} size="sm">{p.ticker}</Text></Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                        {p.qty > 0 ? `+${p.qty}` : p.qty}
                      </Table.Td>
                      <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                        {p.avg_price.toFixed(2)}
                      </Table.Td>
                      {accType === "ALL" && (
                        <Table.Td>
                          <Badge size="xs" variant="outline" color={p.acc_type === "MARGIN" ? "blue" : "gray"}>
                            {p.acc_type}
                          </Badge>
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
