import { randomUUID } from "node:crypto";
import { appendFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import process from "node:process";
import "dotenv/config";
import OpenAI from "openai";
import type { ChatCompletionMessageParam, ChatCompletionTool } from "openai/resources/chat/completions";
import { JobStore } from "./spacetime.js";

const tools: ChatCompletionTool[] = [
  {
    type: "function",
    function: {
      name: "calculator",
      description: "Perform one basic arithmetic operation.",
      parameters: {
        type: "object",
        properties: {
          operation: { type: "string", enum: ["add", "subtract", "multiply", "divide"] },
          a: { type: "number" },
          b: { type: "number" },
        },
        required: ["operation", "a", "b"],
        additionalProperties: false,
      },
    },
  },
];

function executeTool(name: string, raw: string): string {
  if (name !== "calculator") throw new Error(`Unknown tool: ${name}`);
  const { operation, a, b } = JSON.parse(raw) as {
    operation: "add" | "subtract" | "multiply" | "divide";
    a: number;
    b: number;
  };
  if (![a, b].every(Number.isFinite)) throw new Error("Calculator requires finite numbers");
  if (operation === "divide" && b === 0) throw new Error("Division by zero");
  const result = { add: a + b, subtract: a - b, multiply: a * b, divide: a / b }[operation];
  return JSON.stringify({ result });
}

async function main(): Promise<void> {
  const prompt = process.argv.slice(2).join(" ").trim();
  if (!prompt) throw new Error('Usage: npm run agent -- "your task"');

  const model = process.env.QWEN_MODEL ?? "Qwen/Qwen3.5-9B";
  const client = new OpenAI({
    baseURL: process.env.QWEN_BASE_URL ?? "http://127.0.0.1:8080/v1",
    apiKey: process.env.QWEN_API_KEY ?? "local",
  });
  const store = new JobStore(
    process.env.SPACETIME_DATABASE ?? "qwen-agent-jobs",
    process.env.SPACETIME_SERVER ?? "local",
  );
  const jobId = randomUUID();
  let sequence = 0;
  const messages: ChatCompletionMessageParam[] = [
    {
      role: "system",
      content: "You are a concise local assistant. Use tools when needed and never invent results.",
    },
    { role: "user", content: prompt },
  ];

  await store.createJob(jobId, prompt, model);
  for (const message of messages) {
    await store.addMessage(randomUUID(), jobId, sequence++, message.role, String(message.content));
  }

  try {
    const maxSteps = Number(process.env.MAX_AGENT_STEPS ?? "6");
    for (let step = 0; step < maxSteps; step++) {
      const stream = await client.chat.completions.create({
        model,
        messages,
        tools,
        tool_choice: "auto",
        temperature: 0.2,
        stream: true,
      });
      let content = "";
      const calls = new Map<number, { id: string; name: string; arguments: string }>();

      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta;
        if (delta?.content) {
          process.stdout.write(delta.content);
          content += delta.content;
        }
        for (const call of delta?.tool_calls ?? []) {
          const current = calls.get(call.index) ?? { id: "", name: "", arguments: "" };
          current.id += call.id ?? "";
          current.name += call.function?.name ?? "";
          current.arguments += call.function?.arguments ?? "";
          calls.set(call.index, current);
        }
      }

      const toolCalls = [...calls.values()].map((call) => ({
        id: call.id,
        type: "function" as const,
        function: { name: call.name, arguments: call.arguments },
      }));
      messages.push({ role: "assistant", content, tool_calls: toolCalls });
      const storedAssistant = toolCalls.length
        ? JSON.stringify({ content, tool_calls: toolCalls })
        : content;
      await store.addMessage(randomUUID(), jobId, sequence++, "assistant", storedAssistant);

      if (!toolCalls.length) {
        process.stdout.write("\n");
        await store.finishJob(jobId, content);
        const datasetPath = process.env.TRAINING_DATASET ?? "data/trajectories.jsonl";
        await mkdir(dirname(datasetPath), { recursive: true });
        await appendFile(
          datasetPath,
          `${JSON.stringify({ id: jobId, model, status: "completed", messages })}\n`,
          "utf8",
        );
        return;
      }

      for (const call of toolCalls) {
        const result = executeTool(call.function.name, call.function.arguments);
        process.stdout.write(`\n[tool ${call.function.name}] ${result}\n`);
        messages.push({ role: "tool", tool_call_id: call.id, content: result });
        await store.addMessage(
          randomUUID(), jobId, sequence++, "tool", result, call.function.name, call.id,
        );
      }
    }
    throw new Error("Agent reached MAX_AGENT_STEPS without a final response");
  } catch (error) {
    await store.failJob(jobId, error instanceof Error ? error.message : String(error));
    throw error;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
