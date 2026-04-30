import React, { useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Divider,
  Group,
  Image,
  Loader,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { AlertTriangle, RefreshCw, Twitter } from "lucide-react";

const API = "/api";

type TradingSettings = {
  broker: string;
  broker_env: string;
  twitter_broker_env: string;
  dexter_broker_env: string;
  auto_trade_enabled: boolean;
  twitter_polling_enabled: boolean;
  twitter_auto_trade_enabled: boolean;
  dexter_auto_trade_enabled: boolean;
};

type OpendStatus = {
  connected: boolean;
  captcha_pending: boolean;
  captcha_path: string | null;
};

type WorkerEntry = {
  last_seen: string | null;
  seconds_ago: number | null;
  alive: boolean;
  enabled: boolean;
};

type WorkersStatus = {
  twitter: WorkerEntry;
};

function EnvControl({
  label,
  sub,
  value,
  onChange,
  disabled,
}: {
  label: string;
  sub?: string;
  value: "REAL" | "SIMULATE";
  onChange: (v: "REAL" | "SIMULATE") => void;
  disabled?: boolean;
}) {
  return (
    <Group justify="space-between" align="center" wrap="nowrap">
      <Box>
        <Text size="sm" fw={600}>{label}</Text>
        {sub && <Text size="xs" c="dimmed">{sub}</Text>}
      </Box>
      <SegmentedControl
        size="xs"
        value={value}
        onChange={(v) => onChange(v as "REAL" | "SIMULATE")}
        disabled={disabled}
        data={[
          {
            value: "SIMULATE",
            label: <Text size="xs" fw={600}>SIMULATE</Text>,
          },
          {
            value: "REAL",
            label: (
              <Text size="xs" fw={700} c={value === "REAL" ? "orange" : undefined}>
                REAL
              </Text>
            ),
          },
        ]}
        styles={(theme) => ({
          root: { background: theme.colors.gray[1] },
          indicator: {
            background: value === "REAL" ? theme.colors.orange[1] : theme.white,
            border: value === "REAL" ? `1.5px solid ${theme.colors.orange[4]}` : undefined,
          },
        })}
      />
    </Group>
  );
}

function AutoTradeToggle({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <Group justify="space-between" align="center">
      <Text size="sm" fw={600}>{label}</Text>
      <Switch
        size="sm"
        checked={checked}
        onChange={(e) => onChange(e.currentTarget.checked)}
        disabled={disabled}
        color="teal"
        label={checked ? "ON" : "OFF"}
      />
    </Group>
  );
}

function OpendCard() {
  const [status, setStatus] = useState<OpendStatus | null>(null);
  const [captchaImg, setCaptchaImg] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const loadStatus = async () => {
    try {
      const r = await fetch(`${API}/opend/status`);
      if (r.ok) {
        const s = (await r.json()) as OpendStatus;
        setStatus(s);
        if (s.captcha_pending) {
          const ir = await fetch(`${API}/opend/captcha-image`);
          if (ir.ok) setCaptchaImg(((await ir.json()) as { image: string }).image);
        } else {
          setCaptchaImg(null);
        }
      }
    } catch { /* silent */ }
  };

  useEffect(() => {
    loadStatus();
    const t = setInterval(loadStatus, 15_000);
    return () => clearInterval(t);
  }, []);

  const submit = async () => {
    if (!code.trim()) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const r = await fetch(`${API}/opend/submit-captcha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      const data = await r.json();
      if (r.ok) {
        setMessage({ ok: true, text: `送信完了: ${data.response || "OK"}` });
        setCode("");
        setTimeout(loadStatus, 2000);
      } else {
        setMessage({ ok: false, text: data.detail ?? "エラー" });
      }
    } catch (e) {
      setMessage({ ok: false, text: String(e) });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card withBorder>
      <Group justify="space-between" mb="sm">
        <Text fw={700}>Moomoo OpenD</Text>
        <Group gap="xs">
          {status ? (
            <Badge color={status.connected ? "teal" : "red"} variant="dot" size="sm">
              {status.connected ? "CONNECTED" : "DISCONNECTED"}
            </Badge>
          ) : (
            <Badge color="gray" variant="dot" size="sm">UNKNOWN</Badge>
          )}
          <Button variant="subtle" size="xs" leftSection={<RefreshCw size={12} />} onClick={loadStatus}>
            更新
          </Button>
        </Group>
      </Group>
      <Divider mb="md" />

      {status?.captcha_pending ? (
        <Stack gap="sm">
          <Alert color="yellow" variant="light">
            <Text size="sm" fw={600}>キャプチャ認証が必要です</Text>
            <Text size="xs" mt={2}>ログイン時に画像認証が要求されています。コードを入力して送信してください。</Text>
          </Alert>
          {captchaImg && (
            <Image src={captchaImg} alt="captcha" w={200} radius="sm" />
          )}
          <Group gap="sm" align="flex-end">
            <TextInput
              label="認証コード"
              placeholder="例: AB12"
              value={code}
              onChange={(e) => setCode(e.currentTarget.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
              size="sm"
              style={{ flex: 1 }}
            />
            <Button size="sm" onClick={submit} loading={submitting} disabled={!code.trim()}>
              送信
            </Button>
          </Group>
          {message && (
            <Text size="xs" c={message.ok ? "teal" : "red"}>{message.text}</Text>
          )}
        </Stack>
      ) : (
        <Text size="sm" c={status?.connected ? "teal" : "dimmed"}>
          {status?.connected
            ? "OpenD は正常に接続されています。"
            : "OpenD が起動していません。docker compose --profile moomoo up -d opend で起動してください。"}
        </Text>
      )}
    </Card>
  );
}

function WorkerStatusCard({
  workers,
  onToggle,
}: {
  workers: WorkersStatus | null;
  onToggle: (enabled: boolean) => void;
}) {
  const tw = workers?.twitter;

  const agoLabel = (sec: number | null | undefined) => {
    if (sec == null) return "不明";
    if (sec < 60) return `${sec}秒前`;
    return `${Math.floor(sec / 60)}分${sec % 60}秒前`;
  };

  return (
    <Card withBorder>
      <Text fw={700} mb="sm">Worker Status</Text>
      <Divider mb="md" />
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Group gap="sm" align="center">
          <Twitter size={18} />
          <Box>
            <Text size="sm" fw={600}>Twitter Polling</Text>
            <Text size="xs" c="dimmed">
              {tw ? (tw.alive ? `最終応答: ${agoLabel(tw.seconds_ago)}` : `最終応答: ${agoLabel(tw.seconds_ago)}`) : "読み込み中…"}
            </Text>
          </Box>
          {tw ? (
            <Badge color={tw.alive ? "teal" : "red"} variant="dot" size="sm">
              {tw.alive ? "ALIVE" : "DOWN"}
            </Badge>
          ) : (
            <Badge color="gray" variant="dot" size="sm">UNKNOWN</Badge>
          )}
        </Group>
        <Switch
          size="sm"
          checked={tw?.enabled ?? true}
          onChange={(e) => onToggle(e.currentTarget.checked)}
          label={tw?.enabled ? "ON" : "OFF"}
          color="teal"
        />
      </Group>
    </Card>
  );
}

export function SettingsPage() {
  const [settings, setSettings] = useState<TradingSettings | null>(null);
  const [workers, setWorkers] = useState<WorkersStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const workerTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/settings/trading`);
      if (r.ok) setSettings(await r.json());
    } finally {
      setLoading(false);
    }
  };

  const loadWorkers = async () => {
    try {
      const r = await fetch(`${API}/workers/status`);
      if (r.ok) setWorkers(await r.json());
    } catch { /* silent */ }
  };

  useEffect(() => {
    load();
    loadWorkers();
    workerTimerRef.current = setInterval(loadWorkers, 15_000);
    return () => { if (workerTimerRef.current) clearInterval(workerTimerRef.current); };
  }, []);

  const patch = async (update: Partial<TradingSettings>) => {
    if (!settings) return;
    setSaving(true);
    const optimistic = { ...settings, ...update };
    setSettings(optimistic);
    try {
      const r = await fetch(`${API}/settings/trading`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      });
      if (r.ok) setSettings(await r.json());
    } catch {
      load();
    } finally {
      setSaving(false);
    }
  };

  const anyReal =
    settings?.broker_env === "REAL" ||
    settings?.twitter_broker_env === "REAL" ||
    settings?.dexter_broker_env === "REAL";

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Settings</Title>
          <Text c="dimmed" size="sm" mt={2}>取引環境・自動注文の設定</Text>
        </Box>
        {saving && <Loader size="xs" />}
      </Group>

      {anyReal && (
        <Alert icon={<AlertTriangle size={16} />} color="orange" variant="light">
          <Text size="sm" fw={600}>REAL口座が有効です</Text>
          <Text size="xs" mt={2}>実際の資金で取引されます。設定を十分に確認してください。</Text>
        </Alert>
      )}

      <OpendCard />

      <WorkerStatusCard
        workers={workers}
        onToggle={(enabled) => patch({ twitter_polling_enabled: enabled })}
      />

      {loading ? (
        <Loader size="sm" />
      ) : settings ? (
        <>
          {/* Broker Environment */}
          <Card withBorder>
            <Text fw={700} mb="sm">
              Broker Environment
              <Badge ml="sm" size="xs" color="gray" variant="outline">{settings.broker}</Badge>
            </Text>
            <Text size="xs" c="dimmed" mb="md">
              シグナルソースごとに注文先口座（REAL / SIMULATE）を設定します。<br />
              REAL は実口座、SIMULATE は紙トレードです。
            </Text>
            <Divider mb="md" />
            <Stack gap="md">
              <EnvControl
                label="Default"
                sub="手動 POST シグナルなどのデフォルト"
                value={settings.broker_env as "REAL" | "SIMULATE"}
                onChange={(v) => patch({ broker_env: v })}
              />
              <Divider />
              <EnvControl
                label="Twitter"
                sub="Twitter/X から取得したシグナル"
                value={settings.twitter_broker_env as "REAL" | "SIMULATE"}
                onChange={(v) => patch({ twitter_broker_env: v })}
              />
              <Divider />
              <EnvControl
                label="Dexter"
                sub="Dexter エージェントが生成したシグナル"
                value={settings.dexter_broker_env as "REAL" | "SIMULATE"}
                onChange={(v) => patch({ dexter_broker_env: v })}
              />
            </Stack>
          </Card>

          {/* Auto Trade */}
          <Card withBorder>
            <Text fw={700} mb="sm">Auto Trade</Text>
            <Text size="xs" c="dimmed" mb="md">
              信頼度が閾値を超えたシグナルを自動的に発注するかどうかの設定です。
            </Text>
            <Divider mb="md" />
            <Stack gap="md">
              <AutoTradeToggle
                label="Default"
                checked={settings.auto_trade_enabled}
                onChange={(v) => patch({ auto_trade_enabled: v })}
              />
              <Divider />
              <AutoTradeToggle
                label="Twitter (Auto Trade)"
                checked={settings.twitter_auto_trade_enabled}
                onChange={(v) => patch({ twitter_auto_trade_enabled: v })}
              />
              <Divider />
              <AutoTradeToggle
                label="Dexter"
                checked={settings.dexter_auto_trade_enabled}
                onChange={(v) => patch({ dexter_auto_trade_enabled: v })}
              />
            </Stack>
          </Card>
        </>
      ) : (
        <Text c="dimmed" size="sm">設定の読み込みに失敗しました。</Text>
      )}
    </Stack>
  );
}
