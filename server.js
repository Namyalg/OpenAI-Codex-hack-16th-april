const { execFile } = require("child_process");
const { promisify } = require("util");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

const execFileAsync = promisify(execFile);

const isDryRunMode = process.argv.includes("--dry-run");
const isTestMode = process.argv.includes("--test");
const isInteractiveMode = !isDryRunMode && !isTestMode;

const labSpec = {
  title: "Linux Device Management with Udev",
  environment: {
    base_image: "ubuntu:22.04",
    notes: "Fresh Ubuntu container with packages installed during the lab as needed.",
  },
  steps: [
    {
      id: 1,
      title: "Update package index",
      command: "apt-get update",
      pre_explanation:
        "Refresh the APT package index so Ubuntu knows which packages are available to install.",
      expected_behavior:
        "APT downloads package lists from Ubuntu repositories and finishes without errors.",
    },
    {
      id: 2,
      title: "Install udev tools",
      command:
        "DEBIAN_FRONTEND=noninteractive apt-get install -y udev util-linux procps",
      pre_explanation:
        "Install the udev toolkit and a few common system utilities used to inspect devices and processes.",
      expected_behavior:
        "APT installs the packages and prints setup messages, ending with a successful install.",
    },
    {
      id: 3,
      title: "Check udevadm",
      command: "udevadm --version",
      pre_explanation:
        "Verify that the udev command-line tool is available inside the container.",
      expected_behavior:
        "A version number is printed, confirming that udevadm is installed.",
    },
    {
      id: 4,
      title: "Inspect a device node",
      command: "udevadm info --query=property --name=/dev/null",
      pre_explanation:
        "Ask udev for the properties of an existing device node so you can see how devices are described by the system.",
      expected_behavior:
        "The command prints key-value properties for /dev/null, such as its device path and subsystem-related metadata.",
    },
    {
      id: 5,
      title: "Trace the device in sysfs",
      command: "ls -l /sys/dev/char/1:3",
      pre_explanation:
        "Show the sysfs entry for the character device backing /dev/null to connect the device file with its kernel representation.",
      expected_behavior:
        "A symbolic link is shown, pointing from /sys/dev/char/1:3 to the underlying device path in /sys.",
    },
  ],
};

let client = null;
let containerId = null;
let rl = null;
let cleanedUp = false;

loadLocalEnv();

if (isInteractiveMode) {
  rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
}

function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, (answer) => resolve(answer.trim()));
  });
}

function loadLocalEnv() {
  const envFiles = [".env.local", ".env"];

  for (const fileName of envFiles) {
    const filePath = path.join(process.cwd(), fileName);

    if (!fs.existsSync(filePath)) {
      continue;
    }

    const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
    for (const line of lines) {
      const trimmedLine = line.trim();
      if (!trimmedLine || trimmedLine.startsWith("#")) {
        continue;
      }

      const separatorIndex = trimmedLine.indexOf("=");
      if (separatorIndex === -1) {
        continue;
      }

      const key = trimmedLine.slice(0, separatorIndex).trim();
      let value = trimmedLine.slice(separatorIndex + 1).trim();

      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }

      if (!(key in process.env)) {
        process.env[key] = value;
      }
    }

    return;
  }
}

function printDivider() {
  console.log("--------------------------------");
}

function printStepHeader(step) {
  printDivider();
  console.log(`Step ${step.id}: ${step.title}`);
  console.log(`Command: ${step.command}`);
  console.log(`About: ${step.pre_explanation}`);
  printDivider();
}

async function preflightChecks() {
  try {
    await execFileAsync("docker", ["--version"]);
  } catch (error) {
    throw new Error(
      `Docker is not installed or not available in PATH. ${error.message}`
    );
  }

  try {
    await execFileAsync("docker", ["info"], { timeout: 10000 });
  } catch (error) {
    const details = (error.stderr || error.message || "").trim();
    throw new Error(
      `Docker is not running or not accessible. ${details || "Start Docker and try again."}`
    );
  }

  if (!process.env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is not set.");
  }

  let OpenAI;
  try {
    OpenAI = require("openai");
  } catch (error) {
    throw new Error(
      `The 'openai' package is not installed. Run 'npm install openai' first. ${error.message}`
    );
  }

  client = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
  });
}

async function startContainer() {
  console.log(`Starting container from image: ${labSpec.environment.base_image}`);

  const { stdout } = await execFileAsync("docker", [
    "run",
    "-d",
    "--rm",
    labSpec.environment.base_image,
    "bash",
    "-c",
    "tail -f /dev/null",
  ]);

  return stdout.trim();
}

async function runCommand(currentContainerId, command) {
  const startedAt = Date.now();
  console.log(`Running command: ${command}`);

  try {
    const { stdout, stderr } = await execFileAsync(
      "docker",
      ["exec", "-u", "root", currentContainerId, "bash", "-lc", command],
      {
        maxBuffer: 10 * 1024 * 1024,
      }
    );

    return {
      stdout,
      stderr,
      exitCode: 0,
      durationMs: Date.now() - startedAt,
      errorMessage: "",
    };
  } catch (error) {
    return {
      stdout: error.stdout || "",
      stderr: error.stderr || "",
      exitCode: typeof error.code === "number" ? error.code : 1,
      durationMs: Date.now() - startedAt,
      errorMessage: error.message || "Unknown command failure",
    };
  }
}

function extractRawText(response) {
  return (
    response.output?.[0]?.content?.[0]?.text?.trim() ||
    response.output_text?.trim() ||
    ""
  );
}

function tryParseJson(text) {
  if (!text) {
    return { parsed: null, raw: "" };
  }

  try {
    return { parsed: JSON.parse(text), raw: text };
  } catch (_) {}

  const codeFenceMatch = text.match(/```json\s*([\s\S]*?)```/i);
  if (codeFenceMatch) {
    try {
      return { parsed: JSON.parse(codeFenceMatch[1]), raw: text };
    } catch (_) {}
  }

  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    try {
      return {
        parsed: JSON.parse(text.slice(firstBrace, lastBrace + 1)),
        raw: text,
      };
    } catch (_) {}
  }

  return { parsed: null, raw: text };
}

async function explainStep(step, result) {
  const prompt = `Command: ${step.command}

Output:
${result.stdout}
${result.stderr}

Exit code: ${result.exitCode}

Explain:
- what happened
- why it matters
- any important insight or gotcha`;

  try {
    const response = await client.responses.create({
      model: "gpt-5.3-codex",
      input: prompt,
      text: {
        format: {
          type: "json_schema",
          name: "lab_step_explanation",
          strict: true,
          schema: {
            type: "object",
            properties: {
              explanation: { type: "string" },
              insight: { type: "string" },
            },
            required: ["explanation", "insight"],
            additionalProperties: false,
          },
        },
      },
    });

    const rawText = extractRawText(response);
    const { parsed, raw } = tryParseJson(rawText);

    if (parsed && typeof parsed === "object") {
      return {
        explanation:
          typeof parsed.explanation === "string" && parsed.explanation.trim()
            ? parsed.explanation.trim()
            : rawText || "No explanation returned.",
        insight:
          typeof parsed.insight === "string" && parsed.insight.trim()
            ? parsed.insight.trim()
            : "",
        parseFailed: false,
        rawResponse: raw,
        error: "",
      };
    }

    return {
      explanation: rawText || "No explanation returned.",
      insight: "",
      parseFailed: true,
      rawResponse: raw,
      error: "",
    };
  } catch (error) {
    return {
      explanation: `Explanation unavailable: ${error.message}`,
      insight: "",
      parseFailed: false,
      rawResponse: "",
      error: error.message || "Unknown OpenAI error",
    };
  }
}

async function answerFollowUp(step, result, userQuestion) {
  const prompt = `Context:
- Command: ${step.command}
- Step explanation: ${step.pre_explanation}
- Command output:
${result.stdout}
${result.stderr}

User question:
${userQuestion}

Answer the question clearly and concisely for a learner using this lab.`;

  try {
    const response = await client.responses.create({
      model: "gpt-5.3-codex",
      input: prompt,
    });

    const rawText = extractRawText(response);
    return rawText || "No follow-up answer returned.";
  } catch (error) {
    return `Follow-up unavailable: ${error.message}`;
  }
}

function printStepResult(result, explanationResult) {
  const combinedOutput = [result.stdout.trim(), result.stderr.trim()]
    .filter(Boolean)
    .join("\n");

  console.log("OUTPUT:");
  console.log(combinedOutput || "(no output)");
  console.log("");

  if (result.exitCode !== 0) {
    console.log(`COMMAND ERROR: exit code ${result.exitCode}`);
    console.log(result.errorMessage || "Command failed.");
    console.log("");
  }

  console.log("EXPLANATION:");
  console.log(explanationResult.explanation || "(no explanation)");
  console.log("");

  if (explanationResult.error) {
    console.log("OPENAI ERROR:");
    console.log(explanationResult.error);
    console.log("");
  }

  if (explanationResult.parseFailed) {
    console.log("PARSING WARNING:");
    console.log("OpenAI did not return valid JSON. Using raw response.");
    console.log(explanationResult.rawResponse || "(empty response)");
    console.log("");
  }

  console.log("INSIGHT:");
  console.log(explanationResult.insight || "(no insight)");
  console.log("");
  console.log(`Execution time: ${result.durationMs} ms`);
  console.log("");
}

function printDryRun() {
  console.log(`Dry run: ${labSpec.title}`);
  console.log("");

  for (const step of labSpec.steps) {
    printStepHeader(step);
    console.log(`Expected: ${step.expected_behavior}`);
    console.log("");
  }
}

async function promptStepAction(step) {
  printStepHeader(step);

  const input = await question(
    "Press Enter to run, type 'skip' to skip, or 'exit' to quit: "
  );
  const normalized = input.toLowerCase();

  if (normalized === "skip") {
    return "skip";
  }

  if (normalized === "exit") {
    return "exit";
  }

  return "run";
}

async function promptFollowUp() {
  return question(
    "Ask a follow-up question about this step (or press Enter to continue): "
  );
}

async function stopContainer() {
  if (!containerId) {
    return;
  }

  try {
    await execFileAsync("docker", ["stop", containerId]);
    console.log(`Stopped container: ${containerId}`);
  } catch (error) {
    console.error(`Failed to stop container ${containerId}: ${error.message}`);
  } finally {
    containerId = null;
  }
}

async function cleanup() {
  if (cleanedUp) {
    return;
  }

  cleanedUp = true;

  if (rl) {
    rl.close();
    rl = null;
  }

  await stopContainer();
}

process.on("SIGINT", async () => {
  console.log("\nReceived interrupt. Cleaning up...");
  await cleanup();
  process.exit(1);
});

process.on("SIGTERM", async () => {
  await cleanup();
  process.exit(1);
});

async function main() {
  try {
    if (isDryRunMode) {
      printDryRun();
      return;
    }

    await preflightChecks();

    containerId = await startContainer();
    console.log(`Started container: ${containerId}`);
    console.log(`Lab: ${labSpec.title}`);
    console.log("");

    const stepsToRun = isTestMode ? labSpec.steps.slice(0, 2) : labSpec.steps;

    for (const step of stepsToRun) {
      if (isInteractiveMode) {
        const action = await promptStepAction(step);

        if (action === "skip") {
          console.log(`Skipped step ${step.id}.`);
          console.log("");
          continue;
        }

        if (action === "exit") {
          console.log("Exiting lab.");
          console.log("");
          break;
        }
      } else {
        printStepHeader(step);
      }

      const result = await runCommand(containerId, step.command);
      const explanationResult = await explainStep(step, result);
      printStepResult(result, explanationResult);

      if (isInteractiveMode) {
        const userQuestion = await promptFollowUp();

        if (userQuestion) {
          const followUpAnswer = await answerFollowUp(step, result, userQuestion);
          console.log("FOLLOW-UP ANSWER:");
          console.log(followUpAnswer);
          console.log("");
        }
      }
    }
  } catch (error) {
    console.error(`Pre-flight or runtime error: ${error.message}`);
    process.exitCode = 1;
  } finally {
    await cleanup();
  }
}

main();
