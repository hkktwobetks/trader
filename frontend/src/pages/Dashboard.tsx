/// <reference lib="ES2020" />
/// <reference lib="DOM" />
import React, { useEffect, useState } from "react";
import {
  Card,
  Group,
  Stack,
  Text,
  Loader,
  Table,
  NumberInput,
  Button,
  Grid,
  Tabs,
  TextInput,
  Badge,
  ActionIcon,
  Tooltip,
  Divider,
  Box,
} from "@mantine/core";
import { RefreshCw } from "lucide-react";

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

type SmaBacktestResult = {
  symbol: string;
  start: string;
  end: string;
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  trades: {
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    pnl: number;
  }[];
};

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

export function Dashboard() {
  const [health, setHealth] = useState<"ok" | "ng" | "loading">("loading");
  const [pnl, setPnl] = useState<DailyPnl[]>([]);
  const [perf, setPerf] = useState<PerformanceSummary | null>(null);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [backtest, setBacktest] = useState<SmaBacktestResult | null>(null);
  const [btSymbol, setBtSymbol] = useState("AAPL");
  const [btStart, setBtStart] = useState("2024-01-01");
  const [btEnd, setBtEnd] = useState("2024-12-31");
  const [btShort, setBtShort] = useState(5);
  const [btLong, setBtLong] = useState(20);
  const [btLoading, setBtLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = async (): Promise<void> => {
    setRefreshing(true);
    try {
      const [hRes, pnlRes, perfRes, sigRes, ordRes, posRes] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/metrics/pnl/daily`),
        fetch(`${API}/metrics/performance`),
        fetch(`${API}/signals`),
        fetch(`${API}/orders`),
        fetch(`${API}/positions`),
      ]);
      setHealth(hRes.ok ? "ok" : "ng");
      if (pnlRes.ok) setPnl((await pnlRes.json()) as DailyPnl[]);
      if (perfRes.ok) setPerf((await perfRes.json()) as PerformanceSummary);
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

  const runBacktest = async () => {
    setBtLoading(true);
    setBacktest(null);
    try {
      const res = await fetch(`${API}/backtest/sma`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: btSymbol.trim().toUpperCase() || "AAPL",
          timeframe: "1Day",
          start: btStart,
          end: btEnd,
          short_window: btShort,
          long_window: btLong,
        }),
      });
      if (res.ok) setBacktest((await res.json()) as SmaBacktestResult);
    } finally {
      setBtLoading(false);
    }
  };

  return (
    <Stack gap="lg">
      <Group justify="flex-end">
        <Tooltip label="データを再読み込み">
          <ActionIcon
            variant="subtle"
            size="lg"
            onClick={fetchAll}
            loading={refreshing}
            aria-label="再読み込み"
          >
            <RefreshCw size={20} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <Tabs defaultValue="overview" variant="outline">
        <Tabs.List mb="md">
          <Tabs.Tab value="overview">概要</Tabs.Tab>
          <Tabs.Tab value="trading">シグナル・注文・ポジション</Tabs.Tab>
          <Tabs.Tab value="performance">パフォーマンス</Tabs.Tab>
          <Tabs.Tab value="backtest">バックテスト</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          <Stack gap="lg">
            <Grid>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Card withBorder padding="lg">
                  <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb="xs">
                    API ヘルス
                  </Text>
                  <Group>
                    {health === "loading" && !refreshing && <Loader size="sm" />}
                    {health === "ok" && (
                      <Badge color="green" size="lg" variant="light">
                        OK
                      </Badge>
                    )}
                    {health === "ng" && (
                      <Badge color="red" size="lg" variant="light">
                        NG
                      </Badge>
                    )}
                  </Group>
                </Card>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 8 }}>
                <Card withBorder padding="lg">
                  <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb="xs">
                    パフォーマンス概要（実績 PnL ベース）
                  </Text>
                  {perf && (perf.start_date ?? perf.end_date) ? (
                    <Group gap="xl" wrap="wrap">
                      <Box>
                        <Text size="xs" c="dimmed">期間</Text>
                        <Text size="sm" fw={500}>{perf.start_date} 〜 {perf.end_date}</Text>
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">総リターン</Text>
                        <Text fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                          {perf.total_return_pct >= 0 ? "+" : ""}{perf.total_return_pct.toFixed(2)}%
                        </Text>
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">CAGR</Text>
                        <Text fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                          {perf.cagr_pct != null ? `${perf.cagr_pct >= 0 ? "+" : ""}${perf.cagr_pct.toFixed(2)}%` : "—"}
                        </Text>
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">最大DD</Text>
                        <Text fw={600} c={perf.max_drawdown_pct < 0 ? "red" : undefined} style={{ fontVariantNumeric: "tabular-nums" }}>
                          {perf.max_drawdown_pct.toFixed(2)}%
                        </Text>
                      </Box>
                    </Group>
                  ) : (
                    <Text size="sm" c="dimmed">
                      PnL データがまだないため計算できません。
                    </Text>
                  )}
                </Card>
              </Grid.Col>
            </Grid>

            <Card withBorder padding="lg">
              <Text fw={600} mb="sm">日次 PnL</Text>
              <Divider mb="sm" />
              {pnl.length === 0 ? (
                <Text size="sm" c="dimmed">まだ PnL データがありません。</Text>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>日付</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>実現損益</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>含み損益</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {pnl.map((row) => (
                      <Table.Tr key={row.id}>
                        <Table.Td>{row.date}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {row.realized >= 0 ? "+" : ""}{row.realized.toFixed(2)}
                        </Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {row.unrealized >= 0 ? "+" : ""}{row.unrealized.toFixed(2)}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="trading" pt="md">
          <Stack gap="lg">
            <Card withBorder padding="lg">
              <Text fw={600} mb="sm">シグナル（直近100件）</Text>
              <Divider mb="sm" />
              {signals.length === 0 ? (
                <Text size="sm" c="dimmed">シグナルがありません。</Text>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>日時</Table.Th>
                      <Table.Th>発信者</Table.Th>
                      <Table.Th>銘柄</Table.Th>
                      <Table.Th>方向</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>信頼度</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {signals.map((row) => (
                      <Table.Tr key={row.id}>
                        <Table.Td>{new Date(row.created_at).toLocaleString("ja-JP")}</Table.Td>
                        <Table.Td>{row.author}</Table.Td>
                        <Table.Td>{row.ticker}</Table.Td>
                        <Table.Td>
                          <Badge color={row.side === "BUY" ? "green" : "red"} size="sm" variant="light">
                            {row.side}
                          </Badge>
                        </Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {row.confidence != null ? (row.confidence * 100).toFixed(0) + "%" : "—"}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>

            <Card withBorder padding="lg">
              <Text fw={600} mb="sm">注文</Text>
              <Divider mb="sm" />
              {orders.length === 0 ? (
                <Text size="sm" c="dimmed">注文がありません。</Text>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>日時</Table.Th>
                      <Table.Th>ブローカー</Table.Th>
                      <Table.Th>銘柄</Table.Th>
                      <Table.Th>方向</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>数量</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>価格</Table.Th>
                      <Table.Th>ステータス</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {orders.map((row) => (
                      <Table.Tr key={row.id}>
                        <Table.Td>{new Date(row.created_at).toLocaleString("ja-JP")}</Table.Td>
                        <Table.Td>{row.broker}</Table.Td>
                        <Table.Td>{row.ticker}</Table.Td>
                        <Table.Td>
                          <Badge color={row.side === "BUY" ? "green" : "red"} size="sm" variant="light">
                            {row.side}
                          </Badge>
                        </Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.qty}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {row.price != null ? row.price.toFixed(2) : "—"}
                        </Table.Td>
                        <Table.Td>{row.status}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>

            <Card withBorder padding="lg">
              <Text fw={600} mb="sm">ポジション</Text>
              <Divider mb="sm" />
              {positions.length === 0 ? (
                <Text size="sm" c="dimmed">ポジションがありません。</Text>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>銘柄</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>数量</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>平均単価</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {positions.map((row) => (
                      <Table.Tr key={row.id}>
                        <Table.Td>{row.ticker}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.qty}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.avg_price.toFixed(2)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="performance" pt="md">
          <Stack gap="lg">
            {perf && perf.equity_curve.length > 0 ? (
              <Card withBorder padding="lg">
                <Text fw={600} mb="sm">エクイティ曲線</Text>
                <Divider mb="sm" />
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>日付</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>資産</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {perf.equity_curve.map((p: { date: string; equity: number }) => (
                      <Table.Tr key={p.date}>
                        <Table.Td>{p.date}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {Number(p.equity).toLocaleString()}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Card>
            ) : (
              <Card withBorder padding="lg">
                <Text size="sm" c="dimmed">
                  パフォーマンスデータ（PnL ベースのエクイティ曲線）がまだありません。
                </Text>
              </Card>
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="backtest" pt="md">
          <Stack gap="lg">
            <Card withBorder padding="lg">
              <Text fw={600} mb="xs">SMA クロス戦略</Text>
              <Text size="xs" c="dimmed" mb="md">
                対象銘柄・期間の日足バーが MarketBar に登録されている必要があります（Alpaca 取得スクリプトで投入）。
              </Text>
              <Divider mb="md" />
              <Grid>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <TextInput
                    label="銘柄（例: AAPL）"
                    value={btSymbol}
                    onChange={(e) => setBtSymbol((e.target as HTMLInputElement).value)}
                    placeholder="AAPL"
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3 }}>
                  <TextInput
                    label="開始日"
                    value={btStart}
                    onChange={(e) => setBtStart((e.target as HTMLInputElement).value)}
                    placeholder="2024-01-01"
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3 }}>
                  <TextInput
                    label="終了日"
                    value={btEnd}
                    onChange={(e) => setBtEnd((e.target as HTMLInputElement).value)}
                    placeholder="2024-12-31"
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3 }}>
                  <NumberInput
                    label="短期 SMA"
                    value={btShort}
                    onChange={(v: string | number) => setBtShort(Number(v) || 1)}
                    min={1}
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 6, sm: 3 }}>
                  <NumberInput
                    label="長期 SMA"
                    value={btLong}
                    onChange={(v: string | number) => setBtLong(Number(v) || 1)}
                    min={1}
                  />
                </Grid.Col>
              </Grid>
              <Button mt="md" loading={btLoading} onClick={runBacktest}>
                バックテスト実行
              </Button>
            </Card>

            {backtest && (
              <Card withBorder padding="lg">
                <Text fw={600} mb="sm">結果サマリ</Text>
                <Divider mb="md" />
                <Group mb="md" gap="md" wrap="wrap">
                  <Badge
                    size="lg"
                    variant="light"
                    color={backtest.total_return_pct >= 0 ? "green" : "red"}
                  >
                    リターン {backtest.total_return_pct >= 0 ? "+" : ""}{backtest.total_return_pct.toFixed(2)}%
                  </Badge>
                  <Badge size="lg" variant="light" color="orange">
                    最大DD {backtest.max_drawdown_pct.toFixed(2)}%
                  </Badge>
                  <Text size="sm" c="dimmed">トレード数: {backtest.trades.length}</Text>
                </Group>
                {backtest.trades.length > 0 ? (
                  <Table striped highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>エントリー</Table.Th>
                        <Table.Th>エグジット</Table.Th>
                        <Table.Th style={{ textAlign: "right" }}>買値</Table.Th>
                        <Table.Th style={{ textAlign: "right" }}>売値</Table.Th>
                        <Table.Th style={{ textAlign: "right" }}>損益</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {backtest.trades.map((t, i) => (
                        <Table.Tr key={i}>
                          <Table.Td>{t.entry_date}</Table.Td>
                          <Table.Td>{t.exit_date}</Table.Td>
                          <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{t.entry_price.toFixed(2)}</Table.Td>
                          <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{t.exit_price.toFixed(2)}</Table.Td>
                          <Table.Td
                            style={{
                              textAlign: "right",
                              fontVariantNumeric: "tabular-nums",
                              color: t.pnl >= 0 ? "var(--mantine-color-green-6)" : "var(--mantine-color-red-6)",
                            }}
                          >
                            {t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(2)}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                ) : (
                  <Text size="sm" c="dimmed">この期間でシグナルが発生しませんでした。</Text>
                )}
              </Card>
            )}
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
