import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import {
  MantineProvider,
  createTheme,
  AppShell,
  Container,
  Title,
  Text,
  Group,
  Box,
} from "@mantine/core";
import { Dashboard } from "./pages/Dashboard";

const theme = createTheme({
  primaryColor: "blue",
  defaultRadius: "md",
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  headings: { fontFamily: "'Inter', sans-serif", fontWeight: "600" },
  components: {
    Card: {
      defaultProps: { shadow: "sm", padding: "lg", radius: "md" },
    },
    Table: {
      defaultProps: { withTableBorder: true, withColumnBorders: false },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <MantineProvider theme={theme} withNormalizeCSS withGlobalStyles>
      <AppShell header={{ height: 64 }} padding="md">
        <AppShell.Header>
          <Group h="100%" px="lg" justify="space-between">
            <Box>
              <Title order={4} fw={700} lh={1.2}>
                Social Signal Trader
              </Title>
              <Text size="xs" c="dimmed" mt={2}>
                シグナル・バックテスト・運用モニタリング
              </Text>
            </Box>
          </Group>
        </AppShell.Header>
        <AppShell.Main>
          <Container size="xl" py="lg">
            <Dashboard />
          </Container>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  </React.StrictMode>,
);

