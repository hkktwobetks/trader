import React, { useMemo, useState } from "react";
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
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { FlaskConical, Play, RefreshCw } from "lucide-react";

const API = "/api";

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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card withBorder>
      <Text size="xs" tt="uppercase" fw={700} c="dimmed">
        {label}
      </Text>
      <Text fz={24} fw={800} mt={6} style={{ fontVariantNumeric: "tabular-nums" }}>
        {value}
      </Text>
    </Card>
  );
}

export function BacktestPage() {
  const [backtest, setBacktest] = useState<SmaBacktestResult | null>(null);
  const [btSymbol, setBtSymbol] = useState("AAPL");
  const [btStart, setBtStart] = useState("2024-01-01");
  const [btEnd, setBtEnd] = useState("2024-12-31");
  const [btShort, setBtShort] = useState(5);
  const [btLong, setBtLong] = useState(20);
  const [btLoading, setBtLoading] = useState(false);

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

  const summary = useMemo(() => {
    if (!backtest) return null;
    return {
      totalReturn: `${backtest.total_return_pct >= 0 ? "+" : ""}${backtest.total_return_pct.toFixed(2)}%`,
      mdd: `${backtest.max_drawdown_pct.toFixed(2)}%`,
      finalEq: `${backtest.final_equity.toFixed(2)}`,
      nTrades: `${backtest.trades.length}`,
    };
  }, [backtest]);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Backtest Lab</Title>
          <Text c="dimmed" size="sm" mt={4}>
            SMA クロスの簡易バックテストを実行し、結果を一覧で確認します。
          </Text>
        </Box>
        <Group gap="sm">
          <Badge variant="light" size="lg" leftSection={<FlaskConical size={14} />}>
            Experiment
          </Badge>
          <Tooltip label="Run">
            <ActionIcon variant="subtle" size="lg" onClick={runBacktest} loading={btLoading} aria-label="run">
              <Play size={20} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Grid>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Text fw={800}>Parameters</Text>
              <Button variant="light" onClick={runBacktest} leftSection={<RefreshCw size={16} />} loading={btLoading}>
                Run
              </Button>
            </Group>
            <Divider mb="md" />

            <SimpleGrid cols={2} spacing="sm">
              <TextInput label="Symbol" value={btSymbol} onChange={(e) => setBtSymbol(e.currentTarget.value)} />
              <TextInput label="Timeframe" value="1Day" readOnly />
              <TextInput label="Start" type="date" value={btStart} onChange={(e) => setBtStart(e.currentTarget.value)} />
              <TextInput label="End" type="date" value={btEnd} onChange={(e) => setBtEnd(e.currentTarget.value)} />
              <NumberInput label="Short" value={btShort} onChange={(v) => setBtShort(Number(v) || 0)} min={1} />
              <NumberInput label="Long" value={btLong} onChange={(v) => setBtLong(Number(v) || 0)} min={1} />
            </SimpleGrid>

            <Card withBorder mt="md" bg="gray.0">
              <Text size="sm" fw={700}>
                Note
              </Text>
              <Text size="sm" c="dimmed">
                現状のAPIは「SMA戦略」固定です。今後 RSI / MACD や、手数料・スリッページ等
                のパラメータを追加すると研究画面として豪華になります。
              </Text>
            </Card>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="md">
            <Card withBorder>
              <Text fw={800} mb="xs">
                Result Summary
              </Text>
              <Divider mb="md" />

              {summary ? (
                <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
                  <Metric label="Total Return" value={summary.totalReturn} />
                  <Metric label="Max DD" value={summary.mdd} />
                  <Metric label="Final Equity" value={summary.finalEq} />
                  <Metric label="#Trades" value={summary.nTrades} />
                </SimpleGrid>
              ) : (
                <Text size="sm" c="dimmed">
                  まだ結果がありません。左の Run ボタンでバックテストを実行してください。
                </Text>
              )}
            </Card>

            <Card withBorder>
              <Group justify="space-between" mb="xs">
                <Text fw={800}>Trades</Text>
                {btLoading && <Loader size="sm" />}
              </Group>
              <Divider mb="sm" />

              {backtest == null ? (
                <Text size="sm" c="dimmed">
                  バックテスト結果がありません。
                </Text>
              ) : backtest.trades.length === 0 ? (
                <Text size="sm" c="dimmed">
                  トレードが発生しませんでした。
                </Text>
              ) : (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Entry</Table.Th>
                      <Table.Th>Exit</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>Entry Px</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>Exit Px</Table.Th>
                      <Table.Th style={{ textAlign: "right" }}>PnL</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {backtest.trades.slice(0, 200).map((t, idx) => (
                      <Table.Tr key={`${t.entry_date}-${t.exit_date}-${idx}`}>
                        <Table.Td>{t.entry_date}</Table.Td>
                        <Table.Td>{t.exit_date}</Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {t.entry_price.toFixed(2)}
                        </Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {t.exit_price.toFixed(2)}
                        </Table.Td>
                        <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {t.pnl >= 0 ? "+" : ""}
                          {t.pnl.toFixed(2)}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
