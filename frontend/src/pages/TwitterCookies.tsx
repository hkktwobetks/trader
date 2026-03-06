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
  Notification,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { Check, Cookie, RefreshCw, Save, X } from "lucide-react";

const API = "/api";

type CookieStatus = {
  has_cookies: boolean;
  version: string | null;
  auth_token_preview: string | null;
};

function parseCookiePaste(raw: string): { auth_token: string; ct0: string } {
  let auth_token = "";
  let ct0 = "";
  const pairs = raw.split(/;\s*/);
  for (const p of pairs) {
    const [k, ...v] = p.split("=");
    const key = k.trim();
    const val = v.join("=").trim();
    if (key === "auth_token") auth_token = val;
    if (key === "ct0") ct0 = val;
  }
  return { auth_token, ct0 };
}

export function TwitterCookiesPage() {
  const [status, setStatus] = useState<CookieStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  const [cookiePaste, setCookiePaste] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [ct0, setCt0] = useState("");

  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; title: string; message?: string } | null>(null);

  const parsed = useMemo(() => parseCookiePaste(cookiePaste), [cookiePaste]);

  useEffect(() => {
    if (parsed.auth_token) setAuthToken(parsed.auth_token);
    if (parsed.ct0) setCt0(parsed.ct0);
  }, [parsed.auth_token, parsed.ct0]);

  const fetchStatus = async () => {
    setLoadingStatus(true);
    try {
      const r = await fetch(`${API}/settings/twitter-cookies`);
      if (!r.ok) throw new Error(`${r.status}`);
      setStatus((await r.json()) as CookieStatus);
    } catch (e) {
      setNotice({ kind: "err", title: "ステータス取得に失敗", message: String(e) });
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const saveCookies = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const payload = { auth_token: authToken.trim(), ct0: ct0.trim() };
      if (!payload.auth_token || !payload.ct0) {
        setNotice({ kind: "err", title: "入力不足", message: "auth_token と ct0 の両方を入力してください" });
        return;
      }

      const r = await fetch(`${API}/settings/twitter-cookies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await r.json()) as { status?: string; valid?: boolean; error?: string | null; version?: string | null; detail?: string };

      if (!r.ok) {
        setNotice({ kind: "err", title: "保存に失敗", message: data.detail ?? JSON.stringify(data) });
        return;
      }

      if (data.valid) {
        setNotice({ kind: "ok", title: "Cookie 保存 & 検証成功", message: data.version ? `version: ${data.version}` : undefined });
      } else {
        setNotice({ kind: "err", title: "保存は成功 / 検証は失敗", message: data.error ?? "不明なエラー" });
      }

      await fetchStatus();
    } catch (e) {
      setNotice({ kind: "err", title: "通信エラー", message: String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Twitter Cookies</Title>
          <Text c="dimmed" size="sm" mt={4}>
            X(Twitter) の <code>auth_token</code> と <code>ct0</code> を登録します。
          </Text>
        </Box>
        <Group gap="sm">
          {status && (
            <Badge
              variant="light"
              color={status.has_cookies ? "green" : "red"}
              leftSection={<Cookie size={14} />}
              size="lg"
            >
              {status.has_cookies ? `設定済み (${status.auth_token_preview ?? ""})` : "未設定"}
            </Badge>
          )}
          <Tooltip label="ステータス更新">
            <ActionIcon variant="subtle" size="lg" onClick={fetchStatus} loading={loadingStatus} aria-label="refresh">
              <RefreshCw size={20} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {notice && (
        <Notification
          withCloseButton
          onClose={() => setNotice(null)}
          color={notice.kind === "ok" ? "green" : "red"}
          title={notice.title}
          icon={notice.kind === "ok" ? <Check size={16} /> : <X size={16} />}
        >
          {notice.message}
        </Notification>
      )}

      <Grid>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder>
            <Text fw={800} mb="xs">
              まとめて貼り付け
            </Text>
            <Divider mb="sm" />
            <Text size="sm" c="dimmed" mb="sm">
              DevTools の Cookies からコピーした文字列（<code>auth_token=...; ct0=...;</code>）を
              そのまま貼ると自動で分解します。
            </Text>
            <Textarea
              value={cookiePaste}
              onChange={(e) => setCookiePaste(e.currentTarget.value)}
              minRows={6}
              placeholder="auth_token=xxxxx; ct0=yyyyy; …"
            />
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder>
            <Text fw={800} mb="xs">
              個別入力
            </Text>
            <Divider mb="md" />

            <Stack gap="sm">
              <TextInput
                label="auth_token"
                value={authToken}
                onChange={(e) => setAuthToken(e.currentTarget.value)}
                placeholder="40文字の16進文字列"
                styles={{ input: { fontFamily: "monospace" } }}
              />
              <TextInput
                label="ct0"
                value={ct0}
                onChange={(e) => setCt0(e.currentTarget.value)}
                placeholder="ct0 の値"
                styles={{ input: { fontFamily: "monospace" } }}
              />

              <Group justify="flex-end" mt="xs">
                <Button
                  leftSection={<Save size={16} />}
                  onClick={saveCookies}
                  loading={saving}
                >
                  保存 & テスト
                </Button>
              </Group>
            </Stack>
          </Card>

          <Card withBorder mt="md" bg="gray.0">
            <Text fw={800} mb={6}>
              手順
            </Text>
            <Text size="sm" c="dimmed">
              1) x.com にログイン → 2) DevTools → Application → Cookies → x.com → 3) auth_token / ct0 をコピー
            </Text>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
