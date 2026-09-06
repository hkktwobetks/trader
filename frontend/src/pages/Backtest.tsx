import React, { useState } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  Loader,
  NumberInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { Play } from "lucide-react";

const API = "/api";

type SignalTrade = {
  signal_id: number;
  ticker: string;
  side: string;
  signal_date: string;
  entry_price: number;
  stop: number | null;
  first_target: number | null;
  exit_price: number | null;
  exit_date: string | null;
  outcome: string;
  pnl: number;
  qty: number;
  rr_ratio: number | null;
};

type SignalBacktestResult = {
  start: string;
  end: string;
  ticker_filter: string | null;
  total_signals: number;
  tradeable: number;
  wins: number;
  losses: number;
  open_trades: number;
  no_fill: number;
  win_rate_pct: number;
  total_pnl: number;
  avg_rr: number | null;
  trades: SignalTrade[];
};

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Card withBorder>
      <Text size="xs" tt="uppercase" fw={700} c="dimmed">{label}</Text>
      <Text fz={22} fw={800} mt={4} c={color} style={{ fontVariantNumeric: "tabular-nums" }}>
        {value}
      </Text>
    </Card>
  );
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const map: Record<string, { color: string; label: string }> = {
    win:       { color: "teal",   label: "WIN" },
    loss:      { color: "red",    label: "LOSS" },
    open:      { color: "blue",   label: "OPEN" },
    no_fill:   { color: "yellow", label: "NO FILL" },
    no_data:   { color: "gray",   label: "NO DATA" },
    no_target: { color: "gray",   label: "NO TARGET" },
    no_entry:  { color: "gray",   label: "NO ENTRY" },
  };
  const m = map[outcome] ?? { color: "gray", label: outcome };
  return <Badge color={m.color} variant="light" size="sm">{m.label}</Badge>;
}

export function BacktestPage() {
  const [ticker, setTicker] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [qty, setQty] = useState<number>(100);
  const [interval, setInterval] = useState("5m");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SignalBacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API}/backtest/signals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase() || null,
          start: start || null,
          end: end || null,
          qty,
          interval,
        }),
      });
      if (!res.ok) {
        setError(`エラー: ${res.status}`);
        return;
      }
      setResult(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Backtest Lab</Title>
          <Text c="dimmed" size="sm" mt={4}>
            記録済みシグナルをベースに、yfinance の実データでトレードをシミュレートします。
          </Text>
        </Box>
      </Group>

      <Grid>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Text fw={800}>Parameters</Text>
              <Button variant="light" onClick={run} leftSection={<Play size={14} />} loading={loading}>
                Run
              </Button>
            </Group>
            <Divider mb="md" />
            <Stack gap="sm">
              <TextInput
                label="Ticker（空欄=全銘柄）"
                placeholder="AAPL"
                value={ticker}
                onChange={(e) => setTicker(e.currentTarget.value)}
              />
              <SimpleGrid cols={2} spacing="sm">
                <TextInput
                  label="開始日"
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.currentTarget.value)}
                />
                <TextInput
                  label="終了日"
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.currentTarget.value)}
                />
              </SimpleGrid>
              <NumberInput
                label="1トレードの株数"
                value={qty}
                onChange={(v) => setQty(Number(v) || 100)}
                min={1}
              />
              <div>
                <Text size="sm" fw={500} mb={4}>バーサイズ</Text>
                <SegmentedControl
                  size="xs"
                  value={interval}
                  onChange={setInterval}
                  data={[
                    { value: "1m", label: "1m" },
                    { value: "5m", label: "5m" },
                    { value: "15m", label: "15m" },
                    { value: "1h", label: "1h" },
                    { value: "1d", label: "1d" },
                  ]}
                  fullWidth
                />
              </div>
            </Stack>

            <Card withBorder mt="md" bg="gray.0">
              <Text size="xs" fw={700} mb={4}>シミュレーションロジック</Text>
              <Text size="xs" c="dimmed">
                <b>Phase 1</b>: エントリー価格に初めてタッチするバーを待つ
                （BUY: 安値 ≤ entry / SELL: 高値 ≥ entry）。
                到達しなければ NO FILL。<br />
                <b>Phase 2</b>: 成立バー以降で安値 ≤ stop → LOSS、
                高値 ≥ target → WIN を判定。同バーは LOSS 優先。<br />
                5m/15m: 直近 60 日、1m: 7 日が上限。古いシグナルは 1d に自動フォールバック。
              </Text>
            </Card>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap="md">
            {error && (
              <Card withBorder bg="red.0">
                <Text size="sm" c="red">{error}</Text>
              </Card>
            )}

            {loading && (
              <Card withBorder>
                <Group gap="sm">
                  <Loader size="sm" />
                  <Text size="sm" c="dimmed">yfinance でデータ取得中…（数秒かかります）</Text>
                </Group>
              </Card>
            )}

            {result && (
              <>
                <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
                  <Metric label="シグナル数" value={String(result.total_signals)} />
                  <Metric
                    label="勝率"
                    value={result.wins + result.losses > 0 ? `${result.win_rate_pct}%` : "—"}
                    color={result.win_rate_pct >= 50 ? "teal" : "red"}
                  />
                  <Metric
                    label="合計損益"
                    value={`${result.total_pnl >= 0 ? "+" : ""}$${result.total_pnl.toFixed(0)}`}
                    color={result.total_pnl >= 0 ? "teal" : "red"}
                  />
                  <Metric
                    label="平均 R:R"
                    value={result.avg_rr != null ? result.avg_rr.toFixed(2) : "—"}
                  />
                </SimpleGrid>

                <Card withBorder>
                  <Group gap="md" mb="sm">
                    <Text size="sm"><Text span fw={700}>{result.wins}</Text> <Text span c="teal">WIN</Text></Text>
                    <Text size="sm"><Text span fw={700}>{result.losses}</Text> <Text span c="red">LOSS</Text></Text>
                    <Text size="sm"><Text span fw={700}>{result.open_trades}</Text> <Text span c="blue">OPEN</Text></Text>
                    <Text size="sm"><Text span fw={700}>{result.no_fill ?? 0}</Text> <Text span c="yellow.7">NO FILL</Text></Text>
                    <Text size="sm" c="dimmed">({result.tradeable} エントリーあり)</Text>
                  </Group>
                  <Divider mb="sm" />

                  {result.trades.length === 0 ? (
                    <Text size="sm" c="dimmed">トレードがありません。</Text>
                  ) : (
                    <Table striped highlightOnHover>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th>Date</Table.Th>
                          <Table.Th>Ticker</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>Entry</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>Stop</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>Target</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>Exit</Table.Th>
                          <Table.Th>Result</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>R:R</Table.Th>
                          <Table.Th style={{ textAlign: "right" }}>PnL</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {result.trades.map((t) => (
                          <Table.Tr key={t.signal_id}>
                            <Table.Td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                              {new Date(t.signal_date).toLocaleString("ja-JP")}
                            </Table.Td>
                            <Table.Td>
                              <Text fw={700} size="sm">{t.ticker}</Text>
                            </Table.Td>
                            <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                              {t.entry_price ? `$${t.entry_price.toFixed(2)}` : "—"}
                            </Table.Td>
                            <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                              {t.stop != null ? <Text size="sm" c="red">${t.stop.toFixed(2)}</Text> : <Text size="xs" c="dimmed">—</Text>}
                            </Table.Td>
                            <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                              {t.first_target != null ? <Text size="sm" c="teal">${t.first_target.toFixed(2)}</Text> : <Text size="xs" c="dimmed">—</Text>}
                            </Table.Td>
                            <Table.Td style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>
                              {t.exit_price != null
                                ? <><Text size="sm" span>${t.exit_price.toFixed(2)}</Text><br/><Text size="xs" c="dimmed">{t.exit_date ?? ""}</Text></>
                                : "—"}
                            </Table.Td>
                            <Table.Td><OutcomeBadge outcome={t.outcome} /></Table.Td>
                            <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                              {t.rr_ratio != null ? t.rr_ratio.toFixed(2) : "—"}
                            </Table.Td>
                            <Table.Td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                              {t.pnl !== 0 ? (
                                <Text size="sm" c={t.pnl >= 0 ? "teal" : "red"} fw={600}>
                                  {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(0)}
                                </Text>
                              ) : "—"}
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  )}
                </Card>
              </>
            )}

            {!result && !loading && !error && (
              <Card withBorder>
                <Text size="sm" c="dimmed">
                  左の Run ボタンでバックテストを実行してください。
                </Text>
              </Card>
            )}
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
