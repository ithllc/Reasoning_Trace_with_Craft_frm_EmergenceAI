import { schema, table, t } from "spacetimedb/server";

const spacetimedb = schema({
  job: table(
    { public: true },
    {
      id: t.string().primaryKey(),
      prompt: t.string(),
      model: t.string(),
      status: t.string(),
      createdAt: t.string(),
      completedAt: t.string(),
      finalAnswer: t.string(),
      error: t.string(),
    },
  ),
  message: table(
    { public: true },
    {
      id: t.string().primaryKey(),
      jobId: t.string().index(),
      sequence: t.u32(),
      role: t.string(),
      content: t.string(),
      toolName: t.string(),
      toolCallId: t.string(),
      createdAt: t.string(),
    },
  ),
});

export default spacetimedb;

export const createJob = spacetimedb.reducer(
  { id: t.string(), prompt: t.string(), model: t.string(), createdAt: t.string() },
  (ctx, args) => {
    ctx.db.job.insert({
      ...args,
      status: "running",
      completedAt: "",
      finalAnswer: "",
      error: "",
    });
  },
);

export const addMessage = spacetimedb.reducer(
  {
    id: t.string(),
    jobId: t.string(),
    sequence: t.u32(),
    role: t.string(),
    content: t.string(),
    toolName: t.string(),
    toolCallId: t.string(),
    createdAt: t.string(),
  },
  (ctx, args) => ctx.db.message.insert(args),
);

export const finishJob = spacetimedb.reducer(
  { id: t.string(), finalAnswer: t.string(), completedAt: t.string() },
  (ctx, { id, finalAnswer, completedAt }) => {
    const job = ctx.db.job.id.find(id);
    if (!job) throw new Error(`Unknown job: ${id}`);
    ctx.db.job.id.update({
      ...job,
      status: "completed",
      finalAnswer,
      completedAt,
      error: "",
    });
  },
);

export const failJob = spacetimedb.reducer(
  { id: t.string(), error: t.string(), completedAt: t.string() },
  (ctx, { id, error, completedAt }) => {
    const job = ctx.db.job.id.find(id);
    if (!job) throw new Error(`Unknown job: ${id}`);
    ctx.db.job.id.update({
      ...job,
      status: "failed",
      completedAt,
      finalAnswer: "",
      error,
    });
  },
);
