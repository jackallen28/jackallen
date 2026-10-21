// Empties the e2e server's data folder before each run.
import { rmSync } from "node:fs";

rmSync(new URL("../../test-results/e2e-data", import.meta.url), { recursive: true, force: true });
