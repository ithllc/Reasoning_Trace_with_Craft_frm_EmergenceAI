import { spawn } from "node:child_process";

function run(command: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => (stderr += chunk.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} exited ${code}: ${stderr.trim()}`));
    });
  });
}

export class JobStore {
  constructor(
    private readonly database: string,
    private readonly server: string,
  ) {}

  private call(reducer: string, args: unknown[]): Promise<void> {
    return run("spacetime", [
      "call",
      "--server",
      this.server,
      this.database,
      reducer,
      ...args.map((value) => JSON.stringify(value)),
    ]);
  }

  createJob(id: string, prompt: string, model: string): Promise<void> {
    return this.call("create_job", [id, prompt, model, new Date().toISOString()]);
  }

  addMessage(
    id: string,
    jobId: string,
    sequence: number,
    role: string,
    content: string,
    toolName = "",
    toolCallId = "",
  ): Promise<void> {
    return this.call("add_message", [
      id,
      jobId,
      sequence,
      role,
      content,
      toolName,
      toolCallId,
      new Date().toISOString(),
    ]);
  }

  finishJob(id: string, answer: string): Promise<void> {
    return this.call("finish_job", [id, answer, new Date().toISOString()]);
  }

  failJob(id: string, error: string): Promise<void> {
    return this.call("fail_job", [id, error, new Date().toISOString()]);
  }
}
