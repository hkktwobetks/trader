import React, { useRef, useState } from "react";
import {
  ActionIcon,
  Box,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { Bot, Send, Trash2 } from "lucide-react";

const API = "/api";

type QA = {
  id: number;
  query: string;
  answer: string | null;
  error: string | null;
  loading: boolean;
};

const EXAMPLES = [
  "AAPLの直近の動向を教えて",
  "TSLAは今買いタイミング？",
  "NVDAについて強気か弱気か判断して",
  "今週注目すべき米国株を1つ挙げて",
];

export function DexterPage() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<QA[]>([]);
  const [nextId, setNextId] = useState(1);
  const bottomRef = useRef<HTMLDivElement>(null);

  const submit = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;

    const id = nextId;
    setNextId((n) => n + 1);
    setQuery("");

    const entry: QA = { id, query: trimmed, answer: null, error: null, loading: true };
    setHistory((h) => [...h, entry]);

    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);

    try {
      const r = await fetch(`${API}/dexter/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed }),
      });
      const data = (await r.json()) as { answer?: string; detail?: string };
      if (!r.ok) {
        setHistory((h) =>
          h.map((e) => e.id === id ? { ...e, loading: false, error: data.detail ?? "エラー" } : e)
        );
      } else {
        setHistory((h) =>
          h.map((e) => e.id === id ? { ...e, loading: false, answer: data.answer ?? "" } : e)
        );
      }
    } catch (err) {
      setHistory((h) =>
        h.map((e) => e.id === id ? { ...e, loading: false, error: String(err) } : e)
      );
    }

    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(query);
    }
  };

  return (
    <Stack gap="lg" h="calc(100dvh - 64px - 48px)" style={{ display: "flex", flexDirection: "column" }}>
      <Group justify="space-between" align="flex-end">
        <Box>
          <Title order={2}>Dexter</Title>
          <Text c="dimmed" size="sm" mt={4}>
            銘柄について質問すると Dexter エージェントが調査・回答します。
          </Text>
        </Box>
        {history.length > 0 && (
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            onClick={() => setHistory([])}
            aria-label="履歴をクリア"
            title="履歴をクリア"
          >
            <Trash2 size={18} />
          </ActionIcon>
        )}
      </Group>

      {/* 会話履歴 */}
      <ScrollArea flex={1} style={{ minHeight: 0 }}>
        {history.length === 0 ? (
          <Stack gap="sm" pt="xl" align="center">
            <Bot size={48} strokeWidth={1.2} color="var(--mantine-color-dimmed)" />
            <Text c="dimmed" size="sm">銘柄について何でも聞いてください。</Text>
            <Group gap="xs" wrap="wrap" justify="center" mt="xs">
              {EXAMPLES.map((ex) => (
                <Button
                  key={ex}
                  variant="light"
                  size="xs"
                  color="gray"
                  onClick={() => submit(ex)}
                >
                  {ex}
                </Button>
              ))}
            </Group>
          </Stack>
        ) : (
          <Stack gap="md" pb="md">
            {history.map((qa) => (
              <Stack key={qa.id} gap="xs">
                {/* 質問 */}
                <Group justify="flex-end">
                  <Card
                    withBorder
                    radius="md"
                    p="sm"
                    style={{ maxWidth: "75%", background: "var(--mantine-color-blue-0)" }}
                  >
                    <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{qa.query}</Text>
                  </Card>
                </Group>

                {/* 回答 */}
                <Group justify="flex-start" align="flex-start" gap="xs">
                  <Box pt={4}>
                    <Bot size={20} strokeWidth={1.5} />
                  </Box>
                  <Card
                    withBorder
                    radius="md"
                    p="sm"
                    style={{ maxWidth: "80%", flex: 1 }}
                  >
                    {qa.loading ? (
                      <Group gap="xs">
                        <Loader size="xs" />
                        <Text size="sm" c="dimmed">調査中… (数分かかる場合があります)</Text>
                      </Group>
                    ) : qa.error ? (
                      <Stack gap={4}>
                        {qa.error.includes("DEXTER_DIR") ? (
                          <>
                            <Text size="sm" fw={600}>Dexter が設定されていません</Text>
                            <Text size="sm" c="dimmed">
                              <Code>DEXTER_DIR</Code>（Dexter リポジトリのパス）を <Code>backend/.env.local</Code> に設定して再起動してください。
                            </Text>
                          </>
                        ) : (
                          <>
                            <Text size="sm" c="red" fw={600}>エラー</Text>
                            <Code block style={{ fontSize: 12 }}>{qa.error}</Code>
                          </>
                        )}
                      </Stack>
                    ) : (
                      <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{qa.answer}</Text>
                    )}
                  </Card>
                </Group>
              </Stack>
            ))}
            <div ref={bottomRef} />
          </Stack>
        )}
      </ScrollArea>

      {/* 入力欄 */}
      <Card withBorder p="sm">
        <Group gap="sm" align="flex-end">
          <Textarea
            flex={1}
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            onKeyDown={onKeyDown}
            placeholder="銘柄について質問する… (Enter で送信 / Shift+Enter で改行)"
            minRows={1}
            maxRows={4}
            autosize
            styles={{ input: { resize: "none" } }}
          />
          <ActionIcon
            size="lg"
            variant="filled"
            onClick={() => submit(query)}
            disabled={!query.trim()}
            aria-label="送信"
          >
            <Send size={16} />
          </ActionIcon>
        </Group>
      </Card>

      <Divider />
      <Text size="xs" c="dimmed">
        Dexter を使うには <Code>DEXTER_DIR</Code>（Dexter リポジトリのパス）と <Code>bun</Code> のインストールが必要です。
      </Text>
    </Stack>
  );
}
